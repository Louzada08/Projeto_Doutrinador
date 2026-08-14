from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from doutrinador.domain import Document, Passage


PAGE_MARKER = re.compile(r"^\s*\[\[(?:PAGE|PÁGINA):\s*(\d+)]]\s*$", re.IGNORECASE)
SECTION_MARKER = re.compile(r"^\s*\[\[(?:SECTION|SEÇÃO):\s*(.+?)]]\s*$", re.IGNORECASE)
MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")


@dataclass(slots=True)
class _Block:
    text: str
    section: str | None
    page: int


def chunk_document(document: Document, max_chars: int = 900) -> list[Passage]:
    """Divide texto sem perder título, seção e página.

    Quebras de formulário avançam a página. Marcadores ``[[PÁGINA: 12]]`` e
    ``[[SEÇÃO: Título]]`` permitem preservar numeração e seções de uma
    extração. Cabeçalhos Markdown também definem a seção corrente.
    """

    blocks = _blocks(document.content)
    grouped: list[_Block] = []
    current = ""
    location: tuple[str | None, int] | None = None
    for block in blocks:
        block_location = (block.section, block.page)
        pieces = _split_oversized(block.text, max_chars)
        for piece in pieces:
            if current and (location != block_location or len(current) + len(piece) + 2 > max_chars):
                grouped.append(_Block(current, location[0], location[1]))
                current = ""
            location = block_location
            current = f"{current}\n\n{piece}".strip()
    if current and location:
        grouped.append(_Block(current, location[0], location[1]))

    passages: list[Passage] = []
    for ordinal, block in enumerate(grouped, start=1):
        identity = f"{document.id}\0{ordinal}\0{block.page}\0{block.section or ''}\0{block.text}"
        passage_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        passages.append(Passage(
            id=passage_id,
            document_id=document.id,
            title=document.title,
            author=document.author,
            source_level=document.source_level,
            text=block.text,
            ordinal=ordinal,
            section=block.section,
            page=block.page,
            image_url=document.image_url,
            image_description=document.image_description,
        ))
    return passages


def _blocks(content: str) -> list[_Block]:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.replace("\f", "\n\n[[__PAGE_BREAK__]]\n\n").split("\n")
    page = 1
    section: str | None = None
    paragraph: list[str] = []
    result: list[_Block] = []

    def flush() -> None:
        if paragraph:
            text = "\n".join(paragraph).strip()
            if text:
                result.append(_Block(text, section, page))
            paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if stripped == "[[__PAGE_BREAK__]]":
            flush()
            page += 1
            continue
        page_match = PAGE_MARKER.match(line)
        if page_match:
            flush()
            page = int(page_match.group(1))
            continue
        section_match = SECTION_MARKER.match(line) or MARKDOWN_HEADING.match(line)
        if section_match:
            flush()
            section = section_match.group(1).strip()
            continue
        if not stripped:
            flush()
            continue
        paragraph.append(line.strip())
    flush()
    return result


def _split_oversized(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split()
            for word in words:
                if current and len(current) + len(word) + 1 > max_chars:
                    pieces.append(current)
                    current = ""
                current = f"{current} {word}".strip()
        elif current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces
