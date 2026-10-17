"""
Metadata Layer — SQLAlchemy Models
===================================
Structured metadata models that provide a single source of truth about every
table and column in the data warehouse.

Why this module exists:
    The current system stores metadata in two disconnected places:
    1. ``profile_json["nlp_index"]`` — a flat JSON blob per dataset
    2. ``BusinessEntity`` / ``BusinessMetric`` — ORM models that don't
       reference column statistics or semantic types

    This unified layer connects column stats, semantic types, descriptions,
    and quality scores so every downstream module (RAG, Query Planner, LLM)
    can get complete context from one place.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship as orm_relationship

from app.database.base import Base


class ColumnMetadata(Base):
    """
    Rich metadata for a single column in a dataset.

    Populated during ETL alongside the existing ``nlp_index``, but stored
    as proper relational rows instead of a JSON blob — making it queryable,
    joinable, and individually updatable.
    """
    __tablename__ = "column_metadata"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)
    table_name = Column(String(200), nullable=False)
    column_name = Column(String(200), nullable=False)

    # Data classification
    data_type = Column(String(50), nullable=True)         # e.g., "int64", "object", "datetime64"
    semantic_type = Column(String(50), nullable=True)      # e.g., "currency", "geographic", "identifier", "temporal", "categorical", "numeric_measure"
    is_metric = Column(Boolean, default=False)             # Is this column a measurable value?
    is_dimension = Column(Boolean, default=False)          # Is this column a grouping dimension?
    is_identifier = Column(Boolean, default=False)         # Is this a PK / FK / ID column?
    is_temporal = Column(Boolean, default=False)           # Is this a date/time column?

    # Column statistics
    distinct_count = Column(Integer, nullable=True)
    null_percentage = Column(Float, nullable=True)
    min_value = Column(String(200), nullable=True)
    max_value = Column(String(200), nullable=True)
    mean_value = Column(Float, nullable=True)
    sample_values = Column(JSON, nullable=True)            # list of up to 5 sample values

    # Human-readable context
    description = Column(Text, nullable=True)              # Auto-generated or user-edited
    synonyms = Column(JSON, nullable=True)                 # list of synonym strings

    # Quality
    quality_score = Column(Float, nullable=True)           # 0-100 composite quality score

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dataset = orm_relationship("Dataset")


class TableMetadata(Base):
    """
    Table-level metadata: row count, column count, domain, quality summary.
    """
    __tablename__ = "table_metadata"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)
    table_name = Column(String(200), nullable=False, unique=True)
    original_filename = Column(String(300), nullable=True)

    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    domain = Column(String(100), nullable=True)            # e.g., "sales", "healthcare", "education"
    description = Column(Text, nullable=True)
    quality_score = Column(Float, nullable=True)           # 0-100 composite quality

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dataset = orm_relationship("Dataset")
