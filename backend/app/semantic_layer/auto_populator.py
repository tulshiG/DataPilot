"""
Semantic Layer — Auto Populator
=================================
Automatically discovers and registers metrics and dimensions from dataset
metadata during ETL.

Heuristics:
    Metrics:
        • Numeric columns → SUM/AVG depending on semantic type
        • Columns named "revenue", "amount", "price", "cost" → SUM
        • Columns named "count", "quantity" → SUM
        • Columns named "rate", "ratio", "percentage" → AVG

    Dimensions:
        • String/categorical columns with reasonable cardinality (<500 distinct)
        • Columns named "category", "type", "status", "region", "city" → dimension
        • Date/time columns → time dimension
"""

import logging
import re
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.metadata.models import ColumnMetadata, TableMetadata
from app.semantic_layer.models import SemanticMetric, SemanticDimension

logger = logging.getLogger(__name__)

# Heuristic patterns for metric detection
_METRIC_PATTERNS = {
    "sum": [
        r"revenue", r"amount", r"price", r"cost", r"total", r"sales",
        r"profit", r"income", r"expense", r"payment", r"fee", r"balance",
        r"value", r"weight", r"quantity", r"qty", r"count",
        r"spend", r"budget", r"discount", r"tax",
    ],
    "avg": [
        r"rate", r"ratio", r"percent", r"average", r"avg",
        r"score", r"rating", r"gpa", r"margin",
    ],
    "count": [
        r"id$", r"_id$", r"number$", r"no$", r"num$",
    ],
}

# Patterns for dimension detection
_DIMENSION_PATTERNS = [
    r"category", r"type", r"status", r"region", r"city", r"state",
    r"country", r"department", r"team", r"group", r"class",
    r"brand", r"vendor", r"supplier", r"customer", r"segment",
    r"channel", r"source", r"medium", r"platform", r"device",
    r"gender", r"age_group", r"tier", r"level", r"grade",
    r"name", r"label", r"tag",
]

# Synonym generation patterns
_SYNONYMS = {
    "revenue": ["sales", "income", "earnings"],
    "amount": ["value", "total"],
    "price": ["cost", "rate", "charge"],
    "quantity": ["qty", "count", "units"],
    "profit": ["margin", "earnings", "net income"],
    "discount": ["rebate", "reduction"],
    "category": ["type", "class", "group"],
    "region": ["area", "territory", "zone"],
    "city": ["town", "municipality"],
    "status": ["state", "condition"],
}


