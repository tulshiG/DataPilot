"""
Vector Engine — Schema Embedder
================================
Runs during ETL (after ``build_nlp_index``) to embed every table, column,
synonym, and categorical value into the FAISS store.  This powers:

    • Semantic dataset resolution  (replaces fuzzy ``dataset_resolver.py``)
    • Value-level semantic search  (replaces ``value_dictionary`` substring match)
    • RAG context retrieval        (finding relevant schema context for LLM prompts)

Each embedded item carries metadata so search results can be traced back to
the exact table, column, and data type they came from.
"""

import logging
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.vector_engine.embedding_service import embed_texts
from app.vector_engine.faiss_store import get_store

logger = logging.getLogger(__name__)

# Name of the FAISS index that holds all schema embeddings for a workspace.
SCHEMA_INDEX_NAME = "schema_embeddings_ws_{workspace_id}"
VALUE_INDEX_NAME = "value_embeddings_ws_{workspace_id}"


def embed_dataset_schema(db: Session, dataset_id: int):
    """
    Generate and store embeddings for a single dataset's schema metadata.

    Called during ETL after ``build_nlp_index()`` so that the nlp_index
    JSON is already available in ``dataset.profile_json``.

    Embeds:
        • Table name + filename (how users refer to the dataset)
        • Each column name + its synonyms
        • Each categorical value (low cardinality only — up to 200 unique values)
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.profile_json:
        logger.warning(f"Dataset {dataset_id} has no profile_json — skipping schema embedding")
        return

    nlp_index = dataset.profile_json.get("nlp_index")
    if not nlp_index:
        logger.warning(f"Dataset {dataset_id} has no nlp_index — skipping schema embedding")
        return

    workspace_id = dataset.workspace_id
    table_name = dataset.cleaned_table_name or ""
    original_name = dataset.original_filename or ""

    # ---- Collect texts + metadata for schema embeddings ----
    schema_texts: list[str] = []
    schema_meta: list[dict] = []

    # 1) Table-level embedding
    table_text = f"Table: {table_name}. File: {original_name.rsplit('.', 1)[0]}"
    schema_texts.append(table_text)
    schema_meta.append({
        "type": "table",
        "table": table_name,
        "dataset_id": dataset_id,
        "text": table_text,
    })

    # 2) Column-level embeddings (name + synonyms combined)
    columns = nlp_index.get("columns", [])
    synonyms_map = nlp_index.get("synonyms", {})
    column_types = nlp_index.get("column_types", {})
    sample_values = nlp_index.get("sample_values", {})

    for col in columns:
        col_clean = col.replace("_", " ")
        syns = synonyms_map.get(col, [])
        dtype = column_types.get(col, "unknown")
        samples = sample_values.get(col, [])
        samples_str = ", ".join(str(s) for s in samples[:5])

        col_text = f"Column '{col_clean}' in table '{table_name}'. Type: {dtype}."
        if syns:
            col_text += f" Also known as: {', '.join(syns)}."
        if samples_str:
            col_text += f" Sample values: {samples_str}."

        schema_texts.append(col_text)
        schema_meta.append({
            "type": "column",
            "table": table_name,
            "column": col,
            "dtype": dtype,
            "dataset_id": dataset_id,
            "text": col_text,
        })

    # 3) Embed schema texts
    if schema_texts:
        store = get_store(SCHEMA_INDEX_NAME.format(workspace_id=workspace_id))
        vectors = embed_texts(schema_texts)
        store.add(vectors, schema_meta)
        store.save()
        logger.info(
            f"Embedded {len(schema_texts)} schema items for dataset {dataset_id} "
            f"(table={table_name})"
        )

    # ---- Collect texts + metadata for value embeddings ----
    value_dict = nlp_index.get("value_dictionary") or nlp_index.get("Value Dictionary") or {}
    value_texts: list[str] = []
    value_meta: list[dict] = []

    for val_str, val_columns in value_dict.items():
        if not isinstance(val_str, str) or len(val_str) < 2:
            continue
        # Embed each unique value once, referencing all columns it appears in.
        value_texts.append(val_str)
        value_meta.append({
            "type": "value",
            "value": val_str,
            "columns": val_columns if isinstance(val_columns, list) else [val_columns],
            "table": table_name,
            "dataset_id": dataset_id,
        })

    if value_texts:
        vstore = get_store(VALUE_INDEX_NAME.format(workspace_id=workspace_id))
        vvectors = embed_texts(value_texts)
        vstore.add(vvectors, value_meta)
        vstore.save()
        logger.info(
            f"Embedded {len(value_texts)} categorical values for dataset {dataset_id}"
        )


def clear_workspace_embeddings(workspace_id: int):
    """Remove all schema + value embeddings for a workspace (e.g. before full re-index)."""
    get_store(SCHEMA_INDEX_NAME.format(workspace_id=workspace_id)).clear()
    get_store(VALUE_INDEX_NAME.format(workspace_id=workspace_id)).clear()
    logger.info(f"Cleared all embeddings for workspace {workspace_id}")
