from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from utils.chunker import DocumentChunk
from utils.embeddings import (
    EmbeddingError,
    clear_embedding_model_cache,
    create_embeddings,
    create_query_embedding,
    load_embedding_model,
)
from utils.vector_store import (
    VectorStoreError,
    create_faiss_index,
    create_vector_store,
    search_faiss_index,
    search_vector_store,
)


class _FakeEncoder:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = np.asarray(vectors, dtype=np.float64)
        self.calls: list[dict[str, object]] = []

    def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
        self.calls.append({"texts": texts, **kwargs})
        return self.vectors[: len(texts)]


class EmbeddingTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_embedding_model_cache()

    def test_document_and_query_vectors_are_normalized_float32(self) -> None:
        document_model = _FakeEncoder([[3.0, 4.0], [0.0, 2.0]])
        query_model = _FakeEncoder([[6.0, 8.0]])

        document_vectors = create_embeddings(
            ["first", DocumentChunk(1, "second", (2,))],
            model=document_model,
        )
        query_vector = create_query_embedding("question", model=query_model)

        self.assertEqual(document_vectors.dtype, np.float32)
        self.assertEqual(query_vector.dtype, np.float32)
        np.testing.assert_allclose(
            np.linalg.norm(document_vectors, axis=1),
            np.ones(2),
            atol=1e-6,
        )
        np.testing.assert_allclose(np.linalg.norm(query_vector, axis=1), [1.0])
        self.assertTrue(document_model.calls[0]["normalize_embeddings"])
        self.assertFalse(document_model.calls[0]["show_progress_bar"])

    def test_embedding_model_is_loaded_once(self) -> None:
        created: list[str] = []
        fake_module = types.ModuleType("sentence_transformers")

        class FakeSentenceTransformer:
            def __init__(self, name: str) -> None:
                created.append(name)

        fake_module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            first = load_embedding_model("test/model")
            second = load_embedding_model("test/model")

        self.assertIs(first, second)
        self.assertEqual(created, ["test/model"])

    def test_embedding_failures_are_safe(self) -> None:
        with self.assertRaises(ValueError):
            create_embeddings([], model=_FakeEncoder([]))
        with self.assertRaises(ValueError):
            create_query_embedding(" ", model=_FakeEncoder([[1.0]]))
        with self.assertRaises(EmbeddingError):
            create_embeddings(["text"], model=_FakeEncoder([[0.0, 0.0]]))
        with self.assertRaises(EmbeddingError):
            create_embeddings(["text"], model=_FakeEncoder([[float("nan"), 1.0]]))


class VectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = (
            DocumentChunk(0, "alpha", (1,)),
            DocumentChunk(1, "beta", (2,)),
        )

    def test_cosine_search_clamps_top_k_and_maps_chunks(self) -> None:
        store = create_vector_store(
            np.asarray([[10.0, 0.0], [0.0, 5.0]]),
            self.chunks,
        )

        results = search_vector_store(store, [[4.0, 0.0]], top_k=99)

        self.assertEqual(len(results), 2)
        self.assertEqual([result.index for result in results], [0, 1])
        self.assertEqual([result.chunk.text for result in results], ["alpha", "beta"])
        self.assertAlmostEqual(results[0].score, 1.0, places=6)
        self.assertNotIn(-1, [result.index for result in results])

    def test_raw_search_never_returns_faiss_negative_sentinel(self) -> None:
        index = create_faiss_index([[1.0, 0.0], [0.0, 1.0]])
        scores, indices = search_faiss_index(index, [[1.0, 0.0]], top_k=3)
        self.assertEqual(scores.shape, (1, 2))
        self.assertEqual(indices.shape, (1, 2))
        self.assertTrue((indices >= 0).all())

    def test_similarity_threshold_filters_results(self) -> None:
        store = create_vector_store([[1.0, 0.0], [0.0, 1.0]], self.chunks)
        results = search_vector_store(
            store,
            [[1.0, 0.0]],
            top_k=2,
            min_score=0.5,
        )
        self.assertEqual([result.index for result in results], [0])

    def test_rejects_mapping_dimension_and_query_errors(self) -> None:
        with self.assertRaises(VectorStoreError):
            create_vector_store([[1.0, 0.0]], self.chunks)
        with self.assertRaises(VectorStoreError):
            create_faiss_index([[0.0, 0.0]])

        store = create_vector_store([[1.0, 0.0], [0.0, 1.0]], self.chunks)
        with self.assertRaises(VectorStoreError):
            search_vector_store(store, [[1.0, 0.0, 0.0]])
        with self.assertRaises(VectorStoreError):
            search_vector_store(store, [[1.0, 0.0], [0.0, 1.0]])
        with self.assertRaises(VectorStoreError):
            search_vector_store(store, [[1.0, 0.0]], top_k=0)
        with self.assertRaises(VectorStoreError):
            search_vector_store(store, [[1.0, 0.0]], min_score=2.0)


if __name__ == "__main__":
    unittest.main()
