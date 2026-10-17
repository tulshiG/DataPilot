from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from app.models.knowledge_base import BusinessMetric
from app.schemas.knowledge_base import MetricCreate
from app.core.config import settings
from app.core.exceptions import BadRequestException

ALLOWED_AGGREGATIONS = {"sum", "avg", "count", "min", "max"}

def create_metric(db: Session, workspace_id: int, data: MetricCreate) -> BusinessMetric:
    if data.aggregation.lower() not in ALLOWED_AGGREGATIONS:
        raise BadRequestException(f"Aggregation must be one of {ALLOWED_AGGREGATIONS}")

    metric = BusinessMetric(workspace_id=workspace_id, **data.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric

def get_metrics(db: Session, workspace_id: int) -> list[BusinessMetric]:
    return db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()

def calculate_metric_value(db: Session, metric_id: int) -> dict:
    """Actually compute the metric's current value against the cleaned Postgres table."""
    metric = db.query(BusinessMetric).filter(BusinessMetric.id == metric_id).first()
    if not metric:
        raise BadRequestException("Metric not found")

    table_name = metric.dataset.cleaned_table_name
    agg = metric.aggregation.lower()

    engine = create_engine(settings.DATABASE_URL)
    try:
        query = text(f'SELECT {agg}("{metric.column_name}") as value FROM "{table_name}"')
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()
            value = float(result[0]) if result and result[0] is not None else None
    finally:
        engine.dispose()

    return {"metric_name": metric.name, "value": value, "aggregation": agg}