"""
Vector Engine — Embedding Service
=================================
Singleton wrapper around sentence-transformers that generates dense vector
embeddings for text.  Uses `all-MiniLM-L6-v2` (22 M params, 384-dim, runs
on CPU in ~10 ms per embedding).

Why this module exists:
    The current pipeline uses TF-IDF + rapidfuzz for matching user queries to
    dataset/column/value names.  TF-IDF is bag-of-words and can't capture
    semantic similarity ("revenue" ≈ "sales figures" ≈ "income").  Dense
    embeddings encode meaning into vectors where semantically similar concepts
    are close together in cosine space.

Inputs:
    text (str | list[str])  — one or more strings to embed.

Outputs:
    np.ndarray of shape (N, 384) — one 384-dim vector per input string.

Used by:
    • schema_embedder.py  (ETL-time: embed table/column/value metadata)
    • rag_indexer.py       (ETL-time: embed RAG chunks)
    • rag_retriever.py     (query-time: embed user query)
    • semantic_search.py   (query-time: find nearest values)
"""

import logging
import numpy as np
from typing import Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model name — swap this to try a different model without changing any caller.
# all-MiniLM-L6-v2: 22 M params, 384-dim output, CPU ≈ 10 ms/embedding.
# ---------------------------------------------------------------------------
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"

# Module-level singleton — loaded lazily on first call.
_model = None
_model_name: str | None = None


def _get_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _model, _model_name
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model_name = DEFAULT_MODEL_NAME
            logger.info(f"Loading embedding model: {_model_name} ...")
            _model = SentenceTransformer(_model_name)
            logger.info(f"Embedding model loaded successfully (dim={_model.get_sentence_embedding_dimension()})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(
                f"Could not load sentence-transformers model '{DEFAULT_MODEL_NAME}'. "
                f"Make sure 'sentence-transformers' is installed: pip install sentence-transformers"
            ) from e
    return _model


def get_embedding_dimension() -> int:
    """Return the dimensionality of the embedding vectors (384 for MiniLM)."""
    return _get_model().get_sentence_embedding_dimension()


def embed_texts(texts: Union[str, list[str]], *, batch_size: int = 64,
                normalize: bool = True) -> np.ndarray:
    """
    Generate embeddings for one or more text strings.

    Parameters
    ----------
    texts : str or list[str]
        The text(s) to embed.
    batch_size : int
        Batch size for encoding (relevant when texts is a large list).
    normalize : bool
        If True, L2-normalize the vectors (required for cosine similarity
        with FAISS inner-product index).

    Returns
    -------
    np.ndarray
        Shape (N, dim) float32 array of embeddings.
    """
    model = _get_model()

    if isinstance(texts, str):
        texts = [texts]

    if not texts:
        return np.zeros((0, get_embedding_dimension()), dtype=np.float32)

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )

    return embeddings.astype(np.float32)


def embed_single(text: str, *, normalize: bool = True) -> np.ndarray:
    """Convenience wrapper — embed a single string, return shape (dim,)."""
    return embed_texts(text, normalize=normalize)[0]


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors (assumes L2-normalized)."""
    return float(np.dot(vec_a, vec_b))
