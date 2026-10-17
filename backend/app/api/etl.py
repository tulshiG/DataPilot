from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.dataset import ETLResult, ETLLogOut
from app.services import etl_service

router = APIRouter(prefix="/etl", tags=["ETL"])

@router.post("/run/{dataset_id}", response_model=ETLResult)
def run_etl(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return etl_service.run_etl_pipeline(db, dataset_id)

@router.get("/logs/{dataset_id}", response_model=list[ETLLogOut])
def get_logs(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return etl_service.get_etl_logs(db, dataset_id)