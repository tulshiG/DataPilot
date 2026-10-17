from sqlalchemy.orm import Session
from rapidfuzz import fuzz
from app.models.dataset import Dataset

# Relative weight of each signal in the final dataset confidence score
WEIGHTS = {"table": 0.15, "column": 0.30, "value": 0.25, "relationship": 0.10, "metric": 0.20}


def _get_index(ds: Dataset) -> dict | None:
    if not ds.profile_json:
        return None
    return ds.profile_json.get("nlp_index")


def score_dataset(ds: Dataset, tokens: list[str], cleaned_text: str) -> dict:
    """
    Score how likely this dataset is the one the query is asking about,
    using table-name similarity, column/synonym similarity, indexed category
    value matches, relationship connectivity, and metric-column matches.
    """
    index = _get_index(ds)
    if not index:
        return {"dataset_id": ds.id, "name": ds.original_filename, "table_name": ds.cleaned_table_name, "score": 0.0, "breakdown": {}}

    breakdown = {"table": 0.0, "column": 0.0, "value": 0.0, "relationship": 0.0, "metric": 0.0}

    # Table/name similarity
    table_text = ds.original_filename.rsplit(".", 1)[0].lower().replace("_", " ").replace("-", " ")
    breakdown["table"] = max(
        fuzz.partial_ratio(table_text, cleaned_text),
        max((fuzz.ratio(t, table_text) for t in tokens), default=0),
    )

    # Column similarity, including synonym groups from the index
    columns = index.get("columns", [])
    synonyms = index.get("synonyms", {})
    col_scores = []
    for col in columns:
        col_clean = col.lower().replace("_", " ")
        best = fuzz.partial_ratio(col_clean, cleaned_text)
        for syn in synonyms.get(col, []):
            best = max(best, fuzz.partial_ratio(syn, cleaned_text))
        col_scores.append(best)
    breakdown["column"] = max(col_scores) if col_scores else 0.0

    # Value similarity — does the query mention an actual value stored in this dataset?
    # (e.g. "Kentucky", "female", "Electronics")
    # FIX: support both indexer key names for backwards compatibility
    value_dict = index.get("value_dictionary") or index.get("Value Dictionary") or {}
    value_score = 0.0
    for token in tokens:
        tok_lower = token.lower()
        for val in value_dict.keys():
            if not isinstance(val, str):
                continue
            score = fuzz.ratio(tok_lower, val.lower())
            # Boost partial/substring matches
            if tok_lower in val.lower() or val.lower() in tok_lower:
                score = max(score, 85)
            value_score = max(value_score, score)
    breakdown["value"] = value_score

    # Relationship connectivity — small bonus for datasets that participate in
    # a validated relationship graph (more likely to be a "real" queryable entity)
    breakdown["relationship"] = 15.0 if index.get("relationships") else 0.0

    # Metric-column match — does the query mention something like a numeric metric
    # this dataset actually has (revenue, charges, quantity, etc.)?
    numeric_cols = index.get("numeric_columns", [])
    metric_score = 0.0
    for col in numeric_cols:
        col_clean = col.lower().replace("_", " ")
        s = fuzz.partial_ratio(col_clean, cleaned_text)
        for syn in synonyms.get(col, []):
            s = max(s, fuzz.partial_ratio(syn, cleaned_text))
        metric_score = max(metric_score, s)
    breakdown["metric"] = metric_score

    total = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)

    return {
        "dataset_id": ds.id,
        "name": ds.original_filename,
        "table_name": ds.cleaned_table_name,
        "score": round(total, 1),
        "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
    }


def resolve_dataset(
    db: Session, workspace_id: int, tokens: list[str], cleaned_text: str, forced_dataset_id: int | None = None
) -> list[dict]:
    """
    Rank every processed dataset in the workspace by how likely it is to be
    what the query refers to. Returns a sorted list (highest confidence first) —
    never a single guess, so downstream stages can fall back to the 2nd-best
    candidate if the top one fails validation.
    """
    datasets = db.query(Dataset).filter(Dataset.workspace_id == workspace_id, Dataset.is_processed == 1).all()
    if not datasets:
        return []

    if forced_dataset_id:
        datasets = [d for d in datasets if d.id == forced_dataset_id]

    scored = [score_dataset(ds, tokens, cleaned_text) for ds in datasets]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored