from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base

class ETLLog(Base):
    __tablename__ = "etl_logs"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="pending")  # pending, running, success, failed
    stage = Column(String(50), nullable=True)  # loader, cleaner, normalizer, transformer, validator, profiler, postgres_loader
    message = Column(Text, nullable=True)
    rows_before = Column(Integer, nullable=True)
    rows_after = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    dataset = relationship("Dataset", back_populates="etl_logs")