from __future__ import annotations

import sqlite3
import json
from contextlib import closing
from pathlib import Path
from threading import RLock

from doutrinador.application.ports import DocumentRepository, KnowledgeRetriever, SearchResult
from doutrinador.domain import Document, SourceLevel
from doutrinador.infrastructure.memory import _passages, _tokens


class SQLiteKnowledgeBase(DocumentRepository, KnowledgeRetriever):
    """Acervo persistente baseado apenas na biblioteca padrão do Python."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    source_level TEXT NOT NULL CHECK(source_level IN ('A','B','C','D')),
                    content TEXT NOT NULL,
                    year INTEGER,
                    edition TEXT,
                    origin TEXT,
                    provenance_note TEXT,
                    authenticity_status TEXT NOT NULL,
                    rights_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(documents)")
                }
                if "provenance_note" not in columns:
                    connection.execute(
                        "ALTER TABLE documents ADD COLUMN provenance_note TEXT"
                    )
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS document_changes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL,
                        field_name TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT,
                        responsible TEXT NOT NULL,
                        justification TEXT NOT NULL,
                        changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(document_id) REFERENCES documents(id)
                    )
                """)

    def add(self, document: Document) -> None:
        with self._lock, closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                INSERT INTO documents (
                    id, title, author, source_level, content, year, edition, origin,
                    provenance_note,
                    authenticity_status, rights_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document.id, document.title, document.author, document.source_level.value,
                    document.content, document.year, document.edition, document.origin,
                    document.provenance_note,
                    document.authenticity_status, document.rights_status,
                ))

    def list(self) -> list[Document]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM documents ORDER BY created_at DESC, title"
            ).fetchall()
        return [self._to_document(row) for row in rows]

    def get(self, document_id: str) -> Document | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
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
        }
        changes = {key: value for key, value in changes.items() if key in allowed}
        old = {key: getattr(document, key) for key in changes}
        effective = {
            key: value for key, value in changes.items()
            if (old[key].value if isinstance(old[key], SourceLevel) else old[key]) != value
        }
        if not effective:
            raise ValueError("Nenhum valor foi alterado.")
        with self._lock, closing(self._connect()) as connection:
            with connection:
                assignments = ", ".join(f"{key} = ?" for key in effective)
                connection.execute(
                    f"UPDATE documents SET {assignments} WHERE id = ?",
                    (*effective.values(), document_id),
                )
                for field, new_value in effective.items():
                    old_value = old[field].value if isinstance(old[field], SourceLevel) else old[field]
                    connection.execute("""
                        INSERT INTO document_changes
                        (document_id, field_name, old_value, new_value, responsible, justification)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        document_id, field,
                        json.dumps(old_value, ensure_ascii=False),
                        json.dumps(new_value, ensure_ascii=False),
                        responsible, justification,
                    ))
        return self.get(document_id)

    def history(self, document_id: str) -> list[dict]:
        if self.get(document_id) is None:
            raise ValueError("Fonte não encontrada.")
        with closing(self._connect()) as connection:
            rows = connection.execute("""
                SELECT id, field_name, old_value, new_value, responsible,
                       justification, changed_at
                FROM document_changes WHERE document_id = ?
                ORDER BY changed_at DESC, id DESC
            """, (document_id,)).fetchall()
        return [{
            "id": row["id"], "field": row["field_name"],
            "old_value": json.loads(row["old_value"]),
            "new_value": json.loads(row["new_value"]),
            "responsible": row["responsible"], "justification": row["justification"],
            "changed_at": row["changed_at"],
        } for row in rows]

    def search(self, question: str, limit: int = 3) -> list[SearchResult]:
        query = _tokens(question)
        if not query:
            return []
        precedence = {"A": 1.0, "B": 0.92, "C": 0.82, "D": 0.68}
        ranked: list[SearchResult] = []
        for document in self.list():
            for excerpt in _passages(document.content):
                found = query & _tokens(excerpt)
                if found:
                    score = (len(found) / len(query)) * precedence[document.source_level.value]
                    ranked.append(SearchResult(document, excerpt, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _to_document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"], title=row["title"], author=row["author"],
            source_level=SourceLevel(row["source_level"]), content=row["content"],
            year=row["year"], edition=row["edition"], origin=row["origin"],
            provenance_note=row["provenance_note"],
            authenticity_status=row["authenticity_status"], rights_status=row["rights_status"],
        )
