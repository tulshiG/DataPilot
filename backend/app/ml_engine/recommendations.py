"""
ML Engine — Intelligent Recommendations
==========================================
Context-aware query and analysis recommendations based on:
    • Dataset metadata & semantic types
    • Recent query history patterns
    • Unused but relevant columns
    • Statistical properties of the data

Recommendations help users discover insights they haven't asked for yet.

Types:
    • query_suggestions — "Try asking: what is total revenue by region?"
    • analysis_hints — "Column 'price' has outliers worth investigating"
    • correlation_alerts — "Strong correlation found between price and rating"
    • missing_data_warnings — "Column 'email' has 34% null values"
"""

import logging

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.metadata.models import ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)


def generate_recommendations(
    db: Session,
    workspace_id: int,
    dataset_id: int | None = None,
    max_recommendations: int = 10,
) -> list[dict]:
    """
    Generate intelligent recommendations for a workspace/dataset.

    Returns a list of recommendation dicts, each with:
        type, title, description, priority (1-5), suggested_query
    """
    recommendations = []

    # Get metadata
    filters = {"workspace_id": workspace_id}
    if dataset_id:
        filters["dataset_id"] = dataset_id

    columns = db.query(ColumnMetadata).filter_by(**filters).all()
    tables = db.query(TableMetadata).filter_by(**{
        k: v for k, v in filters.items() if k != "dataset_id"
    }).all()

    if not columns:
        return [_rec(
            "setup", "Upload Data",
            "Upload and process a dataset to get personalized recommendations.",
            5
        )]

    # ── 1. Query suggestions based on metrics & dimensions ──
    recommendations.extend(_suggest_queries(columns, tables))

    # ── 2. Data quality warnings ──
    recommendations.extend(_quality_warnings(columns))

    # ── 3. Relationship suggestions ──
    recommendations.extend(_relationship_suggestions(tables))

    # ── 4. Advanced analysis suggestions ──
    recommendations.extend(_analysis_suggestions(columns, tables))

    # Sort by priority (higher = more important), then deduplicate
    recommendations.sort(key=lambda r: r["priority"], reverse=True)
    seen = set()
    unique = []
    for r in recommendations:
        key = r["title"]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:max_recommendations]


def _suggest_queries(columns, tables) -> list[dict]:
    """Suggest queries based on available metrics and dimensions."""
    recs = []

    metrics = [c for c in columns if c.is_metric]
    dimensions = [c for c in columns if c.is_dimension]
    temporals = [c for c in columns if c.is_temporal]

    # Metric + Dimension combinations
    for metric in metrics[:3]:
        for dim in dimensions[:3]:
            if metric.table_name == dim.table_name:
                m_name = metric.column_name.replace("_", " ")
                d_name = dim.column_name.replace("_", " ")
                recs.append(_rec(
                    "query_suggestion",
                    f"Analyze {m_name} by {d_name}",
                    f"Discover how {m_name} varies across different {d_name} values.",
                    4,
                    f"Show total {m_name} by {d_name}",
                ))

    # Trend analysis suggestions
    for metric in metrics[:2]:
        for time_col in temporals[:1]:
            if metric.table_name == time_col.table_name:
                m_name = metric.column_name.replace("_", " ")
                recs.append(_rec(
                    "query_suggestion",
                    f"{m_name.title()} Trend Analysis",
                    f"See how {m_name} changes over time.",
                    4,
                    f"Show {m_name} trend over time",
                ))

    # Top/Bottom analysis
    for metric in metrics[:2]:
        for dim in dimensions[:2]:
            if metric.table_name == dim.table_name:
                m_name = metric.column_name.replace("_", " ")
                d_name = dim.column_name.replace("_", " ")
                recs.append(_rec(
                    "query_suggestion",
                    f"Top {d_name} by {m_name}",
                    f"Find the highest-performing {d_name} categories.",
                    3,
                    f"Top 10 {d_name} by {m_name}",
                ))

    return recs


def _quality_warnings(columns) -> list[dict]:
    """Generate data quality warnings."""
    recs = []

    for col in columns:
        # High null percentage
        if col.null_percentage and col.null_percentage > 20:
            recs.append(_rec(
                "data_quality",
                f"High Missing Data: {col.column_name}",
                f"Column '{col.column_name}' in '{col.table_name}' has {col.null_percentage:.0f}% missing values. "
                f"Consider imputation or filtering.",
                3 if col.null_percentage < 50 else 4,
            ))

        # Very low cardinality on non-ID columns
        if (col.distinct_count and col.distinct_count == 1
                and not col.is_identifier and col.data_type != "boolean"):
            recs.append(_rec(
                "data_quality",
                f"Constant Column: {col.column_name}",
                f"Column '{col.column_name}' has only 1 unique value — it provides no analytical value.",
                2,
            ))

        # Very high cardinality strings (potential ID columns)
        if (col.data_type in ("object", "string", "varchar")
                and col.distinct_count and col.distinct_count > 1000
                and not col.is_identifier):
            recs.append(_rec(
                "data_quality",
                f"High Cardinality: {col.column_name}",
                f"Column '{col.column_name}' has {col.distinct_count} unique values — might be an identifier, not a dimension.",
                2,
            ))

    return recs


def _relationship_suggestions(tables) -> list[dict]:
    """Suggest cross-table analyses."""
    recs = []

    if len(tables) >= 2:
        recs.append(_rec(
            "analysis_hint",
            "Cross-Dataset Analysis Available",
            f"You have {len(tables)} datasets loaded. Try asking questions that span multiple tables "
            f"to discover cross-dataset insights.",
            3,
        ))

    return recs


def _analysis_suggestions(columns, tables) -> list[dict]:
    """Suggest advanced analysis techniques."""
    recs = []

    metrics = [c for c in columns if c.is_metric]
    dimensions = [c for c in columns if c.is_dimension]
    temporals = [c for c in columns if c.is_temporal]

    # Forecasting suggestion
    if temporals and metrics:
        recs.append(_rec(
            "ml_suggestion",
            "Time-Series Forecasting Available",
            "Your data has temporal patterns. Run forecasting to predict future trends.",
            4,
        ))

    # Segmentation suggestion
    if len(metrics) >= 2 and len(dimensions) >= 1:
        recs.append(_rec(
            "ml_suggestion",
            "Customer Segmentation Possible",
            f"With {len(metrics)} numeric features, K-Means clustering can reveal hidden customer segments.",
            3,
        ))

    # Anomaly detection
    if metrics:
        recs.append(_rec(
            "ml_suggestion",
            "Anomaly Detection Available",
            "Run anomaly detection to find outliers and unusual patterns in your data.",
            3,
        ))

    # Distribution analysis
    for metric in metrics[:2]:
        m_name = metric.column_name.replace("_", " ")
        recs.append(_rec(
            "query_suggestion",
            f"{m_name.title()} Distribution",
            f"View the distribution of {m_name} to understand its spread.",
            2,
            f"Show distribution of {m_name}",
        ))

    return recs


def _rec(
    rec_type: str,
    title: str,
    description: str,
    priority: int,
    suggested_query: str | None = None,
) -> dict:
    """Build a recommendation dict."""
    r = {
        "type": rec_type,
        "title": title,
        "description": description,
        "priority": priority,
    }
    if suggested_query:
        r["suggested_query"] = suggested_query
    return r
