"""
Semantic Layer — Models
========================
SQLAlchemy model for semantic metric definitions.

A SemanticMetric maps a human-readable metric name (like "total revenue")
to an exact SQL expression (like ``SUM("order_amount")``), along with
metadata about what it means, how to group it, and how to format it.

This replaces ad-hoc metric detection in the NLP pipeline with a
persistent, editable catalog.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from sqlalchemy.orm import relationship

from app.database.base import Base


class SemanticMetric(Base):
    """
    A business metric definition.

    Examples:
        name="Total Revenue", expression="SUM(\"amount\")",
        table_name="sales", column_name="amount"

        name="Profit Margin", expression="(SUM(\"revenue\") - SUM(\"cost\")) / NULLIF(SUM(\"revenue\"), 0) * 100",
        table_name="financials", column_name=None (computed)
    """
    __tablename__ = "semantic_metrics"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)

    # Identification
    name = Column(String(200), nullable=False)
    key = Column(String(100), nullable=False, index=True)  # normalized lookup key
    description = Column(Text, nullable=True)

    # SQL definition
    expression = Column(Text, nullable=False)  # e.g. SUM("amount")
    aggregation = Column(String(30), nullable=True)  # SUM, AVG, COUNT, etc.
    table_name = Column(String(200), nullable=False)
    column_name = Column(String(200), nullable=True)  # None for computed metrics

    # Metadata
    data_type = Column(String(30), default="numeric")  # numeric, percentage, currency, count
    format_pattern = Column(String(50), nullable=True)  # e.g. "$,.2f", ".1%"
    unit = Column(String(50), nullable=True)  # e.g. "USD", "units", "%"

    # Dimension compatibility
    default_dimensions = Column(JSON, nullable=True)  # ["region", "product_category"]
    time_dimension = Column(String(200), nullable=True)  # date column for trends

    # Synonyms for fuzzy matching
    synonyms = Column(JSON, nullable=True)  # ["revenue", "sales amount", "income"]

    # Auto-populated vs user-defined
    is_auto = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    # Quality
    confidence = Column(Float, default=0.8)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SemanticDimension(Base):
    """
    A dimension definition — categorical columns used for GROUP BY.

    Examples:
        name="Region", column_name="region", table_name="sales"
        name="Product Category", column_name="category", table_name="products"
    """
    __tablename__ = "semantic_dimensions"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)

    name = Column(String(200), nullable=False)
    key = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)

    table_name = Column(String(200), nullable=False)
    column_name = Column(String(200), nullable=False)

    # Cardinality info
    distinct_count = Column(Integer, nullable=True)
    sample_values = Column(JSON, nullable=True)

    # Synonyms
    synonyms = Column(JSON, nullable=True)

    # Hierarchy (e.g., city → state → country)
    parent_dimension_key = Column(String(100), nullable=True)

    is_auto = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
