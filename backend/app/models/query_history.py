from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    # workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    raw_query = Column(Text, nullable=False)
    detected_intent = Column(String(50), nullable=True)
    generated_sql = Column(Text, nullable=True)
    query_spec = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default="success")  # success, failed
    error_message = Column(Text, nullable=True)
    result_row_count = Column(Integer, nullable=True)

    # created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace", back_populates="query_history")
    user = relationship("User")