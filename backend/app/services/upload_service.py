import pandas as pd
from sqlalchemy.orm import Session
from fastapi import UploadFile
from app.models.dataset import Dataset
from app.utils.file_utils import validate_csv_file, save_upload_file
from app.core.exceptions import BadRequestException

def process_uploaded_files(
    db: Session,
    files: list[UploadFile],
    workspace_id: int,
    user_id: int,
) -> list[Dataset]:
    if not files:
        raise BadRequestException("No files provided")

    saved_datasets = []

    for file in files:
        validate_csv_file(file)
        stored_filename, full_path, file_size = save_upload_file(file, workspace_id)

        # Quick profiling to store row/column counts
        try:
            df = pd.read_csv(full_path)
            row_count = len(df)
            column_count = len(df.columns)
        except Exception:
            row_count, column_count = None, None

        dataset = Dataset(
            workspace_id=workspace_id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_path=full_path,
            file_size=file_size,
            row_count=row_count,
            column_count=column_count,
            uploaded_by=user_id,
        )
        db.add(dataset)
        saved_datasets.append(dataset)

    db.commit()
    for ds in saved_datasets:
        db.refresh(ds)
        
    # Auto-run ETL pipeline for each dataset immediately so they become 'processed'
    from app.services.etl_service import run_etl_pipeline
    import logging
    logger = logging.getLogger(__name__)

    for ds in saved_datasets:
        try:
            run_etl_pipeline(db, ds.id)
            db.refresh(ds)
        except Exception as e:
            logger.error(f"Auto ETL failed for dataset {ds.id}: {e}")

    return saved_datasets

def get_workspace_datasets(db: Session, workspace_id: int) -> list[Dataset]:
    return db.query(Dataset).filter(Dataset.workspace_id == workspace_id).all()