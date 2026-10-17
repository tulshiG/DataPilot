import re
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.types import DateTime  # <-- added
from app.core.config import settings

def _safe_table_name(dataset_id: int, original_filename: str) -> str:
    """Generate a safe, unique Postgres table name for the cleaned dataset."""
    base = re.sub(r"[^\w]", "_", original_filename.rsplit(".", 1)[0].lower())
    base = re.sub(r"_+", "_", base).strip("_")[:40]
    return f"ds_{dataset_id}_{base}"

def save_dataframe_to_postgres(df: pd.DataFrame, dataset_id: int, original_filename: str) -> str:
    """
    Save the cleaned DataFrame into its own Postgres table.
    Returns the table name used.
    """
    table_name = _safe_table_name(dataset_id, original_filename)
    engine = create_engine(settings.DATABASE_URL)

    # Force datetime columns to Postgres TIMESTAMP
    dtypes = {col: DateTime() for col in df.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns}

    df.to_sql(table_name, engine, if_exists="replace", index=False, method="multi", chunksize=1000, dtype=dtypes)
    engine.dispose()

    return table_name