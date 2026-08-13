from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class SourceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True, slots=True)
class Document:
    title: str
    author: str
    source_level: SourceLevel
    content: str
    year: int | None = None
    edition: str | None = None
    origin: str | None = None
    provenance_note: str | None = None
    authenticity_status: str = "pendente"
    rights_status: str = "não informado"
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.author.strip() or not self.content.strip():
            raise ValueError("Título, autoria e conteúdo são obrigatórios.")


@dataclass(frozen=True, slots=True)
class Citation:
    document_id: str
    title: str
    author: str
    source_level: SourceLevel
    excerpt: str


@dataclass(frozen=True, slots=True)
class Answer:
    answer: str
    citations: tuple[Citation, ...]
    grounded: bool
    observation: str | None = None
