import pandas as pd

def validate_dataset(df: pd.DataFrame) -> dict:
    """
    Run validation checks and return a structured report of issues found.
    Does NOT modify the dataframe — purely diagnostic.
    """
    issues = []

    # Check for columns with excessive nulls even after cleaning
    for col in df.columns:
        null_pct = df[col].isnull().mean() * 100
        if null_pct > 50:
            issues.append({
                "type": "high_null_percentage",
                "column": col,
                "detail": f"{null_pct:.1f}% missing values remain",
            })

    # Check for constant columns (no analytical value)
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 1:
            issues.append({
                "type": "constant_column",
                "column": col,
                "detail": "Column has a single unique value. Action: Consider dropping if not needed.",
            })

    # Check numeric columns for outliers using IQR
    for col in df.select_dtypes(include="number").columns:
        if df[col].nunique() <= 2:
            continue
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_count = int(((df[col] < lower) | (df[col] > upper)).sum())
        if outlier_count > 0:
            issues.append({
                "type": "outliers_detected",
                "column": col,
                "detail": f"{outlier_count} potential outlier(s) detected. Action: Will be capped using IQR.",
            })

    # Check for negative values in columns that look like they shouldn't have them
    for col in df.select_dtypes(include="number").columns:
        if any(hint in col.lower() for hint in ["price", "amount", "quantity", "qty", "cost", "revenue", "age"]):
            negative_count = int((df[col] < 0).sum())
            if negative_count > 0:
                issues.append({
                    "type": "invalid_negative_values",
                    "column": col,
                    "detail": f"{negative_count} negative value(s) found in {col}. Action: Review for data entry errors.",
                })

    # Check for mixed data types (often stored as objects)
    for col in df.select_dtypes(include="object").columns:
        numeric_count = pd.to_numeric(df[col], errors='coerce').notnull().sum()
        if 0 < numeric_count < len(df[col]):
            issues.append({
                "type": "mixed_data_types",
                "column": col,
                "detail": f"{numeric_count} numeric values mixed with text. Action: Converted to string/category.",
            })

    return {
        "is_valid": len([i for i in issues if i["type"] == "high_null_percentage"]) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }