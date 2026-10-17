"""
ML Engine — Forecasting
=========================
Time-series forecasting using statsmodels.

Supports:
    • Linear trend detection
    • Seasonal decomposition
    • Exponential smoothing (Holt-Winters)
    • Simple moving average baseline
    • Confidence interval generation

Usage:
    forecast = run_forecast(df, date_col="order_date", value_col="revenue", periods=12)
    # Returns: predictions, trend, seasonality, confidence bands
"""

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def run_forecast(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    periods: int = 12,
    method: str = "auto",
    freq: str | None = None,
) -> dict:
    """
    Generate a time-series forecast.

    Parameters
    ----------
    df : pd.DataFrame
        Input data with at least date and value columns.
    date_col : str
        Name of the datetime column.
    value_col : str
        Name of the numeric column to forecast.
    periods : int
        Number of future periods to predict.
    method : str
        "auto" | "holt_winters" | "exponential" | "moving_average" | "linear"
    freq : str, optional
        Pandas frequency string (e.g., "MS" for month start). Auto-detected if None.

    Returns
    -------
    dict with keys:
        historical: list of {date, value}
        forecast: list of {date, predicted, lower, upper}
        trend: str ("increasing"|"decreasing"|"stable")
        trend_slope: float
        seasonality_detected: bool
        method_used: str
        metrics: dict (mae, rmse if validation possible)
    """
    try:
        # Prepare data
        ts_df = _prepare_timeseries(df, date_col, value_col, freq)
        if ts_df is None or len(ts_df) < 6:
            return _fallback_forecast(df, date_col, value_col, periods)

        # Auto-select method
        if method == "auto":
            method = _select_method(ts_df, value_col)

        # Run forecast
        if method == "holt_winters":
            result = _holt_winters_forecast(ts_df, value_col, periods)
        elif method == "exponential":
            result = _exponential_smoothing(ts_df, value_col, periods)
        elif method == "linear":
            result = _linear_forecast(ts_df, value_col, periods)
        else:
            result = _moving_average_forecast(ts_df, value_col, periods)

        # Detect trend
        trend, slope = _detect_trend(ts_df[value_col].values)

        # Detect seasonality
        seasonal = _detect_seasonality(ts_df[value_col].values)

        # Build historical data
        historical = [
            {"date": str(idx), "value": float(val)}
            for idx, val in zip(ts_df.index, ts_df[value_col])
        ]

        return {
            "historical": historical,
            "forecast": result["predictions"],
            "trend": trend,
            "trend_slope": round(float(slope), 4),
            "seasonality_detected": seasonal,
            "method_used": method,
            "metrics": result.get("metrics", {}),
            "periods": periods,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        return {"status": "error", "message": str(e), "method_used": method}


def _prepare_timeseries(df, date_col, value_col, freq):
    """Prepare a clean time-series DataFrame."""
    ts = df[[date_col, value_col]].copy()
    ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
    ts = ts.dropna()

    if len(ts) < 4:
        return None

    ts = ts.sort_values(date_col)
    ts = ts.set_index(date_col)

    # Aggregate duplicates
    ts = ts.groupby(level=0).mean()

    # Infer frequency
    if freq:
        ts = ts.asfreq(freq, method="ffill")
    else:
        inferred = pd.infer_freq(ts.index)
        if inferred:
            ts = ts.asfreq(inferred, method="ffill")
        else:
            # Resample to monthly as default
            ts = ts.resample("MS").mean().dropna()

    return ts


def _select_method(ts_df, value_col):
    """Auto-select the best forecasting method based on data characteristics."""
    n = len(ts_df)
    values = ts_df[value_col].values

    if n < 12:
        return "linear"

    # Check if seasonal pattern exists (needs at least 2 full cycles)
    if n >= 24 and _detect_seasonality(values):
        return "holt_winters"

    if n >= 12:
        return "exponential"

    return "moving_average"


def _holt_winters_forecast(ts_df, value_col, periods):
    """Holt-Winters exponential smoothing with seasonality."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ExponentialSmoothing(
                ts_df[value_col],
                seasonal_periods=min(12, len(ts_df) // 2),
                trend="add",
                seasonal="add",
                initialization_method="estimated",
            )
            fitted = model.fit(optimized=True)
            pred = fitted.forecast(periods)

        ci = _simple_confidence_interval(ts_df[value_col].values, pred.values)

        predictions = [
            {
                "date": str(idx),
                "predicted": round(float(val), 2),
                "lower": round(float(lo), 2),
                "upper": round(float(hi), 2),
            }
            for idx, val, lo, hi in zip(pred.index, pred.values, ci["lower"], ci["upper"])
        ]

        return {"predictions": predictions, "metrics": {"aic": round(fitted.aic, 2) if hasattr(fitted, 'aic') else None}}

    except Exception as e:
        logger.warning(f"Holt-Winters failed ({e}), falling back to exponential")
        return _exponential_smoothing(ts_df, value_col, periods)


def _exponential_smoothing(ts_df, value_col, periods):
    """Simple exponential smoothing."""
    try:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SimpleExpSmoothing(ts_df[value_col], initialization_method="estimated")
            fitted = model.fit(optimized=True)
            pred = fitted.forecast(periods)

        ci = _simple_confidence_interval(ts_df[value_col].values, pred.values)

        predictions = [
            {
                "date": str(idx),
                "predicted": round(float(val), 2),
                "lower": round(float(lo), 2),
                "upper": round(float(hi), 2),
            }
            for idx, val, lo, hi in zip(pred.index, pred.values, ci["lower"], ci["upper"])
        ]

        return {"predictions": predictions}

    except Exception:
        return _moving_average_forecast(ts_df, value_col, periods)


def _linear_forecast(ts_df, value_col, periods):
    """Simple linear regression forecast."""
    values = ts_df[value_col].values
    x = np.arange(len(values))

    # Fit linear trend
    coeffs = np.polyfit(x, values, 1)
    slope, intercept = coeffs

    # Predict future
    future_x = np.arange(len(values), len(values) + periods)
    predicted = slope * future_x + intercept

    # Generate future dates
    last_date = ts_df.index[-1]
    freq = ts_df.index.freq or pd.tseries.offsets.MonthBegin()
    future_dates = pd.date_range(start=last_date + freq, periods=periods, freq=freq)

    ci = _simple_confidence_interval(values, predicted)

    predictions = [
        {
            "date": str(d),
            "predicted": round(float(p), 2),
            "lower": round(float(lo), 2),
            "upper": round(float(hi), 2),
        }
        for d, p, lo, hi in zip(future_dates, predicted, ci["lower"], ci["upper"])
    ]

    return {"predictions": predictions, "metrics": {"slope": round(float(slope), 4)}}


def _moving_average_forecast(ts_df, value_col, periods):
    """Simple moving average forecast."""
    values = ts_df[value_col].values
    window = min(6, len(values) // 2)
    ma = np.mean(values[-window:])

    last_date = ts_df.index[-1]
    freq = ts_df.index.freq or pd.tseries.offsets.MonthBegin()
    future_dates = pd.date_range(start=last_date + freq, periods=periods, freq=freq)

    std = np.std(values[-window:])

    predictions = [
        {
            "date": str(d),
            "predicted": round(float(ma), 2),
            "lower": round(float(ma - 1.96 * std), 2),
            "upper": round(float(ma + 1.96 * std), 2),
        }
        for d in future_dates
    ]

    return {"predictions": predictions}


def _detect_trend(values: np.ndarray) -> tuple[str, float]:
    """Detect if values have an increasing, decreasing, or stable trend."""
    if len(values) < 3:
        return "stable", 0.0

    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]

    # Normalize slope relative to mean
    mean_val = np.mean(np.abs(values)) or 1
    relative_slope = slope / mean_val

    if relative_slope > 0.02:
        return "increasing", slope
    elif relative_slope < -0.02:
        return "decreasing", slope
    else:
        return "stable", slope


def _detect_seasonality(values: np.ndarray) -> bool:
    """Simple seasonality detection via autocorrelation."""
    if len(values) < 12:
        return False

    try:
        # Check autocorrelation at common seasonal lags
        from numpy.fft import fft
        freq_domain = np.abs(fft(values - np.mean(values)))
        n = len(freq_domain) // 2
        if n < 2:
            return False
        # Check if any frequency component is dominant
        power = freq_domain[1:n]
        mean_power = np.mean(power)
        max_power = np.max(power)
        return max_power > 3 * mean_power  # strong periodic signal
    except Exception:
        return False


def _simple_confidence_interval(historical, predicted, level=0.95):
    """Generate confidence intervals based on historical variance."""
    std = np.std(historical)
    z = 1.96 if level == 0.95 else 1.645
    # Widen CI progressively for further-out predictions
    widths = np.array([z * std * (1 + 0.1 * i) for i in range(len(predicted))])
    return {
        "lower": predicted - widths,
        "upper": predicted + widths,
    }


def _fallback_forecast(df, date_col, value_col, periods):
    """Minimal fallback when data is too sparse for proper forecasting."""
    return {
        "historical": [],
        "forecast": [],
        "trend": "unknown",
        "trend_slope": 0.0,
        "seasonality_detected": False,
        "method_used": "none",
        "metrics": {},
        "periods": periods,
        "status": "insufficient_data",
        "message": f"Need at least 6 data points, got {len(df)}",
    }
