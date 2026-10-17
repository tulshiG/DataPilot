"""Heatmap (correlation matrix) data generator."""
import pandas as pd
import numpy as np


def generate_heatmap_data(df: pd.DataFrame, max_cols: int = 8) -> dict:
    """
    Compute pairwise Pearson correlation between numeric columns.
    Returns the matrix in a row/cell format the frontend can render as a heatmap.
    """
    numeric_df = df.select_dtypes(include="number")
    # Exclude likely ID columns
    numeric_df = numeric_df[[
        c for c in numeric_df.columns
        if not any(h in c.lower() for h in ["id", "code", "zip", "phone"])
    ]]

    if numeric_df.shape[1] < 2:
        return {"chart_type": "heatmap", "data": [], "columns": [], "error": "Need ≥ 2 numeric columns"}

    # Limit columns
    numeric_df = numeric_df.iloc[:, :max_cols]
    corr = numeric_df.corr().round(3)
    columns = list(corr.columns)

    # Flatten to list-of-cells format
    cells = []
    for row_label in columns:
        for col_label in columns:
            val = corr.loc[row_label, col_label]
            cells.append({
                "x": col_label,
                "y": row_label,
                "value": float(val) if not np.isnan(val) else 0.0,
            })

    return {
        "chart_type": "heatmap",
        "columns": columns,
        "data": cells,
    }
