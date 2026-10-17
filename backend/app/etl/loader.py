import pandas as pd
from app.core.exceptions import BadRequestException

def load_csv(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path, low_memory=False)
    except pd.errors.EmptyDataError:
        raise BadRequestException("The CSV file is empty")
    except pd.errors.ParserError:
        raise BadRequestException("The CSV file could not be parsed — check formatting")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, low_memory=False, encoding="latin1")

    if df.empty:
        raise BadRequestException("The CSV file has no rows")

    if len(df.columns) == 0:
        raise BadRequestException("The CSV file has no columns")

    if len(df.columns) > 200:
        raise BadRequestException("The CSV file has too many columns (max 200 supported)")

    return df