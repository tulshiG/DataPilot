import pandas as pd
import re

DATE_COLUMN_HINTS = ["date", "time", "created", "updated", "dob", "timestamp", "day", "month", "year"]

def detect_date_columns(df: pd.DataFrame) -> list[str]:
    """
    Detect likely date columns using two signals:
    1. Column name hints (e.g. 'order_date', 'created_at')
    2. Sample value parsing success rate
    """
    candidates = []

    for col in df.columns:
        name_hint = any(hint in col.lower() for hint in DATE_COLUMN_HINTS)

        if df[col].dtype == "object":
            sample = df[col].dropna().astype(str).head(20)
            if len(sample) == 0:
                continue
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=False)
            success_rate = parsed.notnull().mean()

            if name_hint or success_rate >= 0.8:
                candidates.append(col)

    return candidates


def convert_data_types(df: pd.DataFrame, date_columns: list[str] | None = None) -> pd.DataFrame:
    """
    Convert columns to appropriate types:
    - Detected date columns -> datetime
    - Numeric-looking object columns -> int/float
    - Low-cardinality text columns -> category
    """
    df = df.copy()
    date_columns = date_columns or []

    for col in df.columns:
        if col in date_columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=False)
            continue

        # if df[col].dtype == "object":
        if df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col]):
            # Try numeric conversion first
            converted = pd.to_numeric(df[col], errors="coerce")
            non_null_original = df[col].notnull().sum()
            non_null_converted = converted.notnull().sum()

            if non_null_original > 0 and (non_null_converted / non_null_original) >= 0.9:
                df[col] = converted
                continue

            # Convert low-cardinality text to string instead of category (category causes issues with some Postgres inserts)
            unique_ratio = df[col].nunique() / max(len(df), 1)
            if unique_ratio < 0.5 and df[col].nunique() < 100:
                df[col] = df[col].astype("string")

    return df