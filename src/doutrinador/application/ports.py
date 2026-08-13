from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from doutrinador.domain import Document


@dataclass(frozen=True, slots=True)
class SearchResult:
    document: Document
    excerpt: str
    score: float


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
