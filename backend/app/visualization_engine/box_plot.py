"""Box plot data generator — used for distribution comparison across groups."""
import pandas as pd
import numpy as np


def generate_box_plot_data(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    max_groups: int = 8,
) -> dict:
    """
    Compute box plot statistics (min, Q1, median, Q3, max, outliers)
    for value_col grouped by group_col.
    """
    if group_col not in df.columns or value_col not in df.columns:
        return {"chart_type": "box", "data": [], "error": "Missing required columns"}

    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[value_col])

    # Limit to top N groups by count
    top_groups = df[group_col].value_counts().head(max_groups).index.tolist()
    df = df[df[group_col].isin(top_groups)]

    box_data = []
    for group, grp_df in df.groupby(group_col):
        vals = grp_df[value_col].dropna().values
        if len(vals) == 0:
            continue
        q1, median, q3 = np.percentile(vals, [25, 50, 75])
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        outliers = [round(float(v), 2) for v in vals if v < lower_fence or v > upper_fence]
        box_data.append({
            "group": str(group),
            "min": round(float(vals.min()), 2),
            "q1": round(float(q1), 2),
            "median": round(float(median), 2),
            "q3": round(float(q3), 2),
            "max": round(float(vals.max()), 2),
            "outliers": outliers[:20],   # cap outliers sent to frontend
            "count": int(len(vals)),
        })

    # Sort by median descending
    box_data.sort(key=lambda x: x["median"], reverse=True)

    return {
        "chart_type": "box",
        "group_col": group_col,
        "value_col": value_col,
        "data": box_data,
    }
