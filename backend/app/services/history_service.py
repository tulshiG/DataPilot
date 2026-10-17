from sqlalchemy.orm import Session
from app.models.query_history import QueryHistory


def log_query(
    db: Session,
    workspace_id: int,
    user_id: int,
    raw_query: str,
    intent: str | None,
    sql: str | None,
    spec: dict | None,
    status: str,
    error_message: str | None = None,
    row_count: int | None = None,
) -> QueryHistory:
    entry = QueryHistory(
        workspace_id=workspace_id,
        user_id=user_id,
        raw_query=raw_query,
        detected_intent=intent,
        generated_sql=sql,
        query_spec=spec,
        status=status,
        error_message=error_message,
        result_row_count=row_count,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_query_history(db: Session, workspace_id: int, limit: int = 50) -> list[QueryHistory]:
    return (
        db.query(QueryHistory)
        .filter(QueryHistory.workspace_id == workspace_id)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit)
        .all()
    )