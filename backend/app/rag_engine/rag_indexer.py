"""
RAG Engine — Indexer
=====================
Embeds RAG chunks into a dedicated FAISS index for retrieval.

Called during ETL after chunk_builder has produced the text chunks.
Rebuilds the entire workspace RAG index each time (idempotent).
"""

import logging
from sqlalchemy.orm import Session

from app.rag_engine.chunk_builder import build_chunks_for_workspace
from app.vector_engine.embedding_service import embed_texts
from app.vector_engine.faiss_store import get_store

logger = logging.getLogger(__name__)

RAG_INDEX_NAME = "rag_chunks_ws_{workspace_id}"


def build_rag_index(db: Session, workspace_id: int):
    """
    Build (or rebuild) the RAG index for a workspace.

    Steps:
        1. Build text chunks from all workspace metadata
        2. Embed all chunk texts
        3. Store in a dedicated FAISS index
    """
    # Clear existing index
    store = get_store(RAG_INDEX_NAME.format(workspace_id=workspace_id))
    store.clear()

    # Build chunks
    chunks = build_chunks_for_workspace(db, workspace_id)
    if not chunks:
        logger.info(f"No RAG chunks to index for workspace {workspace_id}")
        return

    # Embed
    texts = [c["text"] for c in chunks]
    metadata = [
        {k: v for k, v in c.items() if k != "text"}
        | {"text": c["text"][:500]}  # truncate text in metadata to save space
        for c in chunks
    ]

    vectors = embed_texts(texts)

    # Store
    store = get_store(RAG_INDEX_NAME.format(workspace_id=workspace_id))
    store.add(vectors, metadata)
    store.save()

    logger.info(
        f"RAG index built for workspace {workspace_id}: "
        f"{len(chunks)} chunks indexed"
    )
