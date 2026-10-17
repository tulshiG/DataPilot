import pandas as pd

def generate_line_chart_data(df: pd.DataFrame, x_axis: str, series: list[str]) -> dict:
    """
    Shape data for a line chart showing trend(s) over time.
    Sorts by the date column and supports multiple numeric series (multi-line).
    """
    if x_axis not in df.columns:
        return {"chart_type": "line", "data": [], "error": "Missing date/time column"}

    df = df.copy()
    df[x_axis] = pd.to_datetime(df[x_axis], errors="coerce", format="mixed")
    df = df.dropna(subset=[x_axis]).sort_values(by=x_axis)

    valid_series = [s for s in series if s in df.columns]
    if not valid_series:
        return {"chart_type": "line", "data": [], "error": "No valid numeric series found"}

    # If there are duplicate dates, aggregate by day
    df["_date_str"] = df[x_axis].dt.strftime("%Y-%m-%d")
    grouped = df.groupby("_date_str", as_index=False)[valid_series].sum()

    data = []
    for _, row in grouped.iterrows():
        point = {"date": row["_date_str"]}
        for s in valid_series:
            point[s] = round(float(row[s]), 2)
        data.append(point)

    return {
        "chart_type": "line",
        "x_axis_label": x_axis,
        "series": valid_series,
        "data": data,
    }