import pandas as pd
from sqlalchemy import create_engine, text
from app.core.config import settings

def detect_primary_key(df: pd.DataFrame) -> dict:
    """
    Detect the most likely primary key column(s).
    Heuristics:
    - Column is fully unique (no duplicates)
    - Column has no nulls
    - Prefer columns with 'id' in the name
    - Prefer integer/string ID-like columns over floats
    """
    candidates = []

    for col in df.columns:
        series = df[col]
        if series.isnull().any():
            continue

        is_unique = series.nunique() == len(df)
        if not is_unique:
            continue

        score = 0
        col_lower = col.lower()
        if col_lower == "id":
            score += 50
        elif col_lower.endswith("_id") or col_lower.endswith("id"):
            score += 30
        elif "key" in col_lower or "code" in col_lower:
            score += 15

        if pd.api.types.is_integer_dtype(series):
            score += 10
        elif pd.api.types.is_string_dtype(series) or series.dtype == "object":
            score += 5

        candidates.append({"column": col, "score": score})

    if not candidates:
        return {"primary_key": None, "confidence": "none"}

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]
    confidence = "high" if best["score"] >= 30 else "medium" if best["score"] > 0 else "low"

    return {"primary_key": best["column"], "confidence": confidence, "candidates": candidates}


def detect_foreign_keys(
    source_df: pd.DataFrame,
    source_name: str,
    other_datasets: list[dict],  # [{"name": str, "df": pd.DataFrame, "primary_key": str}]
) -> list[dict]:
    """
    Find columns in source_df that likely reference another dataset's primary key.
    Heuristics:
    - Column name matches or resembles another dataset's PK name (e.g. 'customer_id' -> 'customers.id')
    - Value overlap: a high percentage of source values exist in the target PK column
    """
    foreign_keys = []

    for col in source_df.columns:
        col_lower = col.lower()
        if not (col_lower.endswith("_id") or col_lower.endswith("id")):
            continue

        for target in other_datasets:
            if target["name"] == source_name or not target.get("primary_key"):
                continue

            target_df = target["df"]
            target_pk = target["primary_key"]

            # Name similarity check: 'customer_id' relates to 'customers' table
            name_stub = col_lower.replace("_id", "").replace("id", "")
            table_stub = target["name"].lower().rstrip("s")
            name_match = name_stub in table_stub or table_stub in name_stub

            # Value overlap check
            try:
                source_values = set(source_df[col].dropna().unique())
                target_values = set(target_df[target_pk].dropna().unique())
                if not source_values:
                    continue
                overlap = len(source_values & target_values) / len(source_values)
            except Exception:
                overlap = 0

            if name_match or overlap >= 0.7:
                foreign_keys.append({
                    "source_column": col,
                    "target_dataset": target["name"],
                    "target_column": target_pk,
                    "match_confidence": "high" if (name_match and overlap >= 0.7) else
                                        "medium" if (name_match or overlap >= 0.7) else "low",
                    "value_overlap_percent": round(overlap * 100, 1),
                })

    return foreign_keys