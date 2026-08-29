from __future__ import annotations

import unittest

from utils.chunker import (
    ChunkingError,
    DocumentChunk,
    split_pages_into_chunks,
    split_text_into_chunks,
)
from utils.pdf_loader import PDFPage


class ChunkerTests(unittest.TestCase):
    def test_chunks_are_bounded_and_keep_page_provenance(self) -> None:
        pages = (
            PDFPage(1, "alpha beta gamma delta " * 8),
            PDFPage(2, "second page evidence " * 6),
        )

        chunks = split_pages_into_chunks(
            pages,
            chunk_size=60,
            chunk_overlap=12,
        )

        self.assertGreater(len(chunks), 2)
        self.assertEqual([chunk.chunk_id for chunk in chunks], list(range(len(chunks))))
        self.assertTrue(all(0 < len(chunk.text) <= 60 for chunk in chunks))
        self.assertEqual(chunks[0].page_numbers, (1,))
        self.assertIn((2,), {chunk.page_numbers for chunk in chunks})
        self.assertEqual(chunks[0].source_label, "p. 1")

    def test_overlap_preserves_shared_source_text(self) -> None:
        text = "0123456789" * 8
        chunks = split_pages_into_chunks(
            (PDFPage(1, text),),
            chunk_size=30,
            chunk_overlap=10,
        )

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0].text[-10:], chunks[1].text[:10])

    def test_skips_blank_pages_but_preserves_physical_page_number(self) -> None:
        chunks = split_pages_into_chunks(
            (PDFPage(1, "   "), PDFPage(2, "usable text")),
            chunk_size=50,
            chunk_overlap=5,
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_numbers, (2,))

    def test_empty_document_is_rejected(self) -> None:
        with self.assertRaises(ChunkingError):
            split_pages_into_chunks((PDFPage(1, "  "),))

    def test_invalid_chunk_settings_are_rejected(self) -> None:
        page = PDFPage(1, "content")
        for size, overlap in ((0, 0), (10, -1), (10, 10), (True, 0)):
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                split_pages_into_chunks(
                    (page,),
                    chunk_size=size,
                    chunk_overlap=overlap,
                )

    def test_legacy_text_helper_uses_lightweight_chunker(self) -> None:
        chunks = split_text_into_chunks(
            "one two three four five six",
            chunk_size=12,
            chunk_overlap=3,
        )
        self.assertTrue(chunks)
        self.assertTrue(all(isinstance(chunk, str) for chunk in chunks))

    def test_document_chunk_validates_metadata(self) -> None:
        with self.assertRaises(ValueError):
            DocumentChunk(-1, "text", (1,))
        with self.assertRaises(ValueError):
            DocumentChunk(0, " ", (1,))
        with self.assertRaises(ValueError):
            DocumentChunk(0, "text", ())


if __name__ == "__main__":
    unittest.main()
