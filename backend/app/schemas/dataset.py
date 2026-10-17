from pydantic import BaseModel
from datetime import datetime
from typing import Any

class ETLResult(BaseModel):
    dataset_id: int
    status: str
    rows_before: int
    rows_after: int
    duplicates_removed: int
    date_columns_detected: list[str]
    validation: dict[str, Any]
    cleaning_report: dict[str, Any] | None = None
    cleaned_table_name: str

class ProfileOut(BaseModel):
    row_count: int
    column_count: int
    columns: list[dict[str, Any]]

class ETLLogOut(BaseModel):
    id: int
    dataset_id: int
    status: str
    stage: str | None
    message: str | None
    rows_before: int | None
    rows_after: int | None
    started_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True