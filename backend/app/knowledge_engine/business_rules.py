from sqlalchemy.orm import Session
from app.models.knowledge_base import BusinessRule
from app.schemas.knowledge_base import RuleCreate

def create_rule(db: Session, workspace_id: int, data: RuleCreate) -> BusinessRule:
    rule = BusinessRule(workspace_id=workspace_id, **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

def get_rules(db: Session, workspace_id: int) -> list[BusinessRule]:
    return db.query(BusinessRule).filter(BusinessRule.workspace_id == workspace_id).all()