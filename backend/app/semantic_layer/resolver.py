"""
Semantic Layer — Resolver
==========================
Resolves metric and dimension references from natural language queries
to their exact SQL expressions.

This is the core abstraction that lets users say "show me revenue by region"
and get ``SELECT region, SUM("amount") FROM sales GROUP BY region`` — without
the LLM or NLP pipeline needing to know the exact column name.
"""

import logging
from difflib import SequenceMatcher
from sqlalchemy.orm import Session

from app.semantic_layer.models import SemanticMetric, SemanticDimension

logger = logging.getLogger(__name__)


def resolve_metric(
    db: Session,
    workspace_id: int,
    query_term: str,
    table_name: str | None = None,
) -> SemanticMetric | None:
    """
    Resolve a query term to a semantic metric.

    Matching strategy (in order):
        1. Exact key match
        2. Exact name match (case-insensitive)
        3. Synonym match
        4. Fuzzy match (80% threshold)

    Parameters
    ----------
    query_term : str
        The term to resolve (e.g., "revenue", "total sales", "avg price")
    table_name : str, optional
        If given, prefer metrics from this table.
    """
    query_lower = query_term.lower().strip()

    metrics = db.query(SemanticMetric).filter(
        SemanticMetric.workspace_id == workspace_id,
        SemanticMetric.is_active == True,
    ).all()

    if not metrics:
        return None

    # 1. Exact key match
    for m in metrics:
        if m.key == query_lower:
            if table_name is None or m.table_name == table_name:
                return m

    # 2. Exact name match (case-insensitive)
    for m in metrics:
        if m.name.lower() == query_lower:
            if table_name is None or m.table_name == table_name:
                return m

    # 3. Synonym match
    for m in metrics:
        synonyms = m.synonyms or []
        for syn in synonyms:
            if syn.lower() == query_lower:
                if table_name is None or m.table_name == table_name:
                    return m

    # 4. Fuzzy match
    best_match = None
    best_score = 0.0
    for m in metrics:
        candidates = [m.key, m.name.lower()] + [s.lower() for s in (m.synonyms or [])]
        for candidate in candidates:
            score = SequenceMatcher(None, query_lower, candidate).ratio()
            if score > best_score and score >= 0.80:
                if table_name is None or m.table_name == table_name:
                    best_score = score
                    best_match = m

    return best_match


def resolve_dimension(
    db: Session,
    workspace_id: int,
    query_term: str,
    table_name: str | None = None,
) -> SemanticDimension | None:
    """Resolve a query term to a semantic dimension (same logic as metric matching)."""
    query_lower = query_term.lower().strip()

    dims = db.query(SemanticDimension).filter(
        SemanticDimension.workspace_id == workspace_id,
        SemanticDimension.is_active == True,
    ).all()

    if not dims:
        return None

    # 1. Exact key/name match
    for d in dims:
        if d.key == query_lower or d.name.lower() == query_lower:
            if table_name is None or d.table_name == table_name:
                return d

    # 2. Synonym match
    for d in dims:
        for syn in (d.synonyms or []):
            if syn.lower() == query_lower:
                if table_name is None or d.table_name == table_name:
                    return d

    # 3. Fuzzy
    best_match = None
    best_score = 0.0
    for d in dims:
        candidates = [d.key, d.name.lower(), d.column_name.lower()] + [s.lower() for s in (d.synonyms or [])]
        for candidate in candidates:
            score = SequenceMatcher(None, query_lower, candidate).ratio()
            if score > best_score and score >= 0.80:
                if table_name is None or d.table_name == table_name:
                    best_score = score
                    best_match = d

    return best_match


def get_all_metrics(db: Session, workspace_id: int) -> list[dict]:
    """Get all active metrics for a workspace."""
    metrics = db.query(SemanticMetric).filter(
        SemanticMetric.workspace_id == workspace_id,
        SemanticMetric.is_active == True,
    ).all()

    return [
        {
            "key": m.key,
            "name": m.name,
            "expression": m.expression,
            "aggregation": m.aggregation,
            "table": m.table_name,
            "column": m.column_name,
            "type": m.data_type,
            "unit": m.unit,
            "synonyms": m.synonyms or [],
            "confidence": m.confidence,
        }
        for m in metrics
    ]


def get_all_dimensions(db: Session, workspace_id: int) -> list[dict]:
    """Get all active dimensions for a workspace."""
    dims = db.query(SemanticDimension).filter(
        SemanticDimension.workspace_id == workspace_id,
        SemanticDimension.is_active == True,
    ).all()

    return [
        {
            "key": d.key,
            "name": d.name,
            "table": d.table_name,
            "column": d.column_name,
            "distinct_count": d.distinct_count,
            "synonyms": d.synonyms or [],
        }
        for d in dims
    ]
