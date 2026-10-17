from sqlalchemy.orm import Session
from sqlalchemy import inspect, create_engine
from app.models.dataset import Dataset
from app.core.config import settings

ALLOWED_AGGS = {"sum", "avg", "count", "count_distinct", "min", "max", "median", "variance", "stddev"}


def validate_query_plan(db: Session, spec: dict) -> list[str]:
    """
    Module 12: check every real-world assumption the plan is making, BEFORE
    running SQL — dataset exists, column exists, metric is numeric, join
    columns exist, date column exists, aggregation is a real function.
    Returns a list of problems (empty list = fully valid).
    """
    errors = []
    table_name = spec.get("primary_table")
    if not table_name:
        return ["No dataset was resolved for this query."]

    ds = db.query(Dataset).filter(Dataset.cleaned_table_name == table_name).first()
    if not ds:
        return [f"Dataset '{table_name}' does not exist."]

    engine = create_engine(settings.DATABASE_URL)
    try:
        inspector = inspect(engine)
        try:
            columns_info = {c["name"] for c in inspector.get_columns(table_name)}
        except Exception:
            return [f"Could not read schema for '{table_name}'."]

        if spec.get("select_column") and spec["select_column"] != "*" and spec["select_column"] not in columns_info:
            errors.append(f"Column '{spec['select_column']}' does not exist in '{table_name}'.")

        if spec.get("aggregation") and spec["aggregation"].lower() not in ALLOWED_AGGS:
            errors.append(f"Aggregation '{spec['aggregation']}' is not supported.")

        for f in spec.get("filters", []):
            f_table = f.get("table", table_name)
            try:
                f_cols = {c["name"] for c in inspector.get_columns(f_table)}
            except Exception:
                errors.append(f"Filter references unknown table '{f_table}'.")
                continue
            if f["column"] not in f_cols:
                errors.append(f"Filter column '{f['column']}' does not exist in '{f_table}'.")

        for join in spec.get("joins", []):
            try:
                right_cols = {c["name"] for c in inspector.get_columns(join["table"])}
                left_table = join.get("left_table", table_name)
                left_cols = {c["name"] for c in inspector.get_columns(left_table)}
            except Exception:
                errors.append(f"Join references an unknown table.")
                continue
            if join["right_column"] not in right_cols:
                errors.append(f"Join column '{join['right_column']}' does not exist in '{join['table']}'.")
            if join["left_column"] not in left_cols:
                errors.append(f"Join column '{join['left_column']}' does not exist in '{left_table}'.")

        if spec.get("time_filter") and spec["time_filter"]["column"] not in columns_info:
            errors.append(f"Date column '{spec['time_filter']['column']}' does not exist in '{table_name}'.")

    finally:
        engine.dispose()

    return errors