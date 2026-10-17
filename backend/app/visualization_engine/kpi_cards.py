# from sqlalchemy.orm import Session
# from sqlalchemy import create_engine, text
# from app.models.knowledge_base import BusinessMetric
# from app.models.dataset import Dataset
# from app.core.config import settings
# import pandas as pd


# def generate_kpi_cards(db: Session, workspace_id: int) -> list[dict]:
#     """
#     Compute KPI cards for the workspace.
#     First tries registered BusinessMetrics.
#     If none exist, auto-generates KPIs from the processed datasets' numeric columns.
#     """
#     metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()

#     engine = create_engine(settings.DATABASE_URL)
#     cards = []

#     try:
#         with engine.connect() as conn:
#             # --- Registered metrics ---
#             for metric in metrics:
#                 table_name = metric.dataset.cleaned_table_name
#                 agg = metric.aggregation.lower()
#                 agg_sql = "COUNT(*)" if agg == "count" else f'{agg.upper()}("{metric.column_name}")'
#                 try:
#                     result = conn.execute(text(f'SELECT {agg_sql} as value FROM "{table_name}"')).fetchone()
#                     value = float(result[0]) if result and result[0] is not None else 0
#                 except Exception:
#                     value = None
#                 cards.append({
#                     "metric_id": metric.id,
#                     "name": metric.name,
#                     "value": value,
#                     "aggregation": agg,
#                     "display_value": _format_value(value, metric.name),
#                 })

#             # --- Auto-KPIs from datasets (when no metrics are registered) ---
#             if not metrics:
#                 datasets = db.query(Dataset).filter(
#                     Dataset.workspace_id == workspace_id,
#                     Dataset.is_processed == 1,
#                 ).all()

#                 auto_id = 0
#                 for ds in datasets[:3]:  # cap at 3 datasets for dashboard
#                     try:
#                         # Fetch one row to detect column types
#                         sample = conn.execute(text(f'SELECT * FROM "{ds.cleaned_table_name}" LIMIT 1')).fetchone()
#                         col_names = conn.execute(text(f'SELECT * FROM "{ds.cleaned_table_name}" LIMIT 0')).keys()
#                         col_names = list(col_names)
#                     except Exception:
#                         continue

#                     if not sample:
#                         # Still get row count
#                         try:
#                             count_r = conn.execute(text(f'SELECT COUNT(*) FROM "{ds.cleaned_table_name}"')).fetchone()
#                             count_val = int(count_r[0]) if count_r else 0
#                             auto_id += 1
#                             cards.append({
#                                 "metric_id": f"auto_{auto_id}",
#                                 "name": f"{ds.original_filename} — Records",
#                                 "value": count_val,
#                                 "aggregation": "count",
#                                 "display_value": f"{count_val:,}",
#                             })
#                         except Exception:
#                             pass
#                         continue

#                     # Detect numeric columns
#                     numeric_cols = []
#                     for col, val in zip(col_names, sample):
#                         if isinstance(val, (int, float)) and val is not None:
#                             numeric_cols.append(col)

#                     # Row count KPI always
#                     try:
#                         count_r = conn.execute(text(f'SELECT COUNT(*) FROM "{ds.cleaned_table_name}"')).fetchone()
#                         count_val = int(count_r[0]) if count_r else 0
#                         auto_id += 1
#                         cards.append({
#                             "metric_id": f"auto_{auto_id}",
#                             "name": f"{ds.original_filename} — Records",
#                             "value": count_val,
#                             "aggregation": "count",
#                             "display_value": f"{count_val:,}",
#                         })
#                     except Exception:
#                         pass

#                     # Sum KPIs for top numeric columns (max 3 per dataset)
#                     for col in numeric_cols[:3]:
#                         try:
#                             result = conn.execute(
#                                 text(f'SELECT SUM("{col}") as value FROM "{ds.cleaned_table_name}"')
#                             ).fetchone()
#                             value = float(result[0]) if result and result[0] is not None else 0
#                             auto_id += 1
#                             cards.append({
#                                 "metric_id": f"auto_{auto_id}",
#                                 "name": col.replace("_", " ").title(),
#                                 "value": value,
#                                 "aggregation": "sum",
#                                 "display_value": _format_value(value, col),
#                             })
#                         except Exception:
#                             continue

#     finally:
#         engine.dispose()

#     return cards


# def _format_value(value: float | None, metric_name: str) -> str:
#     if value is None:
#         return "N/A"

#     name_lower = metric_name.lower()
#     is_currency = any(word in name_lower for word in ["revenue", "profit", "cost", "price", "sales", "amount", "total"])

