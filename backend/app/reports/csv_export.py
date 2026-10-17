import os
import uuid
import pandas as pd
from app.core.constants import REPORTS_DIR

def export_dataset_to_csv(df: pd.DataFrame, dataset_name: str) -> tuple[str, str]:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in dataset_name.rsplit(".", 1)[0])[:40]
    file_name = f"{safe_name}_{uuid.uuid4().hex[:8]}.csv"
    file_path = os.path.join(REPORTS_DIR, file_name)

    df.to_csv(file_path, index=False)
    return file_path, file_name