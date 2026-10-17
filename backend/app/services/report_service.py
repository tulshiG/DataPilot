from sqlalchemy.orm import Session
from app.models.reports import Report
from app.models.dataset import Dataset
from app.models.workspace import Workspace
from app.insight_engine.report_generator import generate_executive_summary, _load_dataset_df
from app.reports.pdf_generator import generate_pdf_report
from app.reports.excel_export import export_dataset_to_excel, export_summary_to_excel
from app.reports.csv_export import export_dataset_to_csv
from app.core.exceptions import NotFoundException, BadRequestException


def create_executive_pdf_report(db: Session, workspace_id: int, user_id: int) -> Report:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise NotFoundException("Workspace")

    summary = generate_executive_summary(db, workspace_id)
    file_path, file_name = generate_pdf_report(summary, workspace.name)

    report = Report(
        workspace_id=workspace_id, generated_by=user_id,
        report_type="executive_summary", file_format="pdf",
        file_path=file_path, file_name=file_name,
        summary_snapshot=summary,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def create_executive_excel_report(db: Session, workspace_id: int, user_id: int) -> Report:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise NotFoundException("Workspace")

    summary = generate_executive_summary(db, workspace_id)
    file_path, file_name = export_summary_to_excel(summary, workspace.name)

    report = Report(
        workspace_id=workspace_id, generated_by=user_id,
        report_type="executive_summary", file_format="xlsx",
        file_path=file_path, file_name=file_name,
        summary_snapshot=summary,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def create_dataset_export(db: Session, dataset_id: int, user_id: int, file_format: str) -> Report:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.is_processed:
        raise NotFoundException("Processed dataset")

    df = _load_dataset_df(dataset.cleaned_table_name)

    if file_format == "csv":
        file_path, file_name = export_dataset_to_csv(df, dataset.original_filename)
    elif file_format == "xlsx":
        file_path, file_name = export_dataset_to_excel(df, dataset.original_filename)
    else:
        raise BadRequestException("Unsupported format. Use 'csv' or 'xlsx'.")

    report = Report(
        workspace_id=dataset.workspace_id, generated_by=user_id,
        report_type="dataset_export", file_format=file_format,
        file_path=file_path, file_name=file_name,
        summary_snapshot=None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_workspace_reports(db: Session, workspace_id: int) -> list[Report]:
    return db.query(Report).filter(Report.workspace_id == workspace_id).order_by(Report.created_at.desc()).all()


def get_report_by_id(db: Session, report_id: int) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise NotFoundException("Report")
    return report