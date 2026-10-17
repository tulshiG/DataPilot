import pandas as pd

def generate_bar_chart_data(df: pd.DataFrame, x_axis: str, y_axis: str, limit: int = 20, agg: str = "sum") -> dict:
    """
    Aggregate and shape data for a bar chart: one bar per category.
    Supports agg="sum", "mean", or "count".
    """
    if x_axis not in df.columns or y_axis not in df.columns:
        return {"chart_type": "bar", "data": [], "error": "Missing required columns"}

    if agg == "mean":
        grouped = df.groupby(x_axis, as_index=False)[y_axis].mean()
    elif agg == "count":
        grouped = df.groupby(x_axis, as_index=False)[y_axis].count()
    else:
        grouped = df.groupby(x_axis, as_index=False)[y_axis].sum()
    grouped = grouped.sort_values(by=y_axis, ascending=False).head(limit)

    data = [
        {"category": str(row[x_axis]), "value": _safe_number(row[y_axis])}
        for _, row in grouped.iterrows()
    ]

    return {
        "chart_type": "bar",
        "x_axis_label": x_axis,
        "y_axis_label": y_axis,
        "data": data,
    }

def _safe_number(val):
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0