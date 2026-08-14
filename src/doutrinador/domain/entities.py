from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse
from uuid import uuid4


class SourceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


def validate_image_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("O endereço da imagem deve ser uma URL HTTP ou HTTPS válida.")
    return value


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
    image_url: str | None = None
    image_description: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.author.strip() or not self.content.strip():
            raise ValueError("Título, autoria e conteúdo são obrigatórios.")
        validate_image_url(self.image_url)


@dataclass(frozen=True, slots=True)
class Citation:
    passage_id: str
    document_id: str
    title: str
    author: str
    source_level: SourceLevel
    excerpt: str
    section: str | None = None
    page: int | None = None
    source_url: str | None = None
    image_url: str | None = None
    image_description: str | None = None


@dataclass(frozen=True, slots=True)
class Passage:
    """Trecho endereçável que preserva sua localização na fonte."""

    id: str
    document_id: str
    title: str
    author: str
    source_level: SourceLevel
    text: str
    ordinal: int
    section: str | None = None
    page: int | None = None
    image_url: str | None = None
    image_description: str | None = None


@dataclass(frozen=True, slots=True)
class Answer:
    answer: str
    citations: tuple[Citation, ...]
    grounded: bool
    observation: str | None = None
    interaction_id: int | None = None
