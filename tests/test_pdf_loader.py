from __future__ import annotations

import unittest

import fitz

from utils import pdf_loader
from utils.pdf_loader import (
    PDFEmptyTextError,
    PDFEncryptedError,
    PDFMalformedError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    PDFValidationError,
    extract_pdf_from_bytes,
    extract_text_from_pdf,
)


def _make_pdf(page_texts: list[str], *, encrypted: bool = False) -> bytes:
    with fitz.open() as document:
        for text in page_texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        if encrypted:
            return document.tobytes(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner-password",
                user_pw="user-password",
            )
        return document.tobytes()


class PDFLoaderTests(unittest.TestCase):
    def test_extracts_page_numbered_text_from_memory(self) -> None:
        raw_pdf = _make_pdf(["First page secret", "Second page fact"])

        extracted = extract_pdf_from_bytes(raw_pdf)

        self.assertEqual(extracted.byte_size, len(raw_pdf))
        self.assertEqual(extracted.page_count, 2)
        self.assertEqual([page.page_number for page in extracted.pages], [1, 2])
        self.assertIn("First page secret", extracted.pages[0].text)
        self.assertIn("Second page fact", extracted.pages[1].text)
        self.assertIn("[Page 1]", extracted.numbered_text)
        self.assertIn("[Page 2]", extract_text_from_pdf(memoryview(raw_pdf)))

    def test_rejects_empty_non_pdf_and_non_bytes_inputs(self) -> None:
        with self.assertRaises(PDFValidationError):
            extract_pdf_from_bytes(b"")
        with self.assertRaises(PDFValidationError):
            extract_pdf_from_bytes(b"not a pdf")
        with self.assertRaises(TypeError):
            extract_pdf_from_bytes("%PDF-1.7")  # type: ignore[arg-type]

    def test_rejects_oversized_pdf_before_parsing(self) -> None:
        raw_pdf = _make_pdf(["small"])
        with self.assertRaises(PDFTooLargeError):
            extract_pdf_from_bytes(raw_pdf, max_bytes=len(raw_pdf) - 1)

    def test_rejects_too_many_pages(self) -> None:
        raw_pdf = _make_pdf(["one", "two"])
        with self.assertRaises(PDFTooManyPagesError):
            extract_pdf_from_bytes(raw_pdf, max_pages=1)

    def test_rejects_password_protected_pdf(self) -> None:
        raw_pdf = _make_pdf(["protected"], encrypted=True)
        with self.assertRaises(PDFEncryptedError):
            extract_pdf_from_bytes(raw_pdf)

    def test_rejects_malformed_pdf_with_header(self) -> None:
        with self.assertRaises(PDFMalformedError):
            extract_pdf_from_bytes(b"%PDF-1.7\nthis is not a real PDF")

    def test_rejects_pdf_without_extractable_text(self) -> None:
        raw_pdf = _make_pdf([""])
        with self.assertRaises(PDFEmptyTextError):
            extract_pdf_from_bytes(raw_pdf)

    def test_rejects_invalid_limits(self) -> None:
        raw_pdf = _make_pdf(["text"])
        with self.assertRaises(ValueError):
            extract_pdf_from_bytes(raw_pdf, max_bytes=0)
        with self.assertRaises(ValueError):
            extract_pdf_from_bytes(raw_pdf, max_pages=True)

    def test_has_no_permanent_upload_save_api(self) -> None:
        self.assertFalse(hasattr(pdf_loader, "save_uploaded_file"))


if __name__ == "__main__":
    unittest.main()
