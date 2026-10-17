import pandas as pd

def generate_pie_chart_data(df: pd.DataFrame, label_field: str, value_field: str | None = None) -> dict:
    if label_field not in df.columns:
        return {"chart_type": "pie", "data": [], "error": "Missing label column"}
        
    if value_field and value_field in df.columns:
        grouped = df.groupby(label_field, as_index=False)[value_field].sum()
        grouped = grouped.sort_values(by=value_field, ascending=False).head(10)
        data = [
            {"label": str(row[label_field]), "value": round(float(row[value_field]), 2)}
            for _, row in grouped.iterrows()
        ]
    else:
        grouped = df[label_field].value_counts().reset_index().head(10)
        grouped.columns = [label_field, "count"]
        data = [
            {"label": str(row[label_field]), "value": int(row["count"])}
            for _, row in grouped.iterrows()
        ]
        
    return {
        "chart_type": "pie",
        "label_field": label_field,
        "value_field": value_field or "count",
        "data": data,
    }
