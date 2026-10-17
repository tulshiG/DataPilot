"""
ML Engine — Anomaly Detection
================================
Multi-method anomaly detection for automated data quality monitoring
and outlier discovery in analytics datasets.

Methods:
    • IQR (Interquartile Range) — fast statistical baseline
    • Z-Score — parametric, assumes normal distribution
    • Isolation Forest — non-parametric ML, handles multivariate outliers
    • Moving Average Deviation — for time-series anomalies

Usage:
    anomalies = detect_anomalies(df, columns=["revenue", "quantity"], method="auto")
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_anomalies(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    method: str = "auto",
    contamination: float = 0.05,
    time_col: str | None = None,
) -> dict:
    """
    Detect anomalies in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
    columns : list[str], optional
        Columns to check. If None, auto-select numeric columns.
    method : str
        "auto" | "iqr" | "zscore" | "isolation_forest" | "moving_avg"
    contamination : float
        Expected proportion of anomalies (0.01–0.15).
    time_col : str, optional
        If provided, use time-series aware detection.

    Returns
    -------
    dict with: anomaly_count, anomaly_indices, column_anomalies, summary
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    if not columns:
        return {"status": "error", "message": "No numeric columns found"}

    # Auto-select method
    if method == "auto":
        if time_col and time_col in df.columns:
            method = "moving_avg"
        elif len(df) >= 100 and len(columns) >= 2:
            method = "isolation_forest"
        else:
            method = "iqr"

    try:
        if method == "isolation_forest":
            result = _isolation_forest(df, columns, contamination)
        elif method == "zscore":
            result = _zscore_detection(df, columns)
        elif method == "moving_avg" and time_col:
            result = _moving_avg_detection(df, columns, time_col)
        else:
            result = _iqr_detection(df, columns)

        result["method_used"] = method
        result["status"] = "success"
        return result

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        return {"status": "error", "message": str(e), "method_used": method}


def _iqr_detection(df, columns) -> dict:
    """IQR-based anomaly detection."""
    all_anomaly_idx = set()
    column_results = {}

    for col in columns:
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if len(series) < 4:
            continue

        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1

        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR

        mask = (df[col] < lower) | (df[col] > upper)
        anomaly_indices = df.index[mask].tolist()
        all_anomaly_idx.update(anomaly_indices)

        column_results[col] = {
            "anomaly_count": int(mask.sum()),
            "lower_bound": round(float(lower), 2),
            "upper_bound": round(float(upper), 2),
            "anomaly_indices": anomaly_indices[:20],  # cap for response size
            "anomaly_values": df.loc[mask, col].head(10).tolist(),
        }

    return {
        "anomaly_count": len(all_anomaly_idx),
        "anomaly_indices": sorted(list(all_anomaly_idx))[:100],
        "column_anomalies": column_results,
        "total_rows": len(df),
        "anomaly_rate": round(len(all_anomaly_idx) / max(len(df), 1) * 100, 2),
    }


def _zscore_detection(df, columns, threshold=3.0) -> dict:
    """Z-score based anomaly detection."""
    all_anomaly_idx = set()
    column_results = {}

    for col in columns:
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if len(series) < 4:
            continue

        mean = series.mean()
        std = series.std()
        if std == 0:
            continue

        z_scores = np.abs((df[col] - mean) / std)
        mask = z_scores > threshold
        anomaly_indices = df.index[mask].tolist()
        all_anomaly_idx.update(anomaly_indices)

        column_results[col] = {
            "anomaly_count": int(mask.sum()),
            "mean": round(float(mean), 2),
            "std": round(float(std), 2),
            "threshold": threshold,
            "anomaly_indices": anomaly_indices[:20],
            "max_zscore": round(float(z_scores.max()), 2),
        }

    return {
        "anomaly_count": len(all_anomaly_idx),
        "anomaly_indices": sorted(list(all_anomaly_idx))[:100],
        "column_anomalies": column_results,
        "total_rows": len(df),
        "anomaly_rate": round(len(all_anomaly_idx) / max(len(df), 1) * 100, 2),
    }


def _isolation_forest(df, columns, contamination) -> dict:
    """Isolation Forest based multivariate anomaly detection."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.warning("scikit-learn not available, falling back to IQR")
        return _iqr_detection(df, columns)

    # Prepare feature matrix
    X = df[columns].copy()
    X = X.fillna(X.median())

    # Standardize
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit model
    iso = IsolationForest(
        contamination=contamination,
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
    )
    predictions = iso.fit_predict(X_scaled)
    scores = iso.decision_function(X_scaled)

    # -1 = anomaly, 1 = normal
    anomaly_mask = predictions == -1
    anomaly_indices = df.index[anomaly_mask].tolist()

    # Per-column analysis
    column_results = {}
    for col in columns:
        col_anomalies = df.loc[anomaly_mask, col]
        normal_vals = df.loc[~anomaly_mask, col]
        column_results[col] = {
            "anomaly_count": int(anomaly_mask.sum()),
            "anomaly_mean": round(float(col_anomalies.mean()), 2) if len(col_anomalies) > 0 else None,
            "normal_mean": round(float(normal_vals.mean()), 2) if len(normal_vals) > 0 else None,
        }

    return {
        "anomaly_count": int(anomaly_mask.sum()),
        "anomaly_indices": anomaly_indices[:100],
        "anomaly_scores": [round(float(s), 4) for s in scores[anomaly_mask][:20]],
        "column_anomalies": column_results,
        "total_rows": len(df),
        "anomaly_rate": round(float(anomaly_mask.sum()) / max(len(df), 1) * 100, 2),
    }


def _moving_avg_detection(df, columns, time_col, window=7, threshold=2.5) -> dict:
    """Time-series anomaly detection using moving average deviation."""
    ts_df = df.copy()
    ts_df[time_col] = pd.to_datetime(ts_df[time_col], errors="coerce")
    ts_df = ts_df.dropna(subset=[time_col]).sort_values(time_col)

    all_anomaly_idx = set()
    column_results = {}

    for col in columns:
        if col not in ts_df.columns or col == time_col:
            continue

        series = ts_df[col].astype(float)
        ma = series.rolling(window=window, center=True).mean()
        residual = np.abs(series - ma)
        std = residual.rolling(window=window, center=True).std()

        # Avoid division by zero
        std = std.replace(0, np.nan).fillna(residual.std())

        z = residual / std
        mask = z > threshold
        anomaly_indices = ts_df.index[mask].tolist()
        all_anomaly_idx.update(anomaly_indices)

        column_results[col] = {
            "anomaly_count": int(mask.sum()),
            "window_size": window,
            "threshold": threshold,
            "anomaly_dates": ts_df.loc[mask, time_col].dt.strftime("%Y-%m-%d").head(10).tolist(),
        }

    return {
        "anomaly_count": len(all_anomaly_idx),
        "anomaly_indices": sorted(list(all_anomaly_idx))[:100],
        "column_anomalies": column_results,
        "total_rows": len(df),
        "anomaly_rate": round(len(all_anomaly_idx) / max(len(df), 1) * 100, 2),
    }
