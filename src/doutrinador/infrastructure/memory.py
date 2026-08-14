from __future__ import annotations

from dataclasses import asdict, replace
from typing import Sequence

from doutrinador.application.ports import (
    DocumentRepository, InteractionLogger, KnowledgeRetriever, PassageRepository,
    SearchResult,
)
from doutrinador.domain import Answer, Document, Passage, SourceLevel
from doutrinador.infrastructure.chunking import chunk_document
from doutrinador.infrastructure.retrieval import hybrid_search, tokens


# Compatibilidade com extensões da versão 0.4.
def _tokens(text: str) -> set[str]:
    return set(tokens(text))


def _passages(content: str, max_chars: int = 520) -> list[str]:
    temporary = Document("Temporário", "Sistema", SourceLevel.D, content)
    return [item.text for item in chunk_document(temporary, max_chars)]


class InMemoryKnowledgeBase(
    DocumentRepository, KnowledgeRetriever, PassageRepository, InteractionLogger
):
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._passages: dict[str, Passage] = {}
        self._interactions: list[dict] = []

    def add(self, document: Document) -> None:
        self._documents[document.id] = document
        for passage in chunk_document(document):
            self._passages[passage.id] = passage

    def list(self) -> list[Document]:
        return list(self._documents.values())

    def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def update_metadata(
        self, document_id: str, changes: dict, responsible: str, justification: str
    ) -> Document:
        document = self.get(document_id)
        if document is None:
            raise ValueError("Fonte não encontrada.")
        updated = replace(document, **changes)
        self._documents[document_id] = updated
        for passage_id, passage in list(self._passages.items()):
            if passage.document_id == document_id:
                self._passages[passage_id] = replace(
                    passage,
                    title=updated.title,
                    author=updated.author,
                    source_level=updated.source_level,
                    image_url=updated.image_url,
                    image_description=updated.image_description,
                )
        return updated

    def history(self, document_id: str) -> list[dict]:
        return []

    def search(self, question: str, limit: int = 5) -> list[SearchResult]:
        items = [
            (self._documents[passage.document_id], passage)
            for passage in self._passages.values()
        ]
        return hybrid_search(question, items, limit)

    def get_passage(self, passage_id: str) -> Passage | None:
        return self._passages.get(passage_id)

    def passages_for_document(self, document_id: str) -> list[Passage]:
        return sorted(
            (item for item in self._passages.values() if item.document_id == document_id),
            key=lambda item: item.ordinal,
        )

    def record_interaction(
        self, question: str, passages: Sequence[SearchResult], answer: Answer
    ) -> int:
        interaction_id = len(self._interactions) + 1
        self._interactions.append({
            "id": interaction_id,
            "question": question,
            "passages": [
                {**asdict(item.passage), "score": item.score,
                 "lexical_score": item.lexical_score, "semantic_score": item.semantic_score}
                for item in passages
            ],
            "response": answer.answer,
            "grounded": answer.grounded,
            "observation": answer.observation,
        })
        return interaction_id

    def list_interactions(self, limit: int = 100) -> list[dict]:
        return list(reversed(self._interactions[-limit:]))
