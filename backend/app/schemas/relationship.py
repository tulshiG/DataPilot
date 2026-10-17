from pydantic import BaseModel
from typing import Any
from datetime import datetime

class DiscoverResponse(BaseModel):
    datasets_analyzed: int
    primary_keys: list[dict[str, Any]]
    relationships_found: int

class RelationshipOut(BaseModel):
    id: int
    source_dataset_id: int
    source_column: str
    target_dataset_id: int
    target_column: str
    confidence: str
    value_overlap_percent: float | None
    is_validated: str
    validation_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class ValidateResponse(BaseModel):
    relationship_id: int
    status: str
    message: str

class DiagramNode(BaseModel):
    id: int
    label: str
    primary_key: str | None

class DiagramEdge(BaseModel):
    source: int
    target: int
    source_column: str
    target_column: str
    confidence: str
    validated: str

class DiagramResponse(BaseModel):
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]