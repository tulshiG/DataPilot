import pandas as pd

def analyze_trend(df: pd.DataFrame, date_column: str, value_column: str, freq: str = "M") -> dict:
    """
    Compare business performance over time.
    Groups by period (default monthly), computes period-over-period change.
    """
    if date_column not in df.columns or value_column not in df.columns:
        return {"error": "Missing required columns", "periods": []}

    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce", format="mixed")
    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    df = df.dropna(subset=[date_column, value_column])

    if df.empty:
        return {"error": "No valid data after cleaning", "periods": []}

    df["_period"] = df[date_column].dt.to_period(freq)
    grouped = df.groupby("_period", as_index=False)[value_column].sum().sort_values("_period")
    grouped["_period_str"] = grouped["_period"].astype(str)

    periods = []
    prev_value = None
    for _, row in grouped.iterrows():
        value = float(row[value_column])
        change_pct = None
        if prev_value is not None and prev_value != 0:
            change_pct = round(((value - prev_value) / prev_value) * 100, 2)
        periods.append({
            "period": row["_period_str"],
            "value": round(value, 2),
            "change_percent": change_pct,
        })
        prev_value = value

    # Overall trend direction using simple linear slope
    values = [p["value"] for p in periods]
    direction = "flat"
    if len(values) >= 2:
        overall_change = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
        direction = "up" if overall_change > 5 else "down" if overall_change < -5 else "flat"

    return {
        "periods": periods,
        "direction": direction,
        "overall_change_percent": round(overall_change, 2) if len(values) >= 2 else None,
    }