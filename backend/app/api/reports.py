from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.report import ReportOut
from app.services import report_service
from app.insight_engine.report_generator import generate_executive_summary

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/summary/{workspace_id}")
def get_executive_summary(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return generate_executive_summary(db, workspace_id)

@router.post("/pdf/{workspace_id}", response_model=ReportOut)
def create_pdf_report(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.create_executive_pdf_report(db, workspace_id, current_user.id)

@router.post("/excel/{workspace_id}", response_model=ReportOut)
def create_excel_report(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.create_executive_excel_report(db, workspace_id, current_user.id)

@router.post("/export/{dataset_id}", response_model=ReportOut)
def export_dataset(dataset_id: int, file_format: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.create_dataset_export(db, dataset_id, current_user.id, file_format)

@router.get("/", response_model=list[ReportOut])
def list_reports(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.get_workspace_reports(db, workspace_id)

@router.get("/download/{report_id}")
def download_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = report_service.get_report_by_id(db, report_id)
    media_types = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "csv": "text/csv"}
    return FileResponse(
        path=report.file_path,
        filename=report.file_name,
        media_type=media_types.get(report.file_format, "application/octet-stream"),
    )