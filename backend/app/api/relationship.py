from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dataset import Dataset
from app.models.relationship import DatasetRelationship, DatasetPrimaryKey
from app.schemas.relationship import (
    DiscoverResponse, RelationshipOut, ValidateResponse, DiagramResponse,
    DiagramNode, DiagramEdge,
)
from app.relationship_engine.graph_builder import discover_relationships, validate_relationship
from app.relationship_engine.metadata import generate_data_dictionary

router = APIRouter(prefix="/relationships", tags=["Relationships"])

@router.post("/discover/{workspace_id}", response_model=DiscoverResponse)
def discover(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = discover_relationships(db, workspace_id)
    return {
        "datasets_analyzed": result["datasets_analyzed"],
        "primary_keys": result["primary_keys"],
        "relationships_found": result["relationships_found"],
    }

@router.get("/{workspace_id}", response_model=list[RelationshipOut])
def list_relationships(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(DatasetRelationship).filter(DatasetRelationship.workspace_id == workspace_id).all()

@router.post("/validate/{relationship_id}", response_model=ValidateResponse)
def validate(
    relationship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return validate_relationship(db, relationship_id)

@router.get("/diagram/{workspace_id}", response_model=DiagramResponse)
def get_diagram(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
    ).all()
    relationships = db.query(DatasetRelationship).filter(
        DatasetRelationship.workspace_id == workspace_id
    ).all()

    nodes = []
    for ds in datasets:
        pk_entry = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == ds.id).first()
        nodes.append(DiagramNode(
            id=ds.id,
            label=ds.original_filename,
            primary_key=pk_entry.column_name if pk_entry else None,
        ))

    edges = [
        DiagramEdge(
            source=rel.source_dataset_id,
            target=rel.target_dataset_id,
            source_column=rel.source_column,
            target_column=rel.target_column,
            confidence=rel.confidence,
            validated=rel.is_validated,
        )
        for rel in relationships
    ]

    return DiagramResponse(nodes=nodes, edges=edges)

@router.get("/dictionary/{workspace_id}")
def data_dictionary(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return generate_data_dictionary(db, workspace_id)