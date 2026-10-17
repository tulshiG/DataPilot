"""
RAG Engine — Chunk Builder
===========================
Converts database metadata, business rules, relationships, and query history
into text chunks suitable for embedding and retrieval.

Each chunk is a self-contained piece of context that, when retrieved, gives
the LLM enough information to correctly interpret a user's query.

Chunk types:
    • table_schema  — table name, columns, types, row count
    • column_detail — individual column with stats, synonyms, sample values
    • business_rule — trigger phrase → metric/entity mapping
    • relationship  — FK relationship between two tables
    • query_history — past successful query → intent/spec mapping
"""

import logging
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.knowledge_base import BusinessMetric, BusinessEntity, BusinessRule
from app.models.relationship import DatasetRelationship
from app.models.query_history import QueryHistory
from app.metadata.registry import get_table_context

logger = logging.getLogger(__name__)


def build_chunks_for_dataset(db: Session, dataset_id: int) -> list[dict]:
    """
    Build all RAG chunks for a single dataset.

    Returns a list of dicts, each with:
        - text: the chunk text to embed
        - type: chunk type (table_schema, column_detail, etc.)
        - source: source identifier (table name, rule id, etc.)
        - dataset_id: originating dataset
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.cleaned_table_name:
        return []

    chunks = []
    table_name = dataset.cleaned_table_name
    workspace_id = dataset.workspace_id

    # ---- 1. Table schema chunk ----
    context = get_table_context(db, table_name)
    if context:
        col_descs = []
        for c in context.get("columns", []):
            desc = f"  - {c['name']} ({c['type']}"
            if c.get("semantic_type"):
                desc += f", {c['semantic_type']}"
            desc += ")"
            if c.get("is_metric"):
                desc += " [METRIC]"
            if c.get("is_dimension"):
                desc += " [DIMENSION]"
            if c.get("is_temporal"):
                desc += " [TEMPORAL]"
            col_descs.append(desc)

        schema_text = (
            f"Table '{table_name}' (from file '{context.get('original_filename', '')}') "
            f"has {context.get('row_count', '?')} rows and {context.get('column_count', '?')} columns:\n"
            + "\n".join(col_descs)
        )
        chunks.append({
            "text": schema_text,
            "type": "table_schema",
            "source": table_name,
            "dataset_id": dataset_id,
        })

    # ---- 2. Column detail chunks (one per column) ----
    if context:
        for c in context.get("columns", []):
            parts = [f"Column '{c['name']}' in table '{table_name}'."]
            parts.append(f"Type: {c['type']}.")
            if c.get("semantic_type"):
                parts.append(f"Semantic type: {c['semantic_type']}.")
            if c.get("synonyms"):
                parts.append(f"Also known as: {', '.join(c['synonyms'])}.")
            if c.get("sample_values"):
                samples = ", ".join(str(v) for v in c["sample_values"][:5])
                parts.append(f"Sample values: {samples}.")
            if c.get("distinct_count") is not None:
                parts.append(f"Distinct values: {c['distinct_count']}.")
            if c.get("null_percentage") is not None:
                parts.append(f"Null: {c['null_percentage']}%.")
            if c.get("description"):
                parts.append(f"Description: {c['description']}.")

            chunks.append({
                "text": " ".join(parts),
                "type": "column_detail",
                "source": f"{table_name}.{c['name']}",
                "dataset_id": dataset_id,
            })

    # ---- 3. Business rule chunks ----
    rules = db.query(BusinessRule).filter(
        BusinessRule.workspace_id == workspace_id
    ).all()
    for rule in rules:
        rule_text = f"Business rule: When user says '{rule.trigger_phrase}'"
        if rule.rule_logic:
            rule_text += f", apply logic: {rule.rule_logic}"
        if rule.description:
            rule_text += f". {rule.description}"
        chunks.append({
            "text": rule_text,
            "type": "business_rule",
            "source": f"rule_{rule.id}",
            "dataset_id": dataset_id,
        })

    # ---- 4. Business metric chunks ----
    metrics = db.query(BusinessMetric).filter(
        BusinessMetric.dataset_id == dataset_id
    ).all()
    for metric in metrics:
        metric_text = (
            f"Business metric '{metric.name}' (key: '{metric.metric_key}'): "
            f"computed as {metric.aggregation.upper()}(\"{metric.column_name}\") "
            f"from table '{table_name}'."
        )
        if metric.formula:
            metric_text += f" Formula: {metric.formula}."
        if metric.description:
            metric_text += f" {metric.description}."
        chunks.append({
            "text": metric_text,
            "type": "business_metric",
            "source": f"metric_{metric.id}",
            "dataset_id": dataset_id,
        })

    # ---- 5. Relationship chunks ----
    rels = db.query(DatasetRelationship).filter(
        (DatasetRelationship.source_dataset_id == dataset_id) |
        (DatasetRelationship.target_dataset_id == dataset_id)
    ).all()
    for rel in rels:
        source_ds = db.query(Dataset).filter(Dataset.id == rel.source_dataset_id).first()
        target_ds = db.query(Dataset).filter(Dataset.id == rel.target_dataset_id).first()
        if source_ds and target_ds:
            rel_text = (
                f"Relationship: {source_ds.cleaned_table_name}.{rel.source_column} → "
                f"{target_ds.cleaned_table_name}.{rel.target_column} "
                f"(confidence: {rel.confidence}"
            )
            if hasattr(rel, "value_overlap_percent") and rel.value_overlap_percent:
                rel_text += f", {rel.value_overlap_percent}% value overlap"
            rel_text += ")"
            if hasattr(rel, "is_validated") and rel.is_validated:
                rel_text += f". Validation status: {rel.is_validated}."
            chunks.append({
                "text": rel_text,
                "type": "relationship",
                "source": f"rel_{rel.id}",
                "dataset_id": dataset_id,
            })

    logger.info(f"Built {len(chunks)} RAG chunks for dataset {dataset_id}")
    return chunks


def build_chunks_for_workspace(db: Session, workspace_id: int) -> list[dict]:
    """Build RAG chunks for ALL datasets in a workspace."""
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
    ).all()

    all_chunks = []
    for ds in datasets:
        all_chunks.extend(build_chunks_for_dataset(db, ds.id))

    # ---- Query history chunks (workspace-wide) ----
    try:
        recent_queries = db.query(QueryHistory).filter(
            QueryHistory.workspace_id == workspace_id,
            QueryHistory.status == "success",
        ).order_by(QueryHistory.created_at.desc()).limit(50).all()

        for qh in recent_queries:
            history_text = (
                f"Past query: \"{qh.raw_query}\" → intent: {qh.detected_intent or 'unknown'}"
            )
            if qh.generated_sql:
                # Include abbreviated SQL (first 200 chars) for context.
                history_text += f". SQL: {qh.generated_sql[:200]}"
            all_chunks.append({
                "text": history_text,
                "type": "query_history",
                "source": f"query_{qh.id}",
                "dataset_id": None,
            })
    except Exception as e:
        logger.debug(f"Could not load query history for RAG: {e}")

    logger.info(f"Built {len(all_chunks)} total RAG chunks for workspace {workspace_id}")
    return all_chunks
