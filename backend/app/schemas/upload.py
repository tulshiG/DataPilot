from pydantic import BaseModel
from datetime import datetime

class DatasetOut(BaseModel):
    id: int
    workspace_id: int
    original_filename: str
    file_size: int
    row_count: int | None
    column_count: int | None
    is_processed: int
    original_row_count: int | None = None
    rows_removed: int = 0
    created_at: datetime

    class Config:
        from_attributes = True