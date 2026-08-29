"""Safe, in-memory PDF validation and text extraction."""

from __future__ import annotations

from dataclasses import dataclass

import fitz

DEFAULT_MAX_PDF_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 200
_PDF_HEADER_SCAN_BYTES = 1024


class PDFProcessingError(ValueError):
    """Base class for PDF validation and extraction failures."""


class PDFValidationError(PDFProcessingError):
    """Raised when uploaded data is not an acceptable PDF."""


class PDFTooLargeError(PDFValidationError):
    """Raised when a PDF exceeds the configured byte limit."""


class PDFTooManyPagesError(PDFValidationError):
    """Raised when a PDF exceeds the configured page limit."""


class PDFEncryptedError(PDFValidationError):
    """Raised when a PDF requires a password."""


class PDFMalformedError(PDFValidationError):
    """Raised when PyMuPDF cannot safely parse a PDF."""


class PDFEmptyTextError(PDFValidationError):
    """Raised when a PDF contains no extractable text."""


@dataclass(frozen=True, slots=True)
class PDFPage:
    """Text extracted from one physical PDF page."""

    page_number: int
    text: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.page_number, bool)
            or not isinstance(self.page_number, int)
            or self.page_number < 1
        ):
            raise ValueError("page_number must be one-based and positive.")
        if not isinstance(self.text, str):
            raise TypeError("page text must be a string.")


@dataclass(frozen=True, slots=True)
class ExtractedPDF:
    """Validated PDF text with explicit page provenance."""

    pages: tuple[PDFPage, ...]
    byte_size: int

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def plain_text(self) -> str:
        """Return text separated by page boundaries, without page labels."""

        return "\n\n".join(page.text for page in self.pages if page.text)

    @property
    def numbered_text(self) -> str:
        """Return extracted text with unambiguous, one-based page labels."""

        return "\n\n".join(
            f"[Page {page.page_number}]\n{page.text}"
            for page in self.pages
            if page.text
        )


def _coerce_pdf_bytes(pdf_bytes: bytes | bytearray | memoryview) -> bytes:
    if isinstance(pdf_bytes, bytes):
        return pdf_bytes
    if isinstance(pdf_bytes, (bytearray, memoryview)):
        return bytes(pdf_bytes)
    raise TypeError("pdf_bytes must be bytes-like data.")


def _validate_limits(max_bytes: int, max_pages: int) -> None:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer.")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages must be a positive integer.")


def _normalise_page_text(text: str) -> str:
    return (
        text.replace("\x00", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def extract_pdf_from_bytes(
    pdf_bytes: bytes | bytearray | memoryview,
    *,
    max_bytes: int = DEFAULT_MAX_PDF_BYTES,
    max_pages: int = DEFAULT_MAX_PDF_PAGES,
) -> ExtractedPDF:
    """Validate and extract a PDF without writing the upload to disk.

    The original bytes are used only for the duration of this call. Page numbers
    are one-based so they can be presented directly as answer citations.
    """

    _validate_limits(max_bytes, max_pages)
    raw_pdf = _coerce_pdf_bytes(pdf_bytes)

    if not raw_pdf:
        raise PDFValidationError("The uploaded PDF is empty.")
    if len(raw_pdf) > max_bytes:
        raise PDFTooLargeError(
            f"The PDF exceeds the {max_bytes} byte upload limit."
        )
    if b"%PDF-" not in raw_pdf[:_PDF_HEADER_SCAN_BYTES]:
        raise PDFValidationError("The uploaded data does not have a valid PDF header.")

    try:
        with fitz.open(stream=raw_pdf, filetype="pdf") as document:
            if document.needs_pass:
                raise PDFEncryptedError(
                    "Password-protected PDFs are not supported."
                )

            page_count = document.page_count
            if page_count < 1:
                raise PDFMalformedError("The PDF contains no pages.")
            if page_count > max_pages:
                raise PDFTooManyPagesError(
                    f"The PDF has {page_count} pages; the limit is {max_pages}."
                )

            pages = tuple(
                PDFPage(
                    page_number=page_index + 1,
                    text=_normalise_page_text(
                        document.load_page(page_index).get_text("text", sort=True)
                    ),
                )
                for page_index in range(page_count)
            )
    except PDFProcessingError:
        raise
    except Exception:
        # Parser exceptions can vary between PyMuPDF releases. Do not echo
        # parser details because they may include file-system or document data.
        raise PDFMalformedError("The PDF could not be parsed safely.") from None

    if not any(page.text.strip() for page in pages):
        raise PDFEmptyTextError(
            "No extractable text was found. Scanned PDFs require OCR."
        )

    return ExtractedPDF(pages=pages, byte_size=len(raw_pdf))


def extract_pages_from_pdf(
    pdf_bytes: bytes | bytearray | memoryview,
    **kwargs: int,
) -> tuple[PDFPage, ...]:
    """Convenience API returning page-aware text from PDF bytes."""

    return extract_pdf_from_bytes(pdf_bytes, **kwargs).pages


def extract_text_from_pdf(
    pdf_bytes: bytes | bytearray | memoryview,
    **kwargs: int,
) -> str:
    """Compatibility API returning text with explicit page labels."""

    return extract_pdf_from_bytes(pdf_bytes, **kwargs).numbered_text
