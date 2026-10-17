from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge_base import (
    EntityCreate, EntityOut, MetricCreate, MetricOut, RuleCreate, RuleOut,
)
from app.knowledge_engine import entities, metrics, business_rules

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])

@router.post("/entities/{workspace_id}", response_model=EntityOut)
def create_entity(workspace_id: int, data: EntityCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return entities.create_entity(db, workspace_id, data)

@router.get("/entities/{workspace_id}", response_model=list[EntityOut])
def list_entities(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return entities.get_entities(db, workspace_id)

@router.post("/metrics/{workspace_id}", response_model=MetricOut)
def create_metric(workspace_id: int, data: MetricCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return metrics.create_metric(db, workspace_id, data)

@router.get("/metrics/{workspace_id}", response_model=list[MetricOut])
def list_metrics(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return metrics.get_metrics(db, workspace_id)

@router.get("/metrics/value/{metric_id}")
def get_metric_value(metric_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return metrics.calculate_metric_value(db, metric_id)

@router.post("/rules/{workspace_id}", response_model=RuleOut)
def create_rule(workspace_id: int, data: RuleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return business_rules.create_rule(db, workspace_id, data)

@router.get("/rules/{workspace_id}", response_model=list[RuleOut])
def list_rules(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return business_rules.get_rules(db, workspace_id)