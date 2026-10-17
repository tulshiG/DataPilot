"""
ML Engine — Chart Recommendation
===================================
ML-driven visualization type recommendation based on data characteristics.

Analyzes query results and metadata to recommend the most appropriate
chart type, encodings, and formatting.

Rules engine considers:
    • Number of dimensions vs metrics
    • Cardinality of categorical columns
    • Temporal presence (→ line chart)
    • Distribution shape (→ histogram vs bar)
    • Data density (→ scatter vs heatmap)
    • Result size
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Chart type definitions with scoring criteria
CHART_TYPES = {
    "bar": {
        "name": "Bar Chart",
        "description": "Compare values across categories",
        "ideal_for": "categorical + 1 metric",
    },
    "horizontal_bar": {
        "name": "Horizontal Bar Chart",
        "description": "Compare values with long category labels",
        "ideal_for": "categorical with many values or long labels",
    },
    "line": {
        "name": "Line Chart",
        "description": "Show trends over time",
        "ideal_for": "time series data",
    },
    "area": {
        "name": "Area Chart",
        "description": "Show trends with volume emphasis",
        "ideal_for": "time series with cumulative context",
    },
    "pie": {
        "name": "Pie Chart",
        "description": "Show proportions of a whole",
        "ideal_for": "2-6 categories, proportion focus",
    },
    "donut": {
        "name": "Donut Chart",
        "description": "Show proportions with center metric",
        "ideal_for": "proportions with a summary statistic",
    },
    "scatter": {
        "name": "Scatter Plot",
        "description": "Show relationship between two numeric variables",
        "ideal_for": "2 numeric columns, correlation analysis",
    },
    "heatmap": {
        "name": "Heatmap",
        "description": "Show density or correlation matrix",
        "ideal_for": "2 dimensions + 1 metric, many data points",
    },
    "histogram": {
        "name": "Histogram",
        "description": "Show distribution of a single variable",
        "ideal_for": "distribution analysis, single numeric column",
    },
    "kpi_card": {
        "name": "KPI Card",
        "description": "Display a single key metric",
        "ideal_for": "single aggregate value",
    },
    "table": {
        "name": "Data Table",
        "description": "Show detailed tabular data",
        "ideal_for": "many columns, detailed view",
    },
    "stacked_bar": {
        "name": "Stacked Bar Chart",
        "description": "Compare composition across categories",
        "ideal_for": "2 dimensions + 1 metric",
    },
    "grouped_bar": {
        "name": "Grouped Bar Chart",
        "description": "Compare multiple metrics across categories",
        "ideal_for": "1 dimension + multiple metrics",
    },
}


def recommend_chart(
    columns: list[str],
    rows: list[dict],
    spec: dict | None = None,
    column_types: dict | None = None,
) -> dict:
    """
    Recommend the best chart type for query results.

    Parameters
    ----------
    columns : list[str]
        Column names in the result.
    rows : list[dict]
        Query result rows.
    spec : dict, optional
        The query_spec for intent context.
    column_types : dict, optional
        Mapping of column name → data type.

    Returns
    -------
    dict with: recommended (primary), alternatives, encodings, reasoning
    """
    if not rows or not columns:
        return _single_recommendation("table", "No data to visualize", {})

    n_rows = len(rows)
    n_cols = len(columns)

    # Classify columns
    if column_types is None:
        column_types = _infer_column_types(columns, rows)

    numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
    categorical_cols = [c for c, t in column_types.items() if t == "categorical"]
    temporal_cols = [c for c, t in column_types.items() if t == "temporal"]

    # Get intent from spec
    intent = (spec or {}).get("intent", "explore")
    aggregation = (spec or {}).get("aggregation")

    # Score each chart type
    scores = {}

    # ── Single value (KPI) ──
    if n_rows == 1 and n_cols <= 2 and aggregation:
        return _single_recommendation("kpi_card", "Single aggregate value", {
            "value_column": numeric_cols[0] if numeric_cols else columns[0],
        })

    # ── Time-series ──
    if temporal_cols:
        if n_rows > 2:
            scores["line"] = 90
            scores["area"] = 75
        if numeric_cols and len(numeric_cols) >= 2:
            scores["line"] = 85  # multi-line

    # ── Categorical + metric ──
    if categorical_cols and numeric_cols:
        cardinality = _estimate_cardinality(rows, categorical_cols[0])

        if cardinality <= 6:
            scores["pie"] = 70
            scores["donut"] = 65
            scores["bar"] = 80
        elif cardinality <= 15:
            scores["bar"] = 85
            scores["horizontal_bar"] = 75
        else:
            scores["horizontal_bar"] = 80
            scores["table"] = 70

        # Check for long labels
        avg_label_len = _avg_label_length(rows, categorical_cols[0])
        if avg_label_len > 15:
            scores["horizontal_bar"] = scores.get("horizontal_bar", 0) + 15

    # ── Two categorical + metric (stacked) ──
    if len(categorical_cols) >= 2 and numeric_cols:
        scores["stacked_bar"] = 80
        scores["heatmap"] = 75
        scores["grouped_bar"] = 70

    # ── Two numeric (scatter) ──
    if len(numeric_cols) >= 2 and not categorical_cols and not temporal_cols:
        scores["scatter"] = 85
        if n_rows > 100:
            scores["heatmap"] = 80

    # ── Distribution intent ──
    if intent == "distribution" or (n_cols == 1 and numeric_cols):
        scores["histogram"] = 90

    # ── Large result sets ──
    if n_rows > 50:
        scores["table"] = max(scores.get("table", 0), 60)

    # ── Fallback ──
    if not scores:
        if n_cols > 5:
            scores["table"] = 80
        elif numeric_cols and categorical_cols:
            scores["bar"] = 75
        else:
            scores["table"] = 70

    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    primary = ranked[0]
    alternatives = ranked[1:4]

    # Generate encodings
    encodings = _generate_encodings(
        primary[0], columns, numeric_cols, categorical_cols, temporal_cols
    )

    return {
        "recommended": {
            "type": primary[0],
            **CHART_TYPES.get(primary[0], {}),
            "score": primary[1],
        },
        "alternatives": [
            {"type": t, **CHART_TYPES.get(t, {}), "score": s}
            for t, s in alternatives
        ],
        "encodings": encodings,
        "reasoning": _generate_reasoning(
            primary[0], n_rows, numeric_cols, categorical_cols, temporal_cols, intent
        ),
        "data_profile": {
            "rows": n_rows,
            "columns": n_cols,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "temporal_columns": temporal_cols,
        },
    }


def _infer_column_types(columns: list[str], rows: list[dict]) -> dict:
    """Infer column types from sample data."""
    types = {}
    for col in columns:
        values = [r.get(col) for r in rows[:50] if r.get(col) is not None]
        if not values:
            types[col] = "unknown"
            continue

        # Check numeric
        numeric_count = sum(1 for v in values if isinstance(v, (int, float)))
        if numeric_count / len(values) > 0.8:
            types[col] = "numeric"
            continue

        # Check temporal
        str_values = [str(v) for v in values[:10]]
        import re
        date_pattern = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")
        date_count = sum(1 for v in str_values if date_pattern.search(v))
        if date_count / len(str_values) > 0.5:
            types[col] = "temporal"
            continue

        # Check temporal column names
        temporal_keywords = ["date", "time", "year", "month", "day", "created", "updated"]
        if any(kw in col.lower() for kw in temporal_keywords):
            types[col] = "temporal"
            continue

        types[col] = "categorical"

    return types


def _estimate_cardinality(rows: list[dict], col: str) -> int:
    """Estimate unique value count for a column."""
    values = set(str(r.get(col, "")) for r in rows)
    return len(values)


def _avg_label_length(rows: list[dict], col: str) -> float:
    """Average string length of categorical values."""
    lengths = [len(str(r.get(col, ""))) for r in rows[:20]]
    return sum(lengths) / max(len(lengths), 1)


def _generate_encodings(chart_type, columns, numeric, categorical, temporal) -> dict:
    """Generate encoding mappings for the recommended chart."""
    enc = {}

    if chart_type in ("bar", "horizontal_bar", "pie", "donut"):
        enc["x"] = categorical[0] if categorical else columns[0]
        enc["y"] = numeric[0] if numeric else columns[-1]
        if len(numeric) > 1:
            enc["color"] = numeric[1]

    elif chart_type in ("line", "area"):
        enc["x"] = temporal[0] if temporal else columns[0]
        enc["y"] = numeric[0] if numeric else columns[-1]
        if categorical:
            enc["color"] = categorical[0]

    elif chart_type == "scatter":
        enc["x"] = numeric[0] if len(numeric) > 0 else columns[0]
        enc["y"] = numeric[1] if len(numeric) > 1 else columns[-1]
        if categorical:
            enc["color"] = categorical[0]

    elif chart_type == "heatmap":
        enc["x"] = categorical[0] if categorical else columns[0]
        enc["y"] = categorical[1] if len(categorical) > 1 else columns[1] if len(columns) > 1 else columns[0]
        enc["value"] = numeric[0] if numeric else columns[-1]

    elif chart_type == "histogram":
        enc["x"] = numeric[0] if numeric else columns[0]

    elif chart_type == "kpi_card":
        enc["value"] = numeric[0] if numeric else columns[0]

    elif chart_type == "stacked_bar":
        enc["x"] = categorical[0] if categorical else columns[0]
        enc["y"] = numeric[0] if numeric else columns[-1]
        enc["stack"] = categorical[1] if len(categorical) > 1 else None

    return enc


def _generate_reasoning(chart_type, n_rows, numeric, categorical, temporal, intent) -> str:
    """Human-readable reasoning for the chart choice."""
    reasons = []

    if chart_type == "line" and temporal:
        reasons.append(f"Temporal column '{temporal[0]}' detected → line chart for trend visualization")
    elif chart_type == "bar" and categorical:
        reasons.append(f"Categorical column '{categorical[0]}' with numeric metric → bar chart for comparison")
    elif chart_type == "pie":
        reasons.append(f"Few categories ({_estimate_cardinality.__name__}) → pie chart for proportion view")
    elif chart_type == "scatter":
        reasons.append(f"Two numeric columns → scatter plot for correlation analysis")
    elif chart_type == "kpi_card":
        reasons.append("Single aggregate result → KPI card display")
    elif chart_type == "table":
        reasons.append(f"Many columns or rows ({n_rows}) → table for detailed view")
    elif chart_type == "heatmap":
        reasons.append("Two dimensions with a metric → heatmap for density visualization")

    if intent:
        reasons.append(f"Query intent: {intent}")

    return " | ".join(reasons) if reasons else "Default recommendation based on data shape"


def _single_recommendation(chart_type, reason, encodings) -> dict:
    """Helper for single recommendation result."""
    return {
        "recommended": {
            "type": chart_type,
            **CHART_TYPES.get(chart_type, {}),
            "score": 95,
        },
        "alternatives": [],
        "encodings": encodings,
        "reasoning": reason,
    }
