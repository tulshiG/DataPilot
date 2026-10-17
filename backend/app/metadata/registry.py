"""
Metadata Layer — Registry
==========================
Central API for reading and writing metadata.  All other modules should go
through this registry instead of directly querying ``ColumnMetadata`` /
``TableMetadata`` — it encapsulates the DB queries and provides convenience
helpers like ``get_context_for_table()`` which returns a pre-formatted
summary suitable for LLM prompts.

Populating metadata:
    ``populate_metadata_for_dataset()`` is called during ETL after profiling
    and NLP index building.  It reads the existing ``profile_json["nlp_index"]``
    and writes structured ``ColumnMetadata`` + ``TableMetadata`` rows.
"""

import logging
from sqlalchemy.orm import Session
import pandas as pd

from app.models.dataset import Dataset
from app.metadata.models import ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)

# Heuristics for classifying column semantic types.
_SEMANTIC_TYPE_RULES = {
    "identifier": lambda col, dtype, distinct_ratio: (
        "id" in col.lower() or col.lower().endswith("_id")
        or col.lower() in ("id", "key", "code", "sku")
        or (distinct_ratio > 0.95 and "int" in dtype.lower())
    ),
    "temporal": lambda col, dtype, _: (
        "datetime" in dtype.lower() or "timestamp" in dtype.lower()
        or any(kw in col.lower() for kw in ["date", "time", "created", "updated", "period"])
    ),
    "geographic": lambda col, dtype, _: (
        any(kw in col.lower() for kw in ["city", "state", "country", "region", "zip", "postal", "address", "location"])
    ),
    "currency": lambda col, dtype, _: (
        any(kw in col.lower() for kw in ["price", "amount", "revenue", "cost", "salary", "income", "total", "payment", "fee"])
        and "float" in dtype.lower() or "int" in dtype.lower()
    ),
    "percentage": lambda col, dtype, _: (
        any(kw in col.lower() for kw in ["percent", "rate", "ratio", "pct"])
    ),
    "categorical": lambda col, dtype, distinct_ratio: (
        ("object" in dtype.lower() or "str" in dtype.lower())
        and distinct_ratio < 0.5
    ),
    "numeric_measure": lambda col, dtype, distinct_ratio: (
        ("float" in dtype.lower() or "int" in dtype.lower())
        and "id" not in col.lower()
        and distinct_ratio < 0.95
    ),
}


def _classify_semantic_type(col_name: str, dtype: str, distinct_count: int, row_count: int) -> str:
    """Classify a column's semantic type using heuristic rules."""
    distinct_ratio = distinct_count / max(row_count, 1)
    for stype, rule_fn in _SEMANTIC_TYPE_RULES.items():
        try:
            if rule_fn(col_name, dtype, distinct_ratio):
                return stype
        except Exception:
            continue
    return "unknown"


def _compute_quality_score(null_pct: float, distinct_count: int, row_count: int) -> float:
    """Compute a 0-100 quality score based on completeness and uniqueness."""
    completeness = max(0, 100 - null_pct)          # 0% null = 100 points
    diversity = min(100, (distinct_count / max(row_count, 1)) * 200)  # high diversity = good
    return round(completeness * 0.7 + diversity * 0.3, 1)


