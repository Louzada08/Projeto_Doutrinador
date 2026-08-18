from __future__ import annotations

import json
from contextlib import closing
from dataclasses import asdict
from threading import RLock
from typing import Sequence

import psycopg2
from psycopg2.extras import RealDictCursor

from doutrinador.application.ports import (
    DocumentRepository, InteractionLogger, KnowledgeRetriever, PassageRepository,
    SearchResult,
)
from doutrinador.domain import Answer, Document, Passage, SourceLevel
from doutrinador.infrastructure.chunking import chunk_document
from doutrinador.infrastructure.retrieval import hybrid_search


class PostgresKnowledgeBase(
    DocumentRepository, KnowledgeRetriever, PassageRepository, InteractionLogger
):
    """Acervo persistente usando PostgreSQL via `psycopg2`."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        return psycopg2.connect(self._dsn)

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    source_level TEXT NOT NULL CHECK (source_level IN ('A','B','C','D')),
                    content TEXT NOT NULL,
                    year INTEGER,
                    edition TEXT,
                    origin TEXT,
                    provenance_note TEXT,
                    authenticity_status TEXT NOT NULL,
                    rights_status TEXT NOT NULL,
                    image_url TEXT,
                    image_description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                )
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS passages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    section TEXT,
                    page INTEGER,
                    text TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_passages_document ON passages(document_id, ordinal)"
                )
                cur.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    passages_json TEXT NOT NULL,
                    response TEXT NOT NULL,
                    grounded BOOLEAN NOT NULL,
                    observation TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                )
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS document_changes (
                    id SERIAL PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    responsible TEXT NOT NULL,
                    justification TEXT NOT NULL,
                    changed_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
                """)

    def add(self, document: Document) -> None:
        with self._lock, closing(self._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                INSERT INTO documents (
                    id, title, author, source_level, content, year, edition, origin,
                    provenance_note, authenticity_status, rights_status, image_url, image_description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """, (
                    document.id, document.title, document.author, document.source_level.value,
                    document.content, document.year, document.edition, document.origin,
                    document.provenance_note, document.authenticity_status, document.rights_status,
                    document.image_url, document.image_description,
                ))
                self._index_document(conn, document)
            conn.commit()

    def list(self) -> list[Document]:
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM documents ORDER BY created_at DESC, title")
                rows = cur.fetchall()
        return [self._to_document(row) for row in rows]

    def get(self, document_id: str) -> Document | None:
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
                row = cur.fetchone()
        return self._to_document(row) if row else None

    def update_metadata(self, document_id: str, changes: dict, responsible: str, justification: str) -> Document:
        document = self.get(document_id)
        if document is None:
            raise ValueError("Fonte não encontrada.")
        if "source_level" in changes:
            value = changes["source_level"]
            changes["source_level"] = value.value if isinstance(value, SourceLevel) else SourceLevel(str(value).upper()).value
        allowed = {
            "title", "author", "source_level", "year", "edition", "origin",
            "provenance_note", "authenticity_status", "rights_status",
            "image_url", "image_description",
        }
        changes = {key: value for key, value in changes.items() if key in allowed}
        old = {key: getattr(document, key) for key in changes}
        effective = {
            key: value for key, value in changes.items()
            if (old[key].value if isinstance(old[key], SourceLevel) else old[key]) != value
        }
        if not effective:
            raise ValueError("Nenhum valor foi alterado.")
        with self._lock, closing(self._connect()) as conn:
            with conn.cursor() as cur:
                assignments = ", ".join(f"{key} = %s" for key in effective)
                cur.execute(
                    f"UPDATE documents SET {assignments} WHERE id = %s",
                    (*effective.values(), document_id),
                )
                for field, new_value in effective.items():
                    old_value = old[field].value if isinstance(old[field], SourceLevel) else old[field]
                    cur.execute("""
                        INSERT INTO document_changes
                        (document_id, field_name, old_value, new_value, responsible, justification)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        document_id, field,
                        json.dumps(old_value, ensure_ascii=False),
                        json.dumps(new_value, ensure_ascii=False),
                        responsible, justification,
                    ))
            conn.commit()
        return self.get(document_id)

    def history(self, document_id: str) -> list[dict]:
        if self.get(document_id) is None:
            raise ValueError("Fonte não encontrada.")
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, field_name, old_value, new_value, responsible,
                           justification, changed_at
                    FROM document_changes WHERE document_id = %s
                    ORDER BY changed_at DESC, id DESC
                """, (document_id,))
                rows = cur.fetchall()
        return [{
            "id": row["id"], "field": row["field_name"],
            "old_value": json.loads(row["old_value"]) if row["old_value"] else None,
            "new_value": json.loads(row["new_value"]) if row["new_value"] else None,
            "responsible": row["responsible"], "justification": row["justification"],
            "changed_at": row["changed_at"],
        } for row in rows]

    def search(self, question: str, limit: int = 5) -> list[SearchResult]:
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id AS passage_id, p.ordinal, p.section, p.page, p.text,
                           d.*
                    FROM passages p JOIN documents d ON d.id = p.document_id
                    ORDER BY d.created_at, p.ordinal
                """)
                rows = cur.fetchall()
        items = [(self._to_document(row), self._to_passage(row)) for row in rows]
        return hybrid_search(question, items, limit)

    def get_passage(self, passage_id: str) -> Passage | None:
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id AS passage_id, p.ordinal, p.section, p.page, p.text,
                           d.*
                    FROM passages p JOIN documents d ON d.id = p.document_id
                    WHERE p.id = %s
                """, (passage_id,))
                row = cur.fetchone()
        return self._to_passage(row) if row else None

    def passages_for_document(self, document_id: str) -> list[Passage]:
        if self.get(document_id) is None:
            raise ValueError("Fonte não encontrada.")
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id AS passage_id, p.ordinal, p.section, p.page, p.text,
                           d.*
                    FROM passages p JOIN documents d ON d.id = p.document_id
                    WHERE d.id = %s ORDER BY p.ordinal
                """, (document_id,))
                rows = cur.fetchall()
        return [self._to_passage(row) for row in rows]

    def record_interaction(self, question: str, passages: Sequence[SearchResult], answer: Answer) -> int:
        consulted = [
            {
                **asdict(item.passage),
                "source_level": item.passage.source_level.value,
                "score": item.score,
                "lexical_score": item.lexical_score,
                "semantic_score": item.semantic_score,
            }
            for item in passages
        ]
        with self._lock, closing(self._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO interactions
                    (question, passages_json, response, grounded, observation)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (
                    question, json.dumps(consulted, ensure_ascii=False), answer.answer,
                    bool(answer.grounded), answer.observation,
                ))
                last = cur.fetchone()[0]
            conn.commit()
        return int(last)

    def list_interactions(self, limit: int = 100) -> list[dict]:
        with closing(self._connect()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM interactions ORDER BY created_at DESC, id DESC LIMIT %s
                """, (max(1, min(limit, 1000)),))
                rows = cur.fetchall()
        return [{
            "id": row["id"],
            "question": row["question"],
            "passages": json.loads(row["passages_json"]),
            "response": row["response"],
            "grounded": bool(row["grounded"]),
            "observation": row["observation"],
            "created_at": row["created_at"],
        } for row in rows]

    @staticmethod
    def _index_document(conn: psycopg2.extensions.connection, document: Document) -> None:
        with conn.cursor() as cur:
            for passage in chunk_document(document):
                cur.execute("""
                    INSERT INTO passages (id, document_id, ordinal, section, page, text)
                    VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
                """, (
                    passage.id, passage.document_id, passage.ordinal,
                    passage.section, passage.page, passage.text,
                ))

    @staticmethod
    def _to_passage(row: dict) -> Passage:
        return Passage(
            id=row["passage_id"], document_id=row["id"], title=row["title"],
            author=row["author"], source_level=SourceLevel(row["source_level"]),
            text=row["text"], ordinal=row["ordinal"], section=row["section"],
            page=row["page"], image_url=row.get("image_url"), image_description=row.get("image_description"),
        )

    @staticmethod
    def _to_document(row: dict) -> Document:
        return Document(
            id=row["id"], title=row["title"], author=row["author"],
            source_level=SourceLevel(row["source_level"]), content=row["content"],
            year=row.get("year"), edition=row.get("edition"), origin=row.get("origin"),
            provenance_note=row.get("provenance_note"),
            authenticity_status=row.get("authenticity_status"), rights_status=row.get("rights_status"),
            image_url=row.get("image_url"), image_description=row.get("image_description"),
        )