def auto_populate_semantic_layer(db: Session, dataset_id: int):
    """
    Scan a dataset's column metadata and auto-register metrics and dimensions.
    Idempotent — clears existing auto-generated entries before re-populating.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.cleaned_table_name:
        return

    table_name = dataset.cleaned_table_name
    workspace_id = dataset.workspace_id

    # Clear existing auto-generated entries for this dataset
    db.query(SemanticMetric).filter(
        SemanticMetric.dataset_id == dataset_id,
        SemanticMetric.is_auto == True,
    ).delete()

    db.query(SemanticDimension).filter(
        SemanticDimension.dataset_id == dataset_id,
        SemanticDimension.is_auto == True,
    ).delete()

    # Get column metadata
    columns = db.query(ColumnMetadata).filter(
        ColumnMetadata.dataset_id == dataset_id,
    ).all()

    if not columns:
        logger.info(f"No column metadata found for dataset {dataset_id}")
        return

    metrics_created = 0
    dims_created = 0

    for col in columns:
        col_lower = col.column_name.lower()

        # ── Metric detection ──
        if col.is_metric or col.data_type in ("integer", "float", "numeric", "decimal"):
            agg = _detect_aggregation(col_lower, col)
            if agg:
                metric = SemanticMetric(
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    name=_humanize(col.column_name),
                    key=_to_key(col.column_name),
                    description=f"Auto-detected metric: {agg}(\"{col.column_name}\") from {table_name}",
                    expression=f'{agg}("{col.column_name}")',
                    aggregation=agg,
                    table_name=table_name,
                    column_name=col.column_name,
                    data_type=_detect_data_type(col_lower, col),
                    unit=_detect_unit(col_lower, col),
                    synonyms=_generate_synonyms(col_lower),
                    is_auto=True,
                    confidence=0.7 if col.is_metric else 0.5,
                )
                db.add(metric)
                metrics_created += 1

        # ── Dimension detection ──
        if col.is_dimension or _is_dimension_candidate(col):
            dim = SemanticDimension(
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                name=_humanize(col.column_name),
                key=_to_key(col.column_name),
                description=f"Auto-detected dimension from {table_name}",
                table_name=table_name,
                column_name=col.column_name,
                distinct_count=col.distinct_count,
                sample_values=col.sample_values,
                synonyms=_generate_synonyms(col_lower),
                is_auto=True,
            )
            db.add(dim)
            dims_created += 1

        # ── Time dimension detection ──
        if col.is_temporal:
            dim = SemanticDimension(
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                name=f"Time ({_humanize(col.column_name)})",
                key=f"time_{_to_key(col.column_name)}",
                description=f"Time dimension from {table_name}",
                table_name=table_name,
                column_name=col.column_name,
                synonyms=["date", "time", "period", "when"],
                is_auto=True,
            )
            db.add(dim)
            dims_created += 1

    db.commit()
    logger.info(
        f"Semantic layer populated for dataset {dataset_id}: "
        f"{metrics_created} metrics, {dims_created} dimensions"
    )


def _detect_aggregation(col_lower: str, col: ColumnMetadata) -> str | None:
    """Detect the most appropriate aggregation function for a column."""
    for agg, patterns in _METRIC_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, col_lower):
                return agg.upper()

    # Fallback: numeric columns default to SUM
    if col.is_metric:
        return "SUM"
    if col.data_type in ("integer", "float", "numeric", "decimal"):
        return "SUM"

    return None


def _is_dimension_candidate(col: ColumnMetadata) -> bool:
    """Check if a column looks like a dimension."""
    # Already flagged
    if col.is_dimension:
        return True

    # String type with reasonable cardinality
    if col.data_type in ("object", "string", "varchar", "text", "category"):
        if col.distinct_count and col.distinct_count <= 500:
            return True

    # Name matches known dimension patterns
    col_lower = col.column_name.lower()
    for pattern in _DIMENSION_PATTERNS:
        if re.search(pattern, col_lower):
            return True

    return False


def _detect_data_type(col_lower: str, col: ColumnMetadata) -> str:
    """Detect the semantic data type for formatting."""
    if col.semantic_type == "currency" or any(w in col_lower for w in ["price", "cost", "amount", "revenue", "fee"]):
        return "currency"
    if any(w in col_lower for w in ["rate", "percent", "margin", "ratio"]):
        return "percentage"
    if any(w in col_lower for w in ["count", "quantity", "qty", "number"]):
        return "count"
    return "numeric"


def _detect_unit(col_lower: str, col: ColumnMetadata) -> str | None:
    """Detect the unit for a metric."""
    if col.semantic_type == "currency":
        return "USD"  # default, can be overridden
    if any(w in col_lower for w in ["percent", "rate", "margin"]):
        return "%"
    if any(w in col_lower for w in ["weight"]):
        return "kg"
    return None


def _humanize(name: str) -> str:
    """Convert column_name to Human Name."""
    return name.replace("_", " ").replace("-", " ").title()


def _to_key(name: str) -> str:
    """Convert Column Name to column_name key."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _generate_synonyms(col_lower: str) -> list[str]:
    """Generate synonym list for a column."""
    synonyms = []
    for key, syns in _SYNONYMS.items():
        if key in col_lower:
            synonyms.extend(syns)
    return list(set(synonyms))[:5]  # cap at 5
