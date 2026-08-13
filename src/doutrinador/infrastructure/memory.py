from __future__ import annotations

import re
import unicodedata

from doutrinador.application.ports import DocumentRepository, KnowledgeRetriever, SearchResult
from doutrinador.domain import Document


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return {t for t in re.findall(r"[a-z0-9]+", normalized) if len(t) > 2}


def _passages(content: str, max_chars: int = 520) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    passages: list[str] = []
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                passages.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            passages.append(current)
    return passages


class InMemoryKnowledgeBase(DocumentRepository, KnowledgeRetriever):
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def add(self, document: Document) -> None:
        self._documents[document.id] = document

    def list(self) -> list[Document]:
        return list(self._documents.values())

    def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def update_metadata(self, document_id: str, changes: dict, responsible: str, justification: str) -> Document:
        from dataclasses import replace
        document = self.get(document_id)
        if document is None:
            raise ValueError("Fonte não encontrada.")
        updated = replace(document, **changes)
        self._documents[document_id] = updated
        return updated

    def history(self, document_id: str) -> list[dict]:
        return []

    def search(self, question: str, limit: int = 3) -> list[SearchResult]:
        query = _tokens(question)
        if not query:
            return []
        ranked: list[SearchResult] = []
        precedence = {"A": 1.0, "B": 0.92, "C": 0.82, "D": 0.68}
        for document in self._documents.values():
            for excerpt in _passages(document.content):
                found = query & _tokens(excerpt)
                if not found:
                    continue
                score = (len(found) / len(query)) * precedence[document.source_level.value]
                ranked.append(SearchResult(document, excerpt, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]