def populate_metadata_for_dataset(db: Session, dataset_id: int):
    """
    Read the dataset's profile_json and nlp_index, populate ColumnMetadata
    and TableMetadata rows.  Idempotent — deletes existing rows first.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.profile_json:
        logger.warning(f"Dataset {dataset_id} has no profile — skipping metadata population")
        return

    nlp_index = dataset.profile_json.get("nlp_index", {})
    if not nlp_index:
        return

    workspace_id = dataset.workspace_id
    table_name = dataset.cleaned_table_name or ""
    row_count = dataset.row_count or 0

    # ---- Clear existing metadata for this dataset ----
    db.query(ColumnMetadata).filter(ColumnMetadata.dataset_id == dataset_id).delete()
    db.query(TableMetadata).filter(TableMetadata.dataset_id == dataset_id).delete()

    # ---- Table metadata ----
    columns = nlp_index.get("columns", [])
    table_meta = TableMetadata(
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        table_name=table_name,
        original_filename=dataset.original_filename,
        row_count=row_count,
        column_count=len(columns),
        description=f"Dataset '{dataset.original_filename}' with {row_count} rows and {len(columns)} columns.",
    )
    db.add(table_meta)

    # ---- Column metadata ----
    column_types = nlp_index.get("column_types", {})
    null_percentages = nlp_index.get("null_percentage", {})
    distinct_counts = nlp_index.get("distinct_count", {})
    min_max = nlp_index.get("min_max", {})
    sample_values_map = nlp_index.get("sample_values", {})
    synonyms_map = nlp_index.get("synonyms", {})
    numeric_cols = set(nlp_index.get("numeric_columns", []))
    date_cols = set(nlp_index.get("date_columns", []))

    for col in columns:
        dtype = column_types.get(col, "unknown")
        null_pct = null_percentages.get(col, 0.0)
        dist_count = distinct_counts.get(col, 0)
        mm = min_max.get(col, {})
        samples = sample_values_map.get(col, [])
        syns = synonyms_map.get(col, [])

        semantic_type = _classify_semantic_type(col, dtype, dist_count, row_count)

        col_meta = ColumnMetadata(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            table_name=table_name,
            column_name=col,
            data_type=dtype,
            semantic_type=semantic_type,
            is_metric=col in numeric_cols and semantic_type not in ("identifier",),
            is_dimension=semantic_type in ("categorical", "geographic"),
            is_identifier=semantic_type == "identifier",
            is_temporal=col in date_cols or semantic_type == "temporal",
            distinct_count=dist_count,
            null_percentage=null_pct,
            min_value=str(mm.get("min")) if mm.get("min") is not None else None,
            max_value=str(mm.get("max")) if mm.get("max") is not None else None,
            sample_values=samples[:5],
            synonyms=syns if syns else None,
            quality_score=_compute_quality_score(null_pct, dist_count, row_count),
        )
        db.add(col_meta)

    db.commit()
    logger.info(f"Populated metadata for dataset {dataset_id}: {len(columns)} columns, table '{table_name}'")


def get_table_context(db: Session, table_name: str) -> dict:
    """
    Get full context for a table — used by RAG and Query Planner.

    Returns dict with table info + list of column details, ready to be
    formatted into an LLM prompt or used by the query engine.
    """
    table = db.query(TableMetadata).filter(TableMetadata.table_name == table_name).first()
    if not table:
        return {}

    columns = db.query(ColumnMetadata).filter(
        ColumnMetadata.table_name == table_name
    ).order_by(ColumnMetadata.id).all()

    return {
        "table_name": table.table_name,
        "original_filename": table.original_filename,
        "row_count": table.row_count,
        "column_count": table.column_count,
        "domain": table.domain,
        "description": table.description,
        "columns": [
            {
                "name": c.column_name,
                "type": c.data_type,
                "semantic_type": c.semantic_type,
                "is_metric": c.is_metric,
                "is_dimension": c.is_dimension,
                "is_temporal": c.is_temporal,
                "is_identifier": c.is_identifier,
                "description": c.description,
                "synonyms": c.synonyms,
                "sample_values": c.sample_values,
                "null_percentage": c.null_percentage,
                "distinct_count": c.distinct_count,
            }
            for c in columns
        ],
    }


def get_workspace_tables(db: Session, workspace_id: int) -> list[dict]:
    """List all tables in a workspace with summary info."""
    tables = db.query(TableMetadata).filter(
        TableMetadata.workspace_id == workspace_id
    ).all()

    return [
        {
            "table_name": t.table_name,
            "original_filename": t.original_filename,
            "row_count": t.row_count,
            "column_count": t.column_count,
            "domain": t.domain,
        }
        for t in tables
    ]


def get_metrics_for_workspace(db: Session, workspace_id: int) -> list[dict]:
    """Get all metric columns across all datasets in a workspace."""
    metrics = db.query(ColumnMetadata).filter(
        ColumnMetadata.workspace_id == workspace_id,
        ColumnMetadata.is_metric == True,
    ).all()

    return [
        {
            "table": m.table_name,
            "column": m.column_name,
            "type": m.data_type,
            "semantic_type": m.semantic_type,
            "synonyms": m.synonyms,
            "description": m.description,
        }
        for m in metrics
    ]


def get_dimensions_for_workspace(db: Session, workspace_id: int) -> list[dict]:
    """Get all dimension columns across all datasets in a workspace."""
    dims = db.query(ColumnMetadata).filter(
        ColumnMetadata.workspace_id == workspace_id,
        ColumnMetadata.is_dimension == True,
    ).all()

    return [
        {
            "table": d.table_name,
            "column": d.column_name,
            "semantic_type": d.semantic_type,
            "synonyms": d.synonyms,
            "distinct_count": d.distinct_count,
            "sample_values": d.sample_values,
        }
        for d in dims
    ]
