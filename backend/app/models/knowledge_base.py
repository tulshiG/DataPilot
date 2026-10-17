from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship as orm_relationship
from app.database.base import Base
from app.models.workspace import Workspace

class BusinessEntity(Base):
    """
    Represents a real-world business concept (Customer, Order, Product, etc.)
    mapped to one or more datasets/columns.
    """
    __tablename__ = "business_entities"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(100), nullable=False)          # e.g. "Customer"
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    identifier_column = Column(String(150), nullable=False)  # the PK representing this entity
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = orm_relationship("Dataset")
    workspace = orm_relationship("Workspace", back_populates="entities")


class BusinessMetric(Base):
    """
    Represents a calculable business metric (Revenue, Profit, Stock Level, Order Count).
    Stores which dataset/column(s) and aggregation to use.
    """
    __tablename__ = "business_metrics"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(100), nullable=False)              # e.g. "Total Revenue"
    metric_key = Column(String(100), nullable=False)        # e.g. "revenue" — used in NLP mapping
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    column_name = Column(String(150), nullable=False)        # e.g. "total_amount"
    aggregation = Column(String(20), nullable=False)         # sum, avg, count, min, max
    formula = Column(Text, nullable=True)                    # optional: "price * quantity"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = orm_relationship("Dataset")
    workspace = orm_relationship("Workspace", back_populates="metrics")


class BusinessRule(Base):
    """
    Rule-based mapping for common query phrasing -> metric/entity resolution.
    Used by the NLP engine (Day 4) to interpret vague business questions.
    """
    __tablename__ = "business_rules"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    trigger_phrase = Column(String(200), nullable=False)     # e.g. "best selling product"
    maps_to_metric_id = Column(Integer, ForeignKey("business_metrics.id"), nullable=True)
    maps_to_entity_id = Column(Integer, ForeignKey("business_entities.id"), nullable=True)
    rule_logic = Column(JSON, nullable=True)                 # e.g. {"sort_by": "quantity", "order": "desc", "limit": 1}
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    metric = orm_relationship("BusinessMetric")
    entity = orm_relationship("BusinessEntity")
    workspace = orm_relationship("Workspace", back_populates="rules")