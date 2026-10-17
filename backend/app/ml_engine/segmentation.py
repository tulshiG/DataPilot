"""
ML Engine — Customer Segmentation
====================================
Unsupervised clustering for customer/entity segmentation using
K-Means and RFM (Recency, Frequency, Monetary) analysis.

Supports:
    • K-Means clustering with auto-K selection (elbow method)
    • RFM scoring with automatic quartile binning
    • Feature-based segmentation for any dataset
    • Segment profiling with descriptive statistics

Usage:
    result = run_segmentation(df, feature_cols=["revenue", "orders", "recency"])
    # Returns: cluster labels, profiles, optimal K, feature importance
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def run_segmentation(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    n_clusters: int | None = None,
    method: str = "kmeans",
    max_clusters: int = 8,
) -> dict:
    """
    Run customer/entity segmentation.

    Parameters
    ----------
    df : pd.DataFrame
    feature_cols : list[str], optional
        Columns to use for clustering. Auto-selects numeric if None.
    n_clusters : int, optional
        Number of clusters. Auto-selected via elbow method if None.
    method : str
        "kmeans" | "rfm"
    max_clusters : int
        Maximum clusters to try in auto-selection.

    Returns
    -------
    dict with: labels, profiles, optimal_k, inertia, feature_importance
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return {"status": "error", "message": "scikit-learn not installed"}

    if feature_cols is None:
        feature_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if len(feature_cols) < 2:
        return {"status": "error", "message": "Need at least 2 numeric features"}

    try:
        # Prepare features
        X = df[feature_cols].copy()
        X = X.fillna(X.median())

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Auto-select K
        if n_clusters is None:
            n_clusters = _find_optimal_k(X_scaled, max_clusters)

        # Fit K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Build profiles
        df_clustered = df[feature_cols].copy()
        df_clustered["cluster"] = labels

        profiles = []
        for cluster_id in range(n_clusters):
            cluster_data = df_clustered[df_clustered["cluster"] == cluster_id]
            profile = {
                "cluster_id": int(cluster_id),
                "size": int(len(cluster_data)),
                "percentage": round(len(cluster_data) / len(df) * 100, 1),
                "centroid": {
                    col: round(float(cluster_data[col].mean()), 2)
                    for col in feature_cols
                },
                "stats": {
                    col: {
                        "mean": round(float(cluster_data[col].mean()), 2),
                        "median": round(float(cluster_data[col].median()), 2),
                        "std": round(float(cluster_data[col].std()), 2),
                        "min": round(float(cluster_data[col].min()), 2),
                        "max": round(float(cluster_data[col].max()), 2),
                    }
                    for col in feature_cols
                },
            }
            # Auto-label based on relative position
            profile["label"] = _generate_cluster_label(profile, profiles, feature_cols)
            profiles.append(profile)

        # Feature importance (based on variance ratio)
        feature_importance = _calculate_feature_importance(X_scaled, labels, feature_cols)

        return {
            "status": "success",
            "method": "kmeans",
            "optimal_k": n_clusters,
            "labels": labels.tolist(),
            "profiles": profiles,
            "feature_importance": feature_importance,
            "inertia": round(float(kmeans.inertia_), 2),
            "total_rows": len(df),
            "features_used": feature_cols,
        }

    except Exception as e:
        logger.error(f"Segmentation failed: {e}")
        return {"status": "error", "message": str(e)}


