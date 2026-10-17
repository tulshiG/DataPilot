# from pydantic import BaseModel
# from typing import Any
# from datetime import datetime

# class QueryRequest(BaseModel):
#     query: str

# class QueryResult(BaseModel):
#     raw_query: str
#     intent: str
#     matched_rule: str | None
#     generated_sql: str | None
#     columns: list[str]
#     rows: list[dict[str, Any]]
#     row_count: int
#     summary: str

# class QueryHistoryOut(BaseModel):
#     id: int
#     raw_query: str
#     detected_intent: str | None
#     generated_sql: str | None
#     status: str
#     error_message: str | None
#     result_row_count: int | None
#     created_at: datetime

#     class Config:
#         from_attributes = True
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime

class QueryRequest(BaseModel):
    query: str
    dataset_id: int | None = None

# class QueryResult(BaseModel):
#     raw_query: str
#     intent: str
#     matched_rule: str | None
#     generated_sql: str | None
#     columns: list[str]
#     rows: list[dict[str, Any]]
#     row_count: int
#     summary: str
#     # Optional rich payloads for special intents
#     dashboard: Optional[dict[str, Any]] = None
#     insights: Optional[dict[str, Any]] = None
class QueryResult(BaseModel):
    raw_query: str
    intent: str
    matched_rule: str | None = None
    generated_sql: str | None = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    summary: str = ""
    needs_clarification: bool = False
    message: str | None = None
    candidates: list[dict[str, Any]] = []
    confidence: Any = None
    query_plan: dict[str, Any] | None = None
    engine_used: str | None = None
    dashboard: dict[str, Any] | None = None
    insights: dict[str, Any] | None = None
    # Fields returned by nlp_query_service
    llm_reasoning: str | None = None
    session_id: str | None = None
    is_followup: bool = False
    schema_corrections: dict[str, Any] | None = None
    explanation: Any = None
    chart_recommendation: Any = None

class QueryHistoryOut(BaseModel):
    id: int
    raw_query: str
    detected_intent: str | None
    generated_sql: str | None
    status: str
    error_message: str | None
    result_row_count: int | None
    created_at: datetime
    class Config:
        from_attributes = True