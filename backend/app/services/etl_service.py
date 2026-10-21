from sqlalchemy.orm import Session
from datetime import datetime, timezone
import pandas as pd

from app.models.dataset import Dataset
from app.models.etl_log import ETLLog
from app.models.relationship import DatasetRelationship, DatasetPrimaryKey
from app.etl.loader import load_csv
from app.etl.cleaner import handle_missing_values, remove_duplicates
from app.etl.normalizer import normalize_column_names, normalize_text_values
from app.etl.transformer import detect_date_columns, convert_data_types
from app.etl.validator import validate_dataset
from app.etl.profiler import profile_dataframe
from app.etl.postgres_loader import save_dataframe_to_postgres
from app.relationship_engine.detector import detect_primary_key, detect_foreign_keys
from app.relationship_engine.schema_mapper import load_dataset_dataframe
from app.visualization_engine.dashboard_generator import generate_dashboard
from app.core.exceptions import NotFoundException, BadRequestException
from app.nlp_engine.indexer import build_nlp_index

def _get_other_workspace_datasets(db: Session, workspace_id: int, current_dataset_id: int) -> list[dict]:
    other_datasets = []
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
        Dataset.id != current_dataset_id
    ).all()
    
    for ds in datasets:
        try:
            df = load_dataset_dataframe(ds.cleaned_table_name)
            pk = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == ds.id).first()
            other_datasets.append({
                "name": ds.cleaned_table_name,
                "dataset_id": ds.id,
                "df": df,
                "primary_key": pk.column_name if pk else None
            })
        except Exception:
            pass
    return other_datasets

def run_etl_pipeline(db: Session, dataset_id: int) -> dict:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise NotFoundException("Dataset")

    log = ETLLog(dataset_id=dataset_id, status="running", stage="data_ingestion")
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        # 1. Data Ingestion
        df = load_csv(dataset.file_path)
        rows_before = len(df)
        
        # 2. Data Validation
        log.stage = "data_validation"
        db.commit()
        validation_report = validate_dataset(df)
        
        # 3. Data Preprocessing
        log.stage = "data_preprocessing"
        db.commit()
        # Missing Value Handling & Duplicate Detection
        df, cleaning_report = handle_missing_values(df)
        df, duplicates_removed = remove_duplicates(df)
        # Invalid Data Correction & Data Type Conversion
        date_columns = detect_date_columns(df)
        df = convert_data_types(df, date_columns)
        # Standardization & Normalization
        df = normalize_column_names(df)
        df = normalize_text_values(df)
        
        # 4. Data Profiling
        log.stage = "data_profiling"
        db.commit()
        profile = profile_dataframe(df)

        # 5. Data Transformation
        log.stage = "data_transformation"
        db.commit()
        # Features & data formatting are currently covered by previous pipeline steps
        
        # 6. Relationship Discovery
        log.stage = "relationship_discovery"
        db.commit()
        pk_info = detect_primary_key(df)
        primary_key = pk_info.get("primary_key")
        
        other_datasets = _get_other_workspace_datasets(db, dataset.workspace_id, dataset.id)
        fk_relationships = detect_foreign_keys(df, dataset.original_filename, other_datasets)
        
        # 7. Data Modeling
        log.stage = "data_modeling"
        db.commit()
        if primary_key:
            pk_record = DatasetPrimaryKey(
                dataset_id=dataset.id,
                workspace_id=dataset.workspace_id,
                column_name=primary_key,
                confidence=pk_info.get("confidence", "low")
            )
            db.add(pk_record)
        
        for fk in fk_relationships:
            target_ds = next((d for d in other_datasets if d["name"] == fk["target_dataset"]), None)
            if target_ds:
                rel = DatasetRelationship(
                    workspace_id=dataset.workspace_id,
                    source_dataset_id=dataset.id,
                    target_dataset_id=target_ds["dataset_id"],
                    source_column=fk["source_column"],
                    target_column=fk["target_column"],
                    confidence=fk["match_confidence"]
                )
                db.add(rel)
        db.commit()
        
        # 8. Load into PostgreSQL
        log.stage = "load_postgresql"
        db.commit()
        table_name = save_dataframe_to_postgres(df, dataset.id, dataset.original_filename)
        dataset.cleaned_table_name = table_name
        dataset.is_processed = 1
        dataset.row_count = len(df)
        dataset.column_count = len(df.columns)
        dataset.original_row_count = rows_before
        dataset.rows_removed = duplicates_removed

        dataset.profile_json = profile
        db.commit()
       
        build_nlp_index(db, dataset.id)
        # 9. Knowledge Base
        log.stage = "knowledge_base"
        db.commit()
        from app.knowledge_engine.populator import populate_knowledge_base
        populate_knowledge_base(db, dataset.id)
            
        # 10. NLP Query Engine
        log.stage = "nlp_query_engine"
        db.commit()
        from app.nlp_engine.indexer import build_nlp_index
        build_nlp_index(db, dataset.id)

        # ---- NEW: AI Pipeline Steps (v2) ----

        # 11. Metadata Layer Population
        log.stage = "metadata_population"
        db.commit()
        try:
            from app.metadata.registry import populate_metadata_for_dataset
            populate_metadata_for_dataset(db, dataset.id)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"Metadata population non-fatal error: {e}")

        # 12. Vector Embedding Generation
        log.stage = "vector_embedding"
        db.commit()
        try:
            from app.vector_engine.schema_embedder import embed_dataset_schema
            embed_dataset_schema(db, dataset.id)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"Vector embedding non-fatal error: {e}")

        # 13. RAG Index Building
        log.stage = "rag_index"
        db.commit()
        try:
            from app.rag_engine.rag_indexer import build_rag_index
            build_rag_index(db, dataset.workspace_id)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"RAG index build non-fatal error: {e}")

        # 14. Semantic Layer Population
        log.stage = "semantic_layer"
        db.commit()
        try:
            from app.semantic_layer.auto_populator import auto_populate_semantic_layer
            auto_populate_semantic_layer(db, dataset.id)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"Semantic layer non-fatal error: {e}")

        # 15. Knowledge Graph Building
        log.stage = "knowledge_graph"
        db.commit()
        try:
            from app.knowledge_graph.graph_manager import build_graph
            build_graph(db, dataset.workspace_id)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"Knowledge graph non-fatal error: {e}")

        # ---- End AI Pipeline Steps ----

        # 16. Dashboard & Business Insights
        log.stage = "dashboard_business_insights"
        db.commit()
        try:
            generate_dashboard(db, dataset.workspace_id, filters=None)
        except Exception as e:
            import logging
            logging.error(f"Generate dashboard non-fatal error: {e}")

        # Finalize log
        log.status = "success"
        log.stage = "completed"
        log.rows_before = rows_before
        log.rows_after = len(df)
        log.message = f"18-Step AI Pipeline completed successfully. {duplicates_removed} duplicate(s) removed."
        log.finished_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "dataset_id": dataset.id,
            "status": "success",
            "rows_before": rows_before,
            "rows_after": len(df),
            "duplicates_removed": duplicates_removed,
            "date_columns_detected": date_columns,
            "validation": validation_report,
            "cleaning_report": cleaning_report,
            "cleaned_table_name": table_name,
        }

    except Exception as e:
        log.status = "failed"
        log.message = str(e)
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise BadRequestException(f"Pipeline failed at stage '{log.stage}': {str(e)}")


def get_etl_logs(db: Session, dataset_id: int) -> list[ETLLog]:
    return db.query(ETLLog).filter(ETLLog.dataset_id == dataset_id).order_by(ETLLog.started_at.desc()).all()
