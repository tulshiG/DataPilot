import re
import pandas as pd

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names:
    - lowercase
    - strip whitespace
    - replace spaces/special chars with underscores
    - remove duplicate underscores
    - ensure uniqueness if collisions occur
    """
    df = df.copy()
    new_columns = []
    seen = {}

    for col in df.columns:
        clean = str(col).strip().lower()
        clean = re.sub(r"[^\w\s]", "", clean)      # remove special chars
        clean = re.sub(r"\s+", "_", clean)          # spaces -> underscore
        clean = re.sub(r"_+", "_", clean).strip("_")  # collapse underscores
        if not clean:
            clean = "column"

        if clean in seen:
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 0

        new_columns.append(clean)

    df.columns = new_columns
    return df


def normalize_text_values(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string/object columns for consistency."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
    return df