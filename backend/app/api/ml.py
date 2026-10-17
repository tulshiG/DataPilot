"""
API — ML Engine Endpoints
============================
Exposes forecasting, anomaly detection, segmentation, and recommendations
through REST endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dataset import Dataset
from app.core.config import settings
from app.core.exceptions import BadRequestException

import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ML Engine"])


def _load_dataset_df(dataset: Dataset) -> pd.DataFrame:
    """Load a processed dataset from PostgreSQL into a DataFrame."""
    engine = create_engine(settings.DATABASE_URL)
    try:
        table_name = dataset.cleaned_table_name
        if not table_name:
            raise BadRequestException("Dataset not yet processed")
        df = pd.read_sql(f'SELECT * FROM "{table_name}"', engine)
        return df
    finally:
        engine.dispose()


@router.post("/forecast/{dataset_id}")
def run_forecast(
    dataset_id: int,
    date_col: str = Query(..., description="Date column name"),
    value_col: str = Query(..., description="Value column to forecast"),
    periods: int = Query(12, ge=1, le=60, description="Number of future periods"),
    method: str = Query("auto", description="Forecast method: auto|holt_winters|exponential|linear|moving_average"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run time-series forecasting on a dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise BadRequestException("Dataset not found")

    df = _load_dataset_df(dataset)

    if date_col not in df.columns:
        raise BadRequestException(f"Column '{date_col}' not found")
    if value_col not in df.columns:
        raise BadRequestException(f"Column '{value_col}' not found")

    from app.ml_engine.forecasting import run_forecast as _forecast
    result = _forecast(df, date_col, value_col, periods, method)
    result["dataset_id"] = dataset_id
    return result


@router.post("/anomalies/{dataset_id}")
def detect_anomalies(
    dataset_id: int,
    columns: str = Query(None, description="Comma-separated column names (auto-selects numeric if empty)"),
    method: str = Query("auto", description="Detection method: auto|iqr|zscore|isolation_forest|moving_avg"),
    time_col: str = Query(None, description="Time column for time-series anomaly detection"),
    contamination: float = Query(0.05, ge=0.01, le=0.15),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect anomalies/outliers in a dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise BadRequestException("Dataset not found")

    df = _load_dataset_df(dataset)

    col_list = [c.strip() for c in columns.split(",")] if columns else None

    from app.ml_engine.anomaly_detection import detect_anomalies as _detect
    result = _detect(df, col_list, method, contamination, time_col)
    result["dataset_id"] = dataset_id
    return result


@router.post("/segment/{dataset_id}")
def run_segmentation(
    dataset_id: int,
    features: str = Query(None, description="Comma-separated feature columns (auto-selects numeric if empty)"),
    n_clusters: int = Query(None, ge=2, le=10, description="Number of clusters (auto if empty)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run K-Means clustering segmentation on a dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise BadRequestException("Dataset not found")

    df = _load_dataset_df(dataset)

    feature_cols = [c.strip() for c in features.split(",")] if features else None

    from app.ml_engine.segmentation import run_segmentation as _segment
    result = _segment(df, feature_cols, n_clusters)
    result["dataset_id"] = dataset_id
    return result


@router.post("/rfm/{dataset_id}")
def run_rfm(
    dataset_id: int,
    customer_col: str = Query(..., description="Customer/entity ID column"),
    date_col: str = Query(..., description="Transaction date column"),
    amount_col: str = Query(..., description="Transaction amount column"),
    n_segments: int = Query(4, ge=3, le=5, description="Number of RFM score bins"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run RFM (Recency, Frequency, Monetary) analysis."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise BadRequestException("Dataset not found")

    df = _load_dataset_df(dataset)

    for col in [customer_col, date_col, amount_col]:
        if col not in df.columns:
            raise BadRequestException(f"Column '{col}' not found")

    from app.ml_engine.segmentation import run_rfm_analysis
    result = run_rfm_analysis(df, customer_col, date_col, amount_col, n_segments)
    result["dataset_id"] = dataset_id
    return result


@router.get("/recommendations/{workspace_id}")
def get_recommendations(
    workspace_id: int,
    dataset_id: int = Query(None),
    max_items: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get intelligent recommendations for a workspace/dataset."""
    from app.ml_engine.recommendations import generate_recommendations
    return {
        "workspace_id": workspace_id,
        "recommendations": generate_recommendations(db, workspace_id, dataset_id, max_items),
    }


@router.get("/graph/{workspace_id}")
def get_knowledge_graph(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the knowledge graph structure for visualization."""
    try:
        from app.knowledge_graph.graph_manager import get_graph, get_graph_summary, get_relationships, get_table_nodes
        G = get_graph(db, workspace_id)
        return {
            "workspace_id": workspace_id,
            "summary": get_graph_summary(G),
            "tables": get_table_nodes(G),
            "relationships": get_relationships(G),
        }
    except Exception as e:
        return {"error": str(e), "workspace_id": workspace_id}


@router.get("/graph/{workspace_id}/join-path")
def find_join_path(
    workspace_id: int,
    source: str = Query(..., description="Source table name"),
    target: str = Query(..., description="Target table name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find the shortest join path between two tables."""
    try:
        from app.knowledge_graph.graph_manager import get_graph
        from app.knowledge_graph.path_finder import find_join_path as _find_path
        G = get_graph(db, workspace_id)
        result = _find_path(G, source, target)
        if result is None:
            return {"path_found": False, "source": source, "target": target}
        return {"path_found": True, **result}
    except Exception as e:
        return {"error": str(e)}


@router.get("/semantic/{workspace_id}")
def get_semantic_layer(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all semantic metrics and dimensions for a workspace."""
    try:
        from app.semantic_layer.resolver import get_all_metrics, get_all_dimensions
        return {
            "workspace_id": workspace_id,
            "metrics": get_all_metrics(db, workspace_id),
            "dimensions": get_all_dimensions(db, workspace_id),
        }
    except Exception as e:
        return {"error": str(e), "workspace_id": workspace_id}
