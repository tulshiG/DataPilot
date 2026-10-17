from pydantic import BaseModel
from typing import Any

class DashboardFilter(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    date_column: str | None = None
    category_column: str | None = None
    category_value: str | None = None

class DashboardResponse(BaseModel):
    workspace_id: int
    kpis: list[dict[str, Any]]
    charts: list[dict[str, Any]]
    datasets: list[dict[str, Any]] = []
    generated_at: str