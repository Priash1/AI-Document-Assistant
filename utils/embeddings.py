"""Local, normalized SentenceTransformer embeddings."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import Any

import numpy as np

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingError(RuntimeError):
    """Raised when the embedding model cannot produce safe vectors."""


@lru_cache(maxsize=1)
def load_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> Any:
    """Load and retain one SentenceTransformer model per process."""

    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a non-empty string.")

    # Lazy import keeps unit tests and non-embedding app paths lightweight.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name.strip())


def clear_embedding_model_cache() -> None:
    """Release the cached model, primarily for controlled tests/shutdown."""

    load_embedding_model.cache_clear()


def _chunk_text(chunk: Any) -> str:
    text = chunk if isinstance(chunk, str) else getattr(chunk, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Every embedding input must contain non-empty text.")
    return text.strip()


def _normalise_embeddings(raw_vectors: Any, expected_rows: int) -> np.ndarray:
    vectors = np.asarray(raw_vectors, dtype=np.float32)
    if vectors.ndim == 1 and expected_rows == 1:
        vectors = vectors.reshape(1, -1)
    if (
        vectors.ndim != 2
        or vectors.shape[0] != expected_rows
        or vectors.shape[1] < 1
    ):
        raise EmbeddingError("The embedding model returned an invalid shape.")
    if not np.isfinite(vectors).all():
        raise EmbeddingError("The embedding model returned non-finite values.")

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= np.finfo(np.float32).eps):
        raise EmbeddingError("The embedding model returned a zero-length vector.")

    normalized = vectors / norms
    return np.ascontiguousarray(normalized, dtype=np.float32)


def create_embeddings(
    chunks: Iterable[Any],
    *,
    model: Any | None = None,
) -> np.ndarray:
    """Embed document chunks as finite, L2-normalized float32 rows."""

    texts = [_chunk_text(chunk) for chunk in chunks]
    if not texts:
        raise ValueError("At least one non-empty chunk is required.")
    embedding_model = model if model is not None else load_embedding_model()

    try:
        raw_vectors = embedding_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception:
        raise EmbeddingError(
            "The embedding model could not encode the document."
        ) from None

    return _normalise_embeddings(raw_vectors, len(texts))


def create_query_embedding(
    query: str,
    *,
    model: Any | None = None,
) -> np.ndarray:
    """Embed one query using the same normalized vector space as documents."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    embedding_model = model if model is not None else load_embedding_model()

    try:
        raw_vector = embedding_model.encode(
            [query.strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception:
        raise EmbeddingError("The embedding model could not encode the query.") from None

    return _normalise_embeddings(raw_vector, 1)
