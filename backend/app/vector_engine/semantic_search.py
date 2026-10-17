"""
Vector Engine — Semantic Search
================================
Query-time semantic search over schema metadata and categorical values.

Replaces the current approach in ``dataset_resolver.py`` (fuzzy string matching
with rapidfuzz) and ``entity_extractor.py`` (value_dictionary substring lookup)
with embedding-based similarity search.

Example:
    # Find which column/table "revenue" refers to
    results = search_schema(workspace_id=1, query="revenue")
    # → [{"score": 0.92, "type": "column", "table": "orders",
    #      "column": "total_amount", "text": "Column 'total amount' ... Also known as: revenue, sales, ..."}]

    # Find which column contains "Bangalore"
    results = search_values(workspace_id=1, query="Bangalore")
    # → [{"score": 0.88, "type": "value", "value": "bangalore",
    #      "columns": ["city"], "table": "orders"}]
"""

import logging

from app.vector_engine.embedding_service import embed_single
from app.vector_engine.faiss_store import get_store
from app.vector_engine.schema_embedder import SCHEMA_INDEX_NAME, VALUE_INDEX_NAME

logger = logging.getLogger(__name__)


def search_schema(workspace_id: int, query: str, k: int = 10) -> list[dict]:
    """
    Semantic search over table/column metadata.

    Parameters
    ----------
    workspace_id : int
        Workspace to search within.
    query : str
        User's search term (e.g., "revenue", "customer name", "order date").
    k : int
        Number of results to return.

    Returns
    -------
    list[dict]
        Ranked results with score, type (table/column), table, column, text.
    """
    store = get_store(SCHEMA_INDEX_NAME.format(workspace_id=workspace_id))
    if store.count == 0:
        logger.debug(f"Schema index is empty for workspace {workspace_id}")
        return []

    query_vec = embed_single(query)
    return store.search(query_vec, k=k)


def search_values(workspace_id: int, query: str, k: int = 10) -> list[dict]:
    """
    Semantic search over indexed categorical values.

    Parameters
    ----------
    workspace_id : int
        Workspace to search within.
    query : str
        Entity/value to search for (e.g., "Mumbai", "Electronics").
    k : int
        Number of results to return.

    Returns
    -------
    list[dict]
        Ranked results with score, value, columns, table, dataset_id.
    """
    store = get_store(VALUE_INDEX_NAME.format(workspace_id=workspace_id))
    if store.count == 0:
        logger.debug(f"Value index is empty for workspace {workspace_id}")
        return []

    query_vec = embed_single(query)
    return store.search(query_vec, k=k)


def search_all(workspace_id: int, query: str, k: int = 10) -> dict:
    """
    Combined search over both schema and value indexes.

    Returns
    -------
    dict with keys:
        "schema_results" : list[dict] — top K schema matches
        "value_results"  : list[dict] — top K value matches
    """
    return {
        "schema_results": search_schema(workspace_id, query, k=k),
        "value_results": search_values(workspace_id, query, k=k),
    }
