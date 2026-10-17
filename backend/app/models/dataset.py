from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, BigInteger, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.user import User

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # rows_removed = Column(Integer, default=0, nullable=False)
    # New fields for ETL
    cleaned_table_name = Column(String(150), nullable=True)
    is_processed = Column(Integer, default=0)  # 0 = not processed, 1 = processed
    profile_json = Column(JSON, nullable=True)

    workspace = relationship("Workspace", back_populates="datasets")
    uploader = relationship("User")

    # Cascades
    etl_logs = relationship("ETLLog", cascade="all, delete-orphan", back_populates="dataset")
    entities = relationship("BusinessEntity", cascade="all, delete-orphan", back_populates="dataset")
    metrics = relationship("BusinessMetric", cascade="all, delete-orphan", back_populates="dataset")
    primary_key_entry = relationship("DatasetPrimaryKey", cascade="all, delete-orphan", back_populates="dataset")
    
    # Relationships where this dataset is the source or target
    source_relationships = relationship("DatasetRelationship", foreign_keys="DatasetRelationship.source_dataset_id", cascade="all, delete-orphan", back_populates="source_dataset")
    target_relationships = relationship("DatasetRelationship", foreign_keys="DatasetRelationship.target_dataset_id", cascade="all, delete-orphan", back_populates="target_dataset")
    
    @property
    def original_row_count(self) -> int | None:
        """Returns the initial row count before cleaning, by checking ETL logs."""
        sorted_logs = sorted(self.etl_logs, key=lambda l: l.id, reverse=True)
        for log in sorted_logs:
            if log.rows_before is not None:
                return log.rows_before
        return self.row_count

    @property
    def rows_removed(self) -> int:
        """Returns the difference in rows between initial and final steps."""
        sorted_logs = sorted(self.etl_logs, key=lambda l: l.id, reverse=True)
        for log in sorted_logs:
            if log.rows_before is not None and log.rows_after is not None:
                return log.rows_before - log.rows_after
        return 0
