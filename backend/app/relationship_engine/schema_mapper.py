import pandas as pd
from sqlalchemy import create_engine
from app.core.config import settings

def load_dataset_dataframe(table_name: str) -> pd.DataFrame:
    """Load a cleaned dataset table from Postgres into a DataFrame for analysis."""
    engine = create_engine(settings.DATABASE_URL)
    df = pd.read_sql_table(table_name, engine)
    engine.dispose()
    return df