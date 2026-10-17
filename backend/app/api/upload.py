from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
import os
from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.upload import DatasetOut
from app.services import upload_service, workspace_service
from app.core.exceptions import NotFoundException

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.dataset import Dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise NotFoundException("Dataset")

    # Remove the raw uploaded file
    if os.path.exists(dataset.file_path):
        os.remove(dataset.file_path)

    # Drop the cleaned Postgres table if ETL was run
    if dataset.cleaned_table_name:
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        engine = create_engine(settings.DATABASE_URL)
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS "{dataset.cleaned_table_name}"'))
        finally:
            engine.dispose()

    db.delete(dataset)
    db.commit()
    return {"detail": "Dataset deleted successfully"}
@router.post("/{workspace_id}", response_model=list[DatasetOut])
def upload_files(
    workspace_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = workspace_service.get_workspace_by_id(db, workspace_id, current_user.id)
    if not workspace:
        raise NotFoundException("Workspace")

    return upload_service.process_uploaded_files(db, files, workspace_id, current_user.id)

@router.get("/{workspace_id}", response_model=list[DatasetOut])
def list_datasets(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return upload_service.get_workspace_datasets(db, workspace_id)