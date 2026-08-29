"""Cosine-similarity FAISS storage with safe chunk result mapping."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real
from typing import Any

import faiss
import numpy as np

from utils.chunker import DocumentChunk


class VectorStoreError(ValueError):
    """Raised for invalid vector-store inputs or searches."""


@dataclass(frozen=True, slots=True)
class VectorStore:
    """A FAISS index and its positionally aligned document chunks."""

    index: Any
    chunks: tuple[DocumentChunk, ...]

    @property
    def size(self) -> int:
        return int(self.index.ntotal)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One ranked chunk returned by cosine similarity."""

    rank: int
    index: int
    score: float
    chunk: DocumentChunk


def _as_float32_matrix(values: Any, *, label: str) -> np.ndarray:
    try:
        matrix = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise VectorStoreError(f"{label} must be a numeric matrix.") from exc

    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2 or matrix.shape[0] < 1 or matrix.shape[1] < 1:
        raise VectorStoreError(f"{label} must be a non-empty two-dimensional matrix.")
    if not np.isfinite(matrix).all():
        raise VectorStoreError(f"{label} must contain only finite values.")
    return np.ascontiguousarray(matrix, dtype=np.float32)


def _normalise_rows(matrix: np.ndarray, *, label: str) -> np.ndarray:
    normalized = matrix.copy()
    norms = np.linalg.norm(normalized, axis=1, keepdims=True)
    if np.any(norms <= np.finfo(np.float32).eps):
        raise VectorStoreError(f"{label} cannot contain zero-length vectors.")
    normalized /= norms
    return np.ascontiguousarray(normalized, dtype=np.float32)


def _validated_top_k(top_k: int, available: int) -> int:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise VectorStoreError("top_k must be a positive integer.")
    if available < 1:
        raise VectorStoreError("The vector index is empty.")
    return min(top_k, available)


def create_faiss_index(embeddings: Any) -> Any:
    """Create an exact cosine-similarity index from document embeddings."""

    matrix = _normalise_rows(
        _as_float32_matrix(embeddings, label="embeddings"),
        label="embeddings",
    )
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    return index


def search_faiss_index(
    index: Any,
    query_embedding: Any,
    top_k: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Search a raw FAISS index, clamping k to avoid sentinel -1 results."""

    if not hasattr(index, "search") or not hasattr(index, "ntotal"):
        raise TypeError("index must be a FAISS-compatible index.")
    safe_k = _validated_top_k(top_k, int(index.ntotal))
    query_matrix = _normalise_rows(
        _as_float32_matrix(query_embedding, label="query_embedding"),
        label="query_embedding",
    )
    if query_matrix.shape[1] != int(index.d):
        raise VectorStoreError(
            "The query embedding dimension does not match the vector index."
        )
    return index.search(query_matrix, safe_k)


def create_vector_store(
    embeddings: Any,
    chunks: Iterable[DocumentChunk],
) -> VectorStore:
    """Build an index with a validated one-to-one chunk mapping."""

    chunk_tuple = tuple(chunks)
    if not chunk_tuple:
        raise VectorStoreError("At least one document chunk is required.")
    if any(not isinstance(chunk, DocumentChunk) for chunk in chunk_tuple):
        raise TypeError("chunks must contain DocumentChunk objects.")

    matrix = _as_float32_matrix(embeddings, label="embeddings")
    if matrix.shape[0] != len(chunk_tuple):
        raise VectorStoreError(
            "The embedding row count must match the number of chunks."
        )
    return VectorStore(index=create_faiss_index(matrix), chunks=chunk_tuple)


def search_vector_store(
    store: VectorStore,
    query_embedding: Any,
    *,
    top_k: int = 3,
    min_score: float | None = None,
) -> list[SearchResult]:
    """Return scored chunks for one normalized cosine query."""

    if not isinstance(store, VectorStore):
        raise TypeError("store must be a VectorStore instance.")
    if min_score is not None:
        if isinstance(min_score, bool) or not isinstance(min_score, Real):
            raise VectorStoreError("min_score must be a number between -1 and 1.")
        if not -1.0 <= float(min_score) <= 1.0:
            raise VectorStoreError("min_score must be a number between -1 and 1.")

    query_matrix = _as_float32_matrix(
        query_embedding,
        label="query_embedding",
    )
    if query_matrix.shape[0] != 1:
        raise VectorStoreError("search_vector_store accepts exactly one query.")

    scores, indices = search_faiss_index(
        store.index,
        query_matrix,
        top_k=top_k,
    )
    results: list[SearchResult] = []
    for raw_score, raw_index in zip(scores[0], indices[0], strict=True):
        index = int(raw_index)
        score = max(-1.0, min(1.0, float(raw_score)))
        if index < 0 or index >= len(store.chunks):
            continue
        if min_score is not None and score < float(min_score):
            continue
        results.append(
            SearchResult(
                rank=len(results) + 1,
                index=index,
                score=score,
                chunk=store.chunks[index],
            )
        )
    return results
