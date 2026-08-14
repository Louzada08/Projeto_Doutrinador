from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from doutrinador.domain import Answer, Document, Passage


@dataclass(frozen=True, slots=True)
class SearchResult:
    document: Document
    passage: Passage
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0

    @property
    def excerpt(self) -> str:
        return self.passage.text


class DocumentRepository(ABC):
    @abstractmethod
    def add(self, document: Document) -> None: ...

    @abstractmethod
    def list(self) -> list[Document]: ...

    @abstractmethod
    def get(self, document_id: str) -> Document | None: ...

    @abstractmethod
    def update_metadata(
        self, document_id: str, changes: dict, responsible: str, justification: str
    ) -> Document: ...

    @abstractmethod
    def history(self, document_id: str) -> list[dict]: ...


class KnowledgeRetriever(ABC):
    @abstractmethod
    def search(self, question: str, limit: int = 3) -> list[SearchResult]: ...


class PassageRepository(ABC):
    @abstractmethod
    def get_passage(self, passage_id: str) -> Passage | None: ...

    @abstractmethod
    def passages_for_document(self, document_id: str) -> list[Passage]: ...


class AnswerGenerator(ABC):
    @abstractmethod
    def generate(
        self, question: str, passages: Sequence[SearchResult], system_instruction: str
    ) -> str: ...


class InteractionLogger(ABC):
    @abstractmethod
    def record_interaction(
        self, question: str, passages: Sequence[SearchResult], answer: Answer
    ) -> int: ...

    @abstractmethod
    def list_interactions(self, limit: int = 100) -> list[dict]: ...
