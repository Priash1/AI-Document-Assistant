"""Small, dependency-free text chunking with page provenance."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from utils.pdf_loader import ExtractedPDF, PDFPage

DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_OVERLAP = 200


class ChunkingError(ValueError):
    """Raised when text cannot be converted into useful chunks."""


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A retrieval unit tied to its source PDF page or pages."""

    chunk_id: int
    text: str
    page_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.chunk_id, bool)
            or not isinstance(self.chunk_id, int)
            or self.chunk_id < 0
        ):
            raise ValueError("chunk_id must be non-negative.")
        if not isinstance(self.text, str):
            raise TypeError("chunk text must be a string.")
        if not self.text.strip():
            raise ValueError("A document chunk cannot contain only whitespace.")
        if (
            not isinstance(self.page_numbers, tuple)
            or not self.page_numbers
            or any(
                isinstance(page, bool) or not isinstance(page, int) or page < 1
                for page in self.page_numbers
            )
        ):
            raise ValueError("page_numbers must contain positive page numbers.")

    @property
    def source_label(self) -> str:
        pages = ", ".join(str(page) for page in self.page_numbers)
        prefix = "p." if len(self.page_numbers) == 1 else "pp."
        return f"{prefix} {pages}"


def _validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size < 1
    ):
        raise ValueError("chunk_size must be a positive integer.")
    if (
        isinstance(chunk_overlap, bool)
        or not isinstance(chunk_overlap, int)
        or chunk_overlap < 0
        or chunk_overlap >= chunk_size
    ):
        raise ValueError(
            "chunk_overlap must be a non-negative integer smaller than chunk_size."
        )


def _preferred_split(text: str, start: int, hard_end: int) -> int:
    """Choose a readable boundary without producing very small chunks."""

    if hard_end >= len(text):
        return len(text)

    minimum = start + max(1, (hard_end - start) // 2)
    for separator in ("\n\n", "\n", ". ", " "):
        boundary = text.rfind(separator, minimum, hard_end)
        if boundary >= minimum:
            return boundary + len(separator)
    return hard_end


def _split_page(
    page: PDFPage,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    text = page.text.strip()
    if not text:
        return []

    pieces: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = _preferred_split(text, start, hard_end)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break

        next_start = end - chunk_overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return pieces


def split_pages_into_chunks(
    pages: Iterable[PDFPage],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split page-aware text while preserving one-based source page numbers."""

    _validate_chunk_settings(chunk_size, chunk_overlap)
    chunks: list[DocumentChunk] = []

    for page in pages:
        if not isinstance(page, PDFPage):
            raise TypeError("pages must contain PDFPage objects.")
        for piece in _split_page(
            page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ):
            chunks.append(
                DocumentChunk(
                    chunk_id=len(chunks),
                    text=piece,
                    page_numbers=(page.page_number,),
                )
            )

    if not chunks:
        raise ChunkingError("No non-empty document text was available to chunk.")
    return chunks


def split_document_into_chunks(
    document: ExtractedPDF,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Chunk an extracted PDF and retain its page provenance."""

    if not isinstance(document, ExtractedPDF):
        raise TypeError("document must be an ExtractedPDF instance.")
    return split_pages_into_chunks(
        document.pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def split_text_into_chunks(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Compatibility helper for non-PDF text without LangChain imports."""

    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    chunks = split_pages_into_chunks(
        (PDFPage(page_number=1, text=text),),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return [chunk.text for chunk in chunks]
