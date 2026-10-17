import pandas as pd
import numpy as np

def generate_histogram_data(df: pd.DataFrame, value_field: str, bins: int = 10) -> dict:
    if value_field not in df.columns:
        return {"chart_type": "histogram", "data": [], "error": "Missing column"}
        
    series = pd.to_numeric(df[value_field], errors="coerce").dropna()
    if series.empty:
        return {"chart_type": "histogram", "data": [], "error": "No valid data"}
        
    counts, bin_edges = np.histogram(series, bins=bins)
    
    data = []
    for i in range(len(counts)):
        data.append({
            "range": f"{round(bin_edges[i], 2)} - {round(bin_edges[i+1], 2)}",
            "count": int(counts[i])
        })
        
    return {
        "chart_type": "histogram",
        "value_field": value_field,
        "data": data,
        "bins": bins,
    }
