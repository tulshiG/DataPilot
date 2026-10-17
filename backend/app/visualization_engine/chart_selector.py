import pandas as pd

def detect_data_pattern(df: pd.DataFrame) -> dict:
    """
    Analyze a query result set to understand its shape:
    - column types (numeric, categorical, datetime)
    - cardinality of categorical columns
    - whether it looks like a time series, a distribution, a comparison, or a correlation set
    """
    if df.empty:
        return {"pattern": "empty", "columns": []}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    datetime_cols = df.select_dtypes(include="datetime").columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols and c not in datetime_cols]

    # Try to coerce object columns that are actually dates but weren't parsed
    for col in categorical_cols[:]:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if parsed.notnull().mean() > 0.8:
                datetime_cols.append(col)
                categorical_cols.remove(col)
        except Exception:
            pass

    row_count = len(df)
    category_cardinality = {c: int(df[c].nunique()) for c in categorical_cols}

    # Determine the dominant pattern
    if datetime_cols and numeric_cols:
        pattern = "time_series"
    elif len(numeric_cols) >= 2 and not categorical_cols:
        pattern = "correlation"
    elif categorical_cols and numeric_cols:
        avg_cardinality = sum(category_cardinality.values()) / max(len(category_cardinality), 1)
        pattern = "distribution" if avg_cardinality <= 8 else "comparison"
    elif len(numeric_cols) == 1 and not categorical_cols:
        pattern = "single_metric"
    else:
        pattern = "tabular"

    return {
        "pattern": pattern,
        "row_count": row_count,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "category_cardinality": category_cardinality,
    }
def recommend_chart(pattern_result: dict) -> dict:
    """
    Map a detected data pattern to the best chart type + axis configuration.
    Returns a spec the frontend can render directly.
    """
    pattern = pattern_result["pattern"]
    numeric_cols = pattern_result["numeric_columns"]
    categorical_cols = pattern_result["categorical_columns"]
    datetime_cols = pattern_result["datetime_columns"]
    row_count = pattern_result["row_count"]

    if pattern == "empty":
        return {"chart_type": "none", "reason": "No data returned"}

    if pattern == "time_series":
        return {
            "chart_type": "line",
            "x_axis": datetime_cols[0],
            "y_axis": numeric_cols[0],
            "series": numeric_cols[:3],  # support multi-line if multiple metrics present
            "reason": "Data contains a date/time column paired with numeric values — ideal for showing trends.",
        }

    if pattern == "distribution":
        cat_col = categorical_cols[0]
        cardinality = pattern_result["category_cardinality"].get(cat_col, 0)
        if cardinality <= 6:
            return {
                "chart_type": "pie",
                "label_field": cat_col,
                "value_field": numeric_cols[0] if numeric_cols else None,
                "reason": f"Low number of categories ({cardinality}) — well suited to a proportion view.",
            }
        return {
            "chart_type": "bar",
            "x_axis": cat_col,
            "y_axis": numeric_cols[0] if numeric_cols else None,
            "reason": "Categorical comparison across a moderate number of groups.",
        }

    if pattern == "comparison":
        return {
            "chart_type": "bar",
            "x_axis": categorical_cols[0],
            "y_axis": numeric_cols[0] if numeric_cols else None,
            "reason": "Higher cardinality categorical comparison — bar chart handles many categories better than pie.",
        }

    if pattern == "correlation":
        return {
            "chart_type": "scatter",
            "x_axis": numeric_cols[0],
            "y_axis": numeric_cols[1],
            "reason": "Two numeric variables with no categorical grouping — useful for spotting relationships.",
        }

    if pattern == "single_metric":
        # A single numeric column with many rows -> distribution of values, not a category comparison
        if row_count > 20:
            return {
                "chart_type": "histogram",
                "value_field": numeric_cols[0],
                "bins": 10,
                "reason": "A single numeric column with many rows — histogram shows the value distribution.",
            }
        return {
            "chart_type": "kpi",
            "value_field": numeric_cols[0],
            "reason": "Too few data points for a meaningful chart — displaying as a single KPI value.",
        }

    # Fallback
    return {
        "chart_type": "table",
        "reason": "Data shape doesn't clearly match a standard chart pattern — showing as a table.",
    }


def select_visualization(df) -> dict:
    """Combined entry point: detect pattern, then recommend a chart for it."""
    pattern_result = detect_data_pattern(df)
    chart_recommendation = recommend_chart(pattern_result)
    return {
        "pattern": pattern_result,
        "recommendation": chart_recommendation,
    }
def build_chart_data(df, recommendation: dict) -> dict:
    """Dispatch to the correct chart generator based on the recommendation's chart_type."""
    from app.visualization_engine.bar_chart import generate_bar_chart_data
    from app.visualization_engine.line_chart import generate_line_chart_data
    from app.visualization_engine.pie_chart import generate_pie_chart_data
    from app.visualization_engine.histogram import generate_histogram_data
    from app.visualization_engine.scatter_plot import generate_scatter_plot_data

    chart_type = recommendation.get("chart_type")

    if chart_type == "bar":
        return generate_bar_chart_data(df, recommendation["x_axis"], recommendation["y_axis"])
    if chart_type == "line":
        return generate_line_chart_data(df, recommendation["x_axis"], recommendation["series"])
    if chart_type == "pie":
        return generate_pie_chart_data(df, recommendation["label_field"], recommendation.get("value_field"))
    if chart_type == "histogram":
        return generate_histogram_data(df, recommendation["value_field"], recommendation.get("bins", 10))
    if chart_type == "scatter":
        return generate_scatter_plot_data(df, recommendation["x_axis"], recommendation["y_axis"])
    if chart_type == "kpi":
        val = df[recommendation["value_field"]].iloc[0] if not df.empty else None
        return {"chart_type": "kpi", "value": float(val) if val is not None else None}

    return {"chart_type": "table", "data": df.to_dict(orient="records")}