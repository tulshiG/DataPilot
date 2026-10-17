from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship as orm_relationship
from app.database.base import Base


class DatasetRelationship(Base):
    __tablename__ = "dataset_relationships"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)

    source_dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    source_column = Column(String(150), nullable=False)

    target_dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    target_column = Column(String(150), nullable=False)

    confidence = Column(String(20), nullable=False)           # high, medium, low
    value_overlap_percent = Column(Float, nullable=True)
    is_validated = Column(String(20), default="pending")      # pending, valid, invalid
    validation_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_dataset = orm_relationship("Dataset", foreign_keys=[source_dataset_id], back_populates="source_relationships")
    target_dataset = orm_relationship("Dataset", foreign_keys=[target_dataset_id], back_populates="target_relationships")
    workspace = orm_relationship("Workspace", back_populates="relationships")


class DatasetPrimaryKey(Base):
    __tablename__ = "dataset_primary_keys"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, unique=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    column_name = Column(String(150), nullable=False)
    confidence = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = orm_relationship("Dataset", back_populates="primary_key_entry")
    workspace = orm_relationship("Workspace", back_populates="primary_keys")