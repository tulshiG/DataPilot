"""
API — AI Engine Status & Semantic Search
==========================================
Endpoints for checking AI engine health, Ollama status, and performing
semantic searches over the indexed metadata.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI Engine"])


@router.get("/status")
def ai_status(current_user: User = Depends(get_current_user)):
    """
    Check the health of all AI subsystems:
    - Ollama LLM availability
    - Embedding model status
    - FAISS index counts
    """
    status = {
        "ollama": _check_ollama(),
        "embeddings": _check_embeddings(),
        "config": {
            "ollama_host": settings.OLLAMA_HOST,
            "ollama_model": settings.OLLAMA_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "rag_top_k": settings.RAG_TOP_K,
        },
    }
    status["overall"] = "operational" if status["ollama"]["available"] else "degraded"
    status["fallback_active"] = not status["ollama"]["available"]
    return status


@router.get("/search/{workspace_id}")
def semantic_search(
    workspace_id: int,
    q: str,
    k: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Perform semantic search over the workspace's indexed metadata.
    Useful for debugging and testing the vector engine.
    """
    try:
        from app.vector_engine.semantic_search import search_all
        results = search_all(workspace_id, q, k=k)
        return {
            "query": q,
            "workspace_id": workspace_id,
            "schema_results": results["schema_results"],
            "value_results": results["value_results"],
        }
    except Exception as e:
        return {"error": str(e), "query": q, "workspace_id": workspace_id}


@router.get("/rag/{workspace_id}")
def rag_context(
    workspace_id: int,
    q: str,
    k: int = 8,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview the RAG context that would be injected into the LLM prompt
    for a given query. Useful for debugging prompt engineering.
    """
    try:
        from app.rag_engine.rag_retriever import retrieve_context
        from app.rag_engine.context_assembler import assemble_context
        chunks = retrieve_context(workspace_id, q, k=k)
        context_text = assemble_context(chunks)
        return {
            "query": q,
            "workspace_id": workspace_id,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "formatted_context": context_text,
        }
    except Exception as e:
        return {"error": str(e), "query": q, "workspace_id": workspace_id}


@router.post("/parse/{workspace_id}")
def parse_query_debug(
    workspace_id: int,
    q: str,
    current_user: User = Depends(get_current_user),
):
    """
    Debug endpoint: parse a query through the LLM semantic parser 
    and return the structured spec WITHOUT executing SQL.
    """
    try:
        from app.llm_engine.semantic_parser import parse_query
        spec = parse_query(q, workspace_id)
        return {
            "query": q,
            "workspace_id": workspace_id,
            "llm_available": spec is not None,
            "spec": spec,
        }
    except Exception as e:
        return {"error": str(e), "query": q, "workspace_id": workspace_id}


@router.get("/metadata/{workspace_id}")
def workspace_metadata(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return structured metadata for all tables in a workspace.
    Shows tables, columns, semantic types, metrics, dimensions.
    """
    try:
        from app.metadata.registry import get_workspace_tables, get_metrics_for_workspace, get_dimensions_for_workspace
        return {
            "workspace_id": workspace_id,
            "tables": get_workspace_tables(db, workspace_id),
            "metrics": get_metrics_for_workspace(db, workspace_id),
            "dimensions": get_dimensions_for_workspace(db, workspace_id),
        }
    except Exception as e:
        return {"error": str(e), "workspace_id": workspace_id}


# --- Internal helpers ---

def _check_ollama() -> dict:
    try:
        from app.llm_engine.ollama_client import is_available, OLLAMA_HOST, OLLAMA_MODEL
        available = is_available()
        return {
            "available": available,
            "host": OLLAMA_HOST,
            "model": OLLAMA_MODEL,
            "message": "Ollama is running" if available else "Ollama is not available. Using keyword fallback.",
        }
    except Exception as e:
        return {"available": False, "error": str(e), "message": "Could not check Ollama status"}


def _check_embeddings() -> dict:
    try:
        from app.vector_engine.embedding_service import get_embedding_dimension, DEFAULT_MODEL_NAME
        dim = get_embedding_dimension()
        return {
            "available": True,
            "model": DEFAULT_MODEL_NAME,
            "dimension": dim,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
