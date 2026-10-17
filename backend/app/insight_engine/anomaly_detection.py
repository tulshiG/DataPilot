import pandas as pd
import numpy as np

def detect_anomalies(df: pd.DataFrame, value_column: str, method: str = "zscore", threshold: float = 3.0) -> dict:
    """
    Detect unusual values in a numeric column.
    method='zscore': flags points > threshold standard deviations from the mean.
    Also supports 'iqr' for skewed distributions.
    """
    if value_column not in df.columns:
        return {"error": "Missing column", "anomalies": []}

    series = pd.to_numeric(df[value_column], errors="coerce").dropna()
    if len(series) < 5:
        return {"anomalies": [], "note": "Not enough data points for reliable anomaly detection"}

    anomalies = []

    if method == "zscore":
        mean, std = series.mean(), series.std()
        if std == 0:
            return {"anomalies": [], "note": "No variance in data"}
        z_scores = (series - mean) / std
        flagged = series[z_scores.abs() > threshold]
        for idx, value in flagged.items():
            anomalies.append({
                "row_index": int(idx),
                "value": round(float(value), 2),
                "z_score": round(float(z_scores[idx]), 2),
                "severity": "high" if abs(z_scores[idx]) > threshold + 1 else "medium",
            })
    else:  # IQR method
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flagged = series[(series < lower) | (series > upper)]
        for idx, value in flagged.items():
            anomalies.append({
                "row_index": int(idx),
                "value": round(float(value), 2),
                "severity": "high" if (value < lower - iqr) or (value > upper + iqr) else "medium",
            })

    return {
        "method": method,
        "total_checked": len(series),
        "anomaly_count": len(anomalies),
        "anomalies": sorted(anomalies, key=lambda a: abs(a.get("z_score", a["value"])), reverse=True)[:20],
    }


def detect_sudden_changes(trend_periods: list[dict], spike_threshold: float = 30.0) -> list[dict]:
    """Given trend_analysis output periods, flag sudden period-over-period spikes/drops."""
    spikes = []
    for period in trend_periods:
        change = period.get("change_percent")
        if change is not None and abs(change) >= spike_threshold:
            spikes.append({
                "period": period["period"],
                "change_percent": change,
                "direction": "spike" if change > 0 else "drop",
            })
    return spikes