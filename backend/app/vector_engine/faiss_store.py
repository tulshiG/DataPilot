"""
Vector Engine — FAISS Store
============================
Manages named FAISS indexes on disk with metadata sidecar files.

Each index stores dense vectors + a parallel metadata list that maps each
vector back to its source (table name, column name, chunk text, etc.).
Indexes are saved to / loaded from ``data/vector_indexes/<name>/``.

Why FAISS over pgvector (for now):
    • In-process — no extra service to run.
    • Faster for small-to-medium workloads (< 1 M vectors).
    • Can migrate to pgvector later by swapping this file.

Inputs:
    • vectors (np.ndarray)  — embeddings to store.
    • metadata (list[dict]) — one dict per vector with source information.

Outputs:
    • Top-K nearest neighbors with metadata and similarity scores.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Where indexes are persisted on disk.
_DEFAULT_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "vector_indexes"
)
INDEX_DIR = os.environ.get("DATAPILOT_VECTOR_INDEX_DIR", _DEFAULT_INDEX_DIR)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


class FAISSStore:
    """
    A named FAISS index with JSON metadata sidecar.

    Usage:
        store = FAISSStore("schema_embeddings", dimension=384)
        store.add(vectors, metadata_list)
        results = store.search(query_vector, k=5)
        store.save()
    """

    def __init__(self, name: str, dimension: int = 384):
        self.name = name
        self.dimension = dimension
        self._index = None          # faiss.IndexFlatIP (inner-product = cosine on L2-normed vectors)
        self._metadata: list[dict] = []
        self._index_path = os.path.join(INDEX_DIR, name)
        self._loaded = False

    # ------------------------------------------------------------------
    # Lazy import so FAISS is only required when actually used.
    # ------------------------------------------------------------------
    @staticmethod
    def _faiss():
        import faiss
        return faiss

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------
    def _ensure_index(self):
        """Create or load the FAISS index."""
        if self._index is not None:
            return

        faiss = self._faiss()

        # Try to load from disk first.
        idx_file = os.path.join(self._index_path, "index.faiss")
        meta_file = os.path.join(self._index_path, "metadata.json")

        if os.path.exists(idx_file) and os.path.exists(meta_file):
            try:
                self._index = faiss.read_index(idx_file)
                with open(meta_file, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                self._loaded = True
                logger.info(
                    f"Loaded FAISS index '{self.name}': "
                    f"{self._index.ntotal} vectors, {len(self._metadata)} metadata entries"
                )
                return
            except Exception as e:
                logger.warning(f"Failed to load existing index '{self.name}': {e}")

        # Create a new empty index (Inner Product = cosine similarity on L2-normed vecs).
        self._index = faiss.IndexFlatIP(self.dimension)
        self._metadata = []
        logger.info(f"Created new FAISS index '{self.name}' (dim={self.dimension})")

    def add(self, vectors: np.ndarray, metadata: list[dict]):
        """
        Add vectors with associated metadata to the index.

        Parameters
        ----------
        vectors : np.ndarray, shape (N, dim)
            L2-normalized embeddings.
        metadata : list[dict]
            One metadata dict per vector (must have same length as vectors).
        """
        self._ensure_index()

        if len(vectors) != len(metadata):
            raise ValueError(
                f"vectors ({len(vectors)}) and metadata ({len(metadata)}) must have the same length"
            )
        if vectors.ndim != 2 or vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Expected vectors of shape (N, {self.dimension}), got {vectors.shape}"
            )

        self._index.add(vectors.astype(np.float32))
        self._metadata.extend(metadata)
        logger.debug(f"Added {len(vectors)} vectors to '{self.name}' (total: {self._index.ntotal})")

    def search(self, query_vector: np.ndarray, k: int = 5) -> list[dict]:
        """
        Search for the top-K nearest neighbors of a query vector.

        Parameters
        ----------
        query_vector : np.ndarray, shape (dim,) or (1, dim)
            L2-normalized query embedding.
        k : int
            Number of results to return.

        Returns
        -------
        list[dict]
            Each dict has: ``score`` (float, cosine similarity), plus all
            keys from the stored metadata for that vector.
        """
        self._ensure_index()

        if self._index.ntotal == 0:
            return []

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        actual_k = min(k, self._index.ntotal)
        scores, indices = self._index.search(query_vector.astype(np.float32), actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue  # FAISS returns -1 for unfilled slots
            meta = self._metadata[idx] if idx < len(self._metadata) else {}
            results.append({"score": float(score), **meta})

        return results

    def save(self):
        """Persist the index and metadata to disk."""
        self._ensure_index()
        faiss = self._faiss()

        _ensure_dir(self._index_path)
        idx_file = os.path.join(self._index_path, "index.faiss")
        meta_file = os.path.join(self._index_path, "metadata.json")

        faiss.write_index(self._index, idx_file)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False)

        logger.info(
            f"Saved FAISS index '{self.name}': "
            f"{self._index.ntotal} vectors → {idx_file}"
        )

    def clear(self):
        """Remove all vectors and metadata (in-memory + on disk)."""
        self._index = None
        self._metadata = []
        if os.path.exists(self._index_path):
            shutil.rmtree(self._index_path)
        logger.info(f"Cleared FAISS index '{self.name}'")

    @property
    def count(self) -> int:
        self._ensure_index()
        return self._index.ntotal


# ---------------------------------------------------------------------------
# Module-level convenience — singleton stores by name.
# ---------------------------------------------------------------------------
_stores: dict[str, FAISSStore] = {}


def get_store(name: str, dimension: int = 384) -> FAISSStore:
    """Get or create a named FAISS store (singleton per name)."""
    if name not in _stores:
        _stores[name] = FAISSStore(name, dimension)
    return _stores[name]
