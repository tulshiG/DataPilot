from sqlalchemy.orm import Session
from app.models.dataset import Dataset
from app.models.knowledge_base import BusinessEntity, BusinessMetric
import pandas as pd
from sqlalchemy import create_engine, inspect
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def populate_knowledge_base(db: Session, dataset_id: int):
    """
    Auto-detects and populates the Knowledge Base (Business entities & metrics) 
    from the processed dataset in PostgreSQL.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset or not dataset.cleaned_table_name:
        return
        
    engine = create_engine(settings.DATABASE_URL)
    try:
        inspector = inspect(engine)
        if not inspector.has_table(dataset.cleaned_table_name):
            return
            
        columns = inspector.get_columns(dataset.cleaned_table_name)
        
        # Determine metrics vs entities
        for col in columns:
            col_name = col["name"]
            type_str = str(col["type"]).upper()
            
            # Simple heuristic
            if "INT" in type_str or "FLOAT" in type_str or "NUMERIC" in type_str or "REAL" in type_str:
                if "id" not in col_name.lower():
                    # Create metric if not exists
                    exists = db.query(BusinessMetric).filter(
                        BusinessMetric.dataset_id == dataset.id,
                        BusinessMetric.column_name == col_name
                    ).first()
                    if not exists:
                        m = BusinessMetric(
                            workspace_id=dataset.workspace_id,
                            dataset_id=dataset.id,
                            name=col_name.replace("_", " ").title(),
                            metric_key=col_name.replace("_", " "),
                            column_name=col_name,
                            aggregation="sum"
                        )
                        db.add(m)
            elif "CHAR" in type_str or "TEXT" in type_str:
                if df_cardinality_check(engine, dataset.cleaned_table_name, col_name):
                     exists = db.query(BusinessEntity).filter(
                        BusinessEntity.dataset_id == dataset.id,
                        BusinessEntity.identifier_column == col_name
                     ).first()
                     if not exists:
                         e = BusinessEntity(
                             workspace_id=dataset.workspace_id,
                             dataset_id=dataset.id,
                             name=col_name.replace("_", " ").title(),
                             identifier_column=col_name
                         )
                         db.add(e)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to populate knowledge base: {e}")
    finally:
        engine.dispose()

def df_cardinality_check(engine, table_name, col_name) -> bool:
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            res = conn.execute(text(f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"')).fetchone()
            unique_count = res[0]
            # If unique count is small enough, treat as an entity dimension
            return unique_count < 1000
    except:
        return False
