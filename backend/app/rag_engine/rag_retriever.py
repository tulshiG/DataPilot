"""
RAG Engine — Retriever
=======================
Query-time retrieval of the most relevant context chunks for a user query.

This is the core RAG mechanism: embed the user's question, search the RAG
FAISS index, return the top-K most relevant chunks that will be injected
into the LLM's system prompt.
"""

import logging

from app.vector_engine.embedding_service import embed_single
from app.vector_engine.faiss_store import get_store
from app.rag_engine.rag_indexer import RAG_INDEX_NAME

logger = logging.getLogger(__name__)


def retrieve_context(workspace_id: int, query: str, k: int = 8,
                     min_score: float = 0.2) -> list[dict]:
    """
    Retrieve the top-K most relevant RAG chunks for a query.

    Parameters
    ----------
    workspace_id : int
        Workspace to search within.
    query : str
        The user's natural language query.
    k : int
        Maximum number of chunks to return.
    min_score : float
        Minimum cosine similarity threshold — chunks below this are filtered out.

    Returns
    -------
    list[dict]
        Each dict has: score, text, type (table_schema/column_detail/etc.),
        source, dataset_id.
    """
    store = get_store(RAG_INDEX_NAME.format(workspace_id=workspace_id))

    if store.count == 0:
        logger.debug(f"RAG index is empty for workspace {workspace_id}")
        return []

    query_vec = embed_single(query)
    results = store.search(query_vec, k=k)

    # Filter by minimum score
    filtered = [r for r in results if r.get("score", 0) >= min_score]

    logger.debug(
        f"RAG retrieval for workspace {workspace_id}: "
        f"query='{query[:60]}...', {len(filtered)}/{len(results)} chunks above threshold {min_score}"
    )

    return filtered
