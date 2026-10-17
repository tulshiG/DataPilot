from pydantic import BaseModel
from typing import Any
from datetime import datetime


class ReportOut(BaseModel):
    id: int
    workspace_id: int
    generated_by: int
    report_type: str
    file_format: str
    file_path: str
    file_name: str
    summary_snapshot: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True
