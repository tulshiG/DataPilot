import pandas as pd

def generate_scatter_plot_data(df: pd.DataFrame, x_axis: str, y_axis: str, max_points: int = 500) -> dict:
    """
    Shape data for a scatter plot of two numeric variables.
    Samples down to max_points if the dataset is very large, to keep the frontend responsive.
    """
    if x_axis not in df.columns or y_axis not in df.columns:
        return {"chart_type": "scatter", "data": [], "error": "Missing required columns"}

    subset = df[[x_axis, y_axis]].dropna()
    subset[x_axis] = pd.to_numeric(subset[x_axis], errors="coerce")
    subset[y_axis] = pd.to_numeric(subset[y_axis], errors="coerce")
    subset = subset.dropna()

    if len(subset) > max_points:
        subset = subset.sample(n=max_points, random_state=42)

    data = [{"x": round(float(row[x_axis]), 2), "y": round(float(row[y_axis]), 2)} for _, row in subset.iterrows()]

    # Simple correlation coefficient as a bonus insight
    correlation = round(float(subset[x_axis].corr(subset[y_axis])), 3) if len(subset) > 1 else None

    return {
        "chart_type": "scatter",
        "x_axis_label": x_axis,
        "y_axis_label": y_axis,
        "data": data,
        "correlation": correlation,
    }