from sqlalchemy.orm import Session
from app.models.knowledge_base import BusinessEntity
from app.schemas.knowledge_base import EntityCreate

def create_entity(db: Session, workspace_id: int, data: EntityCreate) -> BusinessEntity:
    entity = BusinessEntity(workspace_id=workspace_id, **data.model_dump())
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity

def get_entities(db: Session, workspace_id: int) -> list[BusinessEntity]:
    return db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()