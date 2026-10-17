"""
dashboard_generator.py  (v2 — Smart Domain-Aware)
─────────────────────────────────────────────────
Produces KPI cards + a rich set of domain-tailored charts for every
processed dataset in the workspace.  Works for ANY dataset type:
  orders, insurance, superstore, students, HR, inventory, medical, …
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
import pandas as pd

from app.models.dataset import Dataset
from app.visualization_engine.kpi_cards import generate_kpi_cards
from app.visualization_engine.domain_detector import detect_domain, classify_columns
from app.visualization_engine.chart_builder import build_charts_from_intents
from app.core.config import settings


def _dedupe_datasets(datasets: list[Dataset]) -> list[Dataset]:
    """Keep only the most recent version of each filename."""
    seen: dict[str, Dataset] = {}
    for ds in datasets:
        key = ds.original_filename
        if key not in seen or ds.id > seen[key].id:
            seen[key] = ds
    return list(seen.values())


def generate_dashboard(db: Session, workspace_id: int, filters: dict | None = None) -> dict:
    kpis = generate_kpi_cards(db, workspace_id)

    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
    ).all()
    datasets = _dedupe_datasets(datasets)

    engine = create_engine(settings.DATABASE_URL)
    charts: list[dict] = []
    dataset_meta: list[dict] = []   # returned so the frontend can show domain badges

    try:
        with engine.connect() as conn:
            for ds in datasets:
                try:
                    result = conn.execute(
                        text(f'SELECT * FROM "{ds.cleaned_table_name}" LIMIT 3000')
                    )
                    columns = list(result.keys())
                    rows = result.fetchall()
                except Exception:
                    continue

                if not rows:
                    continue

                df = pd.DataFrame(rows, columns=columns)

                # ── Step 1: detect domain ────────────────────────────────────
                domain_info = detect_domain(df)

                # ── Step 2: classify columns + resolve named roles ───────────
                cols = classify_columns(df)

                # ── Step 3: build charts from domain intents ─────────────────
                ds_charts = build_charts_from_intents(
                    df,
                    ds.original_filename,
                    cols,
                    domain_info["chart_intents"],
                )
                charts.extend(ds_charts)

                dataset_meta.append({
                    "id": ds.id,
                    "name": ds.original_filename,
                    "domain": domain_info["domain"],
                    "domain_label": domain_info["label"],
                    "domain_icon": domain_info["icon"],
                    "chart_count": len(ds_charts),
                    "rows": len(df),
                    "columns": len(df.columns),
                })

    finally:
        engine.dispose()

    return {
        "workspace_id": workspace_id,
        "kpis": kpis,
        "charts": charts,
        "datasets": dataset_meta,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }