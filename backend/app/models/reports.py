from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    report_type = Column(String(30), nullable=False)   # executive_summary, dataset_export
    file_format = Column(String(10), nullable=False)   # pdf, xlsx, csv
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    summary_snapshot = Column(JSON, nullable=True)      # store the data used, for reference

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace", back_populates="reports")
    user = relationship("User")