import pandas as pd
import numpy as np

def profile_dataframe(df: pd.DataFrame) -> dict:
    """Generate summary statistics and structural info for a dataset."""
    profile = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": [],
    }

    for col in df.columns:
        series = df[col]
        col_info = {
            "name": col,
            "dtype": str(series.dtype),
            "null_count": int(series.isnull().sum()),
            "null_percent": round(float(series.isnull().mean() * 100), 2),
            "unique_count": int(series.nunique()),
        }

        if pd.api.types.is_numeric_dtype(series):
            col_info.update({
                "min": _safe_float(series.min()),
                "max": _safe_float(series.max()),
                "mean": _safe_float(series.mean()),
                "std": _safe_float(series.std()),
            })
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_info.update({
                "min_date": str(series.min()),
                "max_date": str(series.max()),
            })
        else:
            top_values = series.value_counts().head(5).to_dict()
            col_info["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        profile["columns"].append(col_info)

    return profile

def _safe_float(value):
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return None
    return float(value)