from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.visualization_engine.dashboard_generator import generate_dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/{workspace_id}", response_model=DashboardResponse)
def get_dashboard(
    workspace_id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    date_column: str | None = Query(None),
    category_column: str | None = Query(None),
    category_value: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "date_column": date_column,
        "category_column": category_column,
        "category_value": category_value,
    }
    return generate_dashboard(db, workspace_id, filters)