import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from app.models.dataset import Dataset
from app.models.relationship import DatasetRelationship, DatasetPrimaryKey
from app.relationship_engine.detector import detect_primary_key, detect_foreign_keys
from app.relationship_engine.schema_mapper import load_dataset_dataframe
from app.core.config import settings
from app.core.exceptions import BadRequestException


def discover_relationships(db: Session, workspace_id: int) -> dict:
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
    ).all()

    if len(datasets) < 1:
        raise BadRequestException("No processed datasets found in this workspace. Run ETL first.")

    dataset_info = []
    for ds in datasets:
        try:
            df = load_dataset_dataframe(ds.cleaned_table_name)
        except Exception as e:
            raise BadRequestException(f"Could not load dataset '{ds.original_filename}': {str(e)}")

        pk_result = detect_primary_key(df)
        dataset_info.append({
            "id": ds.id, "name": ds.original_filename, "df": df,
            "primary_key": pk_result["primary_key"],
            "pk_confidence": pk_result["confidence"],
        })
        

        # Store/update primary key
        if pk_result["primary_key"]:
            existing_pk = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == ds.id).first()
            if existing_pk:
                existing_pk.column_name = pk_result["primary_key"]
                existing_pk.confidence = pk_result["confidence"]
            else:
                db.add(DatasetPrimaryKey(
                    dataset_id=ds.id,
                    workspace_id=workspace_id,
                    column_name=pk_result["primary_key"],
                    confidence=pk_result["confidence"],
                ))

    db.commit()

    # Clear old relationships for this workspace before re-detecting
    db.query(DatasetRelationship).filter(DatasetRelationship.workspace_id == workspace_id).delete()
    db.commit()

    # Detect foreign keys across all dataset pairs
    all_relationships = []
    for source in dataset_info:
        others = [d for d in dataset_info if d["id"] != source["id"]]
        fks = detect_foreign_keys(source["df"], source["name"], others)

        for fk in fks:
            target = next(d for d in dataset_info if d["name"] == fk["target_dataset"])

            rel = DatasetRelationship(
                workspace_id=workspace_id,
                source_dataset_id=source["id"],
                source_column=fk["source_column"],
                target_dataset_id=target["id"],
                target_column=fk["target_column"],
                confidence=fk["match_confidence"],
                value_overlap_percent=fk["value_overlap_percent"],
                is_validated="pending",
            )
            db.add(rel)
            all_relationships.append(rel)

    db.commit()
    for rel in all_relationships:
        db.refresh(rel)

    return {
        "datasets_analyzed": len(dataset_info),
        "primary_keys": [
            {"dataset": d["name"], "primary_key": d["primary_key"], "confidence": d["pk_confidence"]}
            for d in dataset_info
        ],
        "relationships_found": len(all_relationships),
        "relationships": all_relationships,
    }


def validate_relationship(db: Session, relationship_id: int) -> dict:
    """
    Actually attempt a SQL JOIN between the two tables using the detected keys,
    to confirm the relationship is real and usable.
    """
    rel = db.query(DatasetRelationship).filter(DatasetRelationship.id == relationship_id).first()
    if not rel:
        raise BadRequestException("Relationship not found")

    source_table = rel.source_dataset.cleaned_table_name
    target_table = rel.target_dataset.cleaned_table_name

    engine = create_engine(settings.DATABASE_URL)
    try:
        query = text(f"""
            SELECT COUNT(*) as match_count
            FROM "{source_table}" s
            INNER JOIN "{target_table}" t
            ON s."{rel.source_column}" = t."{rel.target_column}"
            LIMIT 1
        """)
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()
            match_count = result[0] if result else 0

        rel.is_validated = "valid" if match_count > 0 else "invalid"
        rel.validation_message = f"Join produced {match_count} matching row(s)" if match_count > 0 else "Join produced no matches"

    except Exception as e:
        rel.is_validated = "invalid"
        rel.validation_message = f"Join failed: {str(e)}"
    finally:
        engine.dispose()

    db.commit()
    db.refresh(rel)

    return {
        "relationship_id": rel.id,
        "status": rel.is_validated,
        "message": rel.validation_message,
    }