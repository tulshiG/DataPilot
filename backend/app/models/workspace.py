from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="workspaces")

    # Cascades
    datasets = relationship("Dataset", cascade="all, delete-orphan", back_populates="workspace")
    entities = relationship("BusinessEntity", cascade="all, delete-orphan", back_populates="workspace")
    metrics = relationship("BusinessMetric", cascade="all, delete-orphan", back_populates="workspace")
    rules = relationship("BusinessRule", cascade="all, delete-orphan", back_populates="workspace")
    relationships = relationship("DatasetRelationship", cascade="all, delete-orphan", back_populates="workspace")
    primary_keys = relationship("DatasetPrimaryKey", cascade="all, delete-orphan", back_populates="workspace")
    query_history = relationship("QueryHistory", cascade="all, delete-orphan", back_populates="workspace")
    reports = relationship("Report", cascade="all, delete-orphan", back_populates="workspace")