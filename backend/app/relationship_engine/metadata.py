import pandas as pd
from sqlalchemy.orm import Session
from app.models.dataset import Dataset
from app.models.relationship import DatasetPrimaryKey
from app.relationship_engine.schema_mapper import load_dataset_dataframe

def generate_data_dictionary(db: Session, workspace_id: int) -> dict:
    """
    Build a full metadata dictionary for every processed dataset in the workspace:
    column names, types, null %, sample values, and PK/FK flags.
    """
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
    ).all()

    dictionary = {"workspace_id": workspace_id, "datasets": []}

    for ds in datasets:
        df = load_dataset_dataframe(ds.cleaned_table_name)
        pk_entry = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == ds.id).first()
        pk_column = pk_entry.column_name if pk_entry else None

        columns_meta = []
        for col in df.columns:
            series = df[col]
            sample_values = series.dropna().astype(str).unique()[:3].tolist()

            columns_meta.append({
                "column_name": col,
                "data_type": str(series.dtype),
                "is_primary_key": col == pk_column,
                "null_percent": round(float(series.isnull().mean() * 100), 2),
                "unique_count": int(series.nunique()),
                "sample_values": sample_values,
            })

        dictionary["datasets"].append({
            "dataset_id": ds.id,
            "dataset_name": ds.original_filename,
            "table_name": ds.cleaned_table_name,
            "row_count": ds.row_count,
            "column_count": ds.column_count,
            "primary_key": pk_column,
            "columns": columns_meta,
        })

    return dictionary