def run_rfm_analysis(
    df: pd.DataFrame,
    customer_col: str,
    date_col: str,
    amount_col: str,
    n_segments: int = 4,
) -> dict:
    """
    RFM (Recency, Frequency, Monetary) segmentation.

    Parameters
    ----------
    customer_col : str
        Column identifying unique customers/entities.
    date_col : str
        Transaction date column.
    amount_col : str
        Transaction amount column.
    n_segments : int
        Number of RFM score bins (typically 4 or 5).
    """
    try:
        rfm_df = df.copy()
        rfm_df[date_col] = pd.to_datetime(rfm_df[date_col], errors="coerce")
        rfm_df = rfm_df.dropna(subset=[date_col, amount_col])

        # Calculate RFM
        reference_date = rfm_df[date_col].max() + pd.Timedelta(days=1)

        rfm = rfm_df.groupby(customer_col).agg({
            date_col: lambda x: (reference_date - x.max()).days,  # Recency
            amount_col: ["count", "sum"],  # Frequency, Monetary
        })

        rfm.columns = ["recency", "frequency", "monetary"]
        rfm = rfm[rfm["monetary"] > 0]  # Filter out non-positive

        # Score into quartiles
        for metric in ["recency", "frequency", "monetary"]:
            if metric == "recency":
                # Lower recency = better (more recent)
                rfm[f"{metric}_score"] = pd.qcut(
                    rfm[metric], q=n_segments, labels=list(range(n_segments, 0, -1)),
                    duplicates="drop"
                ).astype(int)
            else:
                rfm[f"{metric}_score"] = pd.qcut(
                    rfm[metric], q=n_segments, labels=list(range(1, n_segments + 1)),
                    duplicates="drop"
                ).astype(int)

        # Combined RFM score
        rfm["rfm_score"] = (
            rfm["recency_score"].astype(str) +
            rfm["frequency_score"].astype(str) +
            rfm["monetary_score"].astype(str)
        )
        rfm["total_score"] = rfm["recency_score"] + rfm["frequency_score"] + rfm["monetary_score"]

        # Segment labels
        max_score = n_segments * 3
        rfm["segment"] = rfm["total_score"].apply(
            lambda x: _rfm_segment_label(x, max_score)
        )

        # Build segment profiles
        segments = rfm.groupby("segment").agg({
            "recency": "mean",
            "frequency": "mean",
            "monetary": ["mean", "sum"],
            "total_score": "count",
        })
        segments.columns = ["avg_recency", "avg_frequency", "avg_monetary", "total_monetary", "count"]

        segment_profiles = []
        for seg_name, row in segments.iterrows():
            segment_profiles.append({
                "segment": seg_name,
                "count": int(row["count"]),
                "percentage": round(int(row["count"]) / len(rfm) * 100, 1),
                "avg_recency_days": round(float(row["avg_recency"]), 1),
                "avg_frequency": round(float(row["avg_frequency"]), 1),
                "avg_monetary": round(float(row["avg_monetary"]), 2),
                "total_monetary": round(float(row["total_monetary"]), 2),
            })

        return {
            "status": "success",
            "method": "rfm",
            "total_customers": len(rfm),
            "segments": sorted(segment_profiles, key=lambda x: x["count"], reverse=True),
            "rfm_summary": {
                "avg_recency": round(float(rfm["recency"].mean()), 1),
                "avg_frequency": round(float(rfm["frequency"].mean()), 1),
                "avg_monetary": round(float(rfm["monetary"].mean()), 2),
            },
        }

    except Exception as e:
        logger.error(f"RFM analysis failed: {e}")
        return {"status": "error", "message": str(e)}


def _find_optimal_k(X_scaled, max_k) -> int:
    """Find optimal K using the elbow method with second derivative."""
    from sklearn.cluster import KMeans

    max_k = min(max_k, len(X_scaled) - 1, 10)
    if max_k < 2:
        return 2

    inertias = []
    K_range = range(2, max_k + 1)

    for k in K_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append(km.inertia_)

    if len(inertias) < 3:
        return 3

    # Second derivative (rate of change of rate of change)
    diffs = np.diff(inertias)
    diffs2 = np.diff(diffs)

    # Optimal K is where the second derivative is maximum (elbow point)
    optimal_idx = np.argmax(np.abs(diffs2)) + 2  # +2 because of double diff offset
    optimal_k = list(K_range)[min(optimal_idx, len(K_range) - 1)]

    return max(2, min(optimal_k, max_k))


def _generate_cluster_label(profile, existing_profiles, features) -> str:
    """Generate a human-readable label for a cluster."""
    labels = [
        "Champions", "High Value", "Growing", "Average",
        "At Risk", "Low Activity", "New", "Dormant",
    ]
    idx = profile["cluster_id"]
    return labels[idx % len(labels)]


def _calculate_feature_importance(X_scaled, labels, feature_names) -> list[dict]:
    """Calculate feature importance based on between-cluster variance."""
    n_features = X_scaled.shape[1]
    importances = []

    overall_var = np.var(X_scaled, axis=0)

    for i, name in enumerate(feature_names):
        # Between-cluster variance for this feature
        cluster_means = []
        for cluster in np.unique(labels):
            cluster_means.append(np.mean(X_scaled[labels == cluster, i]))
        between_var = np.var(cluster_means)
        total_var = overall_var[i] if overall_var[i] > 0 else 1

        importances.append({
            "feature": name,
            "importance": round(float(between_var / total_var), 3),
        })

    importances.sort(key=lambda x: x["importance"], reverse=True)
    return importances


def _rfm_segment_label(total_score: int, max_score: int) -> str:
    """Map RFM total score to a segment label."""
    ratio = total_score / max_score
    if ratio >= 0.85:
        return "Champions"
    elif ratio >= 0.70:
        return "Loyal Customers"
    elif ratio >= 0.55:
        return "Potential Loyalists"
    elif ratio >= 0.40:
        return "At Risk"
    elif ratio >= 0.25:
        return "Needs Attention"
    else:
        return "Lost"
