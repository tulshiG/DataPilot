import pandas as pd
import numpy as np

def handle_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean null/empty values using intelligent strategies:
    - Numeric: Mean for normal, Median for skewed.
    - Categorical: Mode for <5% missing, 'Unknown' for 5-30%, 'Missing' if >30%.
    - Date: Forward fill.
    Returns cleaned dataframe and a cleaning report dictionary.
    """
    df = df.copy()
    report = {"actions": []}

    placeholders = ["", " ", "NA", "N/A", "null", "NULL", "None", "-", "?"]
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].replace(placeholders, np.nan)

    df.dropna(axis=1, how="all", inplace=True)
    df.dropna(axis=0, how="all", inplace=True)

    for col in df.columns:
        missing_count = int(df[col].isnull().sum())
        if missing_count == 0:
            continue

        missing_pct = missing_count / len(df)
        
        # Datetimes
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].ffill().bfill()
            report["actions"].append(f"Forward-filled {missing_count} missing dates in '{col}'")
            continue

        # Numerics
        if pd.api.types.is_numeric_dtype(df[col]):
            skewness = df[col].skew()
            if missing_pct < 0.05:
                # Small amount missing, use forward fill or median as fallback
                df[col] = df[col].ffill()
                report["actions"].append(f"Forward-filled {missing_count} missing values in '{col}'")
            elif pd.notnull(skewness) and abs(skewness) < 1:
                # Roughly symmetric, use mean
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                report["actions"].append(f"Replaced {missing_count} missing values in '{col}' with mean ({mean_val:.2f})")
            else:
                # Skewed, use median
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                report["actions"].append(f"Replaced {missing_count} missing values in '{col}' with median ({median_val})")
        # Categoricals
        else:
            if missing_pct < 0.05:
                mode_val = df[col].mode()
                fill_val = mode_val[0] if not mode_val.empty else "Unknown"
                df[col] = df[col].fillna(fill_val)
                report["actions"].append(f"Replaced {missing_count} missing values in '{col}' with mode ('{fill_val}')")
            elif missing_pct <= 0.30:
                df[col] = df[col].fillna("Unknown")
                report["actions"].append(f"Replaced {missing_count} missing values in '{col}' with 'Unknown'")
            else:
                df[col] = df[col].fillna("Missing")
                report["actions"].append(f"Created 'Missing' category for {missing_count} missing values in '{col}'")

    # Outlier Capping (IQR)
    for col in df.select_dtypes(include="number").columns:
        if df[col].nunique() > 2: # Skip binary/boolean-like
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                outliers = ((df[col] < lower) | (df[col] > upper)).sum()
                if outliers > 0:
                    df[col] = df[col].clip(lower=lower, upper=upper)
                    report["actions"].append(f"Capped {outliers} outliers in '{col}' using IQR")

    return df, report


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate rows. Returns cleaned df and count removed."""
    before = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    removed = before - len(df)
    return df, removed