#     if is_currency:
#         return f"${value:,.2f}"
#     if isinstance(value, float) and value == int(value):
#         return f"{int(value):,}"
#     if isinstance(value, float):
#         return f"{value:,.2f}"
#     return f"{int(value):,}"
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, inspect
from app.models.knowledge_base import BusinessMetric
from app.core.config import settings

DATE_HINTS = ["date", "created_at", "order_date", "timestamp"]

def _find_date_column(engine, table_name: str) -> str | None:
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        for col in columns:
            if any(hint in col["name"].lower() for hint in DATE_HINTS):
                return col["name"]
    except Exception:
        pass
    return None


def generate_kpi_cards(db: Session, workspace_id: int) -> list[dict]:
    metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()

    engine = create_engine(settings.DATABASE_URL)
    cards = []

    try:
        with engine.connect() as conn:
            for metric in metrics:
                table_name = metric.dataset.cleaned_table_name
                agg = metric.aggregation.lower()
                agg_sql = "COUNT(*)" if agg == "count" else f'{agg.upper()}("{metric.column_name}")'

                try:
                    result = conn.execute(text(f'SELECT {agg_sql} as value FROM "{table_name}"')).fetchone()
                    value = float(result[0]) if result and result[0] is not None else 0
                except Exception:
                    value = None

                change_percent = None
                date_col = _find_date_column(engine, table_name)
                if date_col and agg in ("sum", "count") and value is not None:
                    try:
                        agg_expr = "COUNT(*)" if agg == "count" else f'SUM("{metric.column_name}")'
                        trend_query = f'''
                            SELECT
                                COALESCE({agg_expr} FILTER (WHERE "{date_col}" >= now() - interval '30 days'), 0) as current_period,
                                COALESCE({agg_expr} FILTER (WHERE "{date_col}" >= now() - interval '60 days' AND "{date_col}" < now() - interval '30 days'), 0) as prior_period
                            FROM "{table_name}"
                        '''
                        trend_row = conn.execute(text(trend_query)).fetchone()
                        current_p, prior_p = float(trend_row[0]), float(trend_row[1])
                        if prior_p > 0:
                            change_percent = round(((current_p - prior_p) / prior_p) * 100, 1)
                    except Exception:
                        change_percent = None

                cards.append({
                    "metric_id": metric.id,
                    "name": metric.name,
                    "value": value,
                    "aggregation": agg,
                    "display_value": _format_value(value, metric.name),
                    "change_percent": change_percent,
                })

            if not metrics:
                from app.models.dataset import Dataset
                datasets = db.query(Dataset).filter(
                    Dataset.workspace_id == workspace_id,
                    Dataset.is_processed == 1,
                ).all()

                auto_id = 0
                for ds in datasets[:3]:
                    try:
                        table_name = ds.cleaned_table_name
                        count_r = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).fetchone()
                        count_val = int(count_r[0]) if count_r else 0
                        auto_id += 1
                        cards.append({
                            "metric_id": f"auto_{auto_id}",
                            "name": f"{ds.original_filename} Records",
                            "value": count_val,
                            "aggregation": "count",
                            "display_value": f"{count_val:,}",
                            "change_percent": None,
                        })

                        inspector = inspect(engine)
                        cols = inspector.get_columns(table_name)
                        numeric_cols = [c["name"] for c in cols if any(t in str(c["type"]).upper() for t in ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]) and not any(h in c["name"].lower() for h in ["id", "code", "zip"])]

                        for col in numeric_cols[:1]:  # Just top numeric column for sum
                            sum_r = conn.execute(text(f'SELECT SUM("{col}") FROM "{table_name}"')).fetchone()
                            sum_val = float(sum_r[0]) if sum_r and sum_r[0] is not None else 0
                            auto_id += 1
                            cards.append({
                                "metric_id": f"auto_{auto_id}",
                                "name": col.replace("_", " ").title(),
                                "value": sum_val,
                                "aggregation": "sum",
                                "display_value": _format_value(sum_val, col),
                                "change_percent": None, 
                            })
                    except Exception:
                        pass
    finally:
        engine.dispose()

    return cards


def _format_value(value, metric_name: str) -> str:
    if value is None:
        return "N/A"
    name_lower = metric_name.lower()
    is_currency = any(w in name_lower for w in ["revenue", "profit", "cost", "price", "sales", "amount"])
    if is_currency:
        return f"${value:,.2f}" if value < 1_000_000 else f"${value/1_000_000:,.2f}M"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"