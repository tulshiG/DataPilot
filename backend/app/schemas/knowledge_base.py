from pydantic import BaseModel
from typing import Any
from datetime import datetime

class EntityCreate(BaseModel):
    name: str
    dataset_id: int
    identifier_column: str
    description: str | None = None

class EntityOut(EntityCreate):
    id: int
    workspace_id: int
    created_at: datetime
    class Config:
        from_attributes = True


class MetricCreate(BaseModel):
    name: str
    metric_key: str
    dataset_id: int
    column_name: str
    aggregation: str  # sum, avg, count, min, max
    formula: str | None = None
    description: str | None = None

class MetricOut(MetricCreate):
    id: int
    workspace_id: int
    created_at: datetime
    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    trigger_phrase: str
    maps_to_metric_id: int | None = None
    maps_to_entity_id: int | None = None
    rule_logic: dict[str, Any] | None = None
    description: str | None = None

class RuleOut(RuleCreate):
    id: int
    workspace_id: int
    created_at: datetime
    class Config:
        from_attributes = True