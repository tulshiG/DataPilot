import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from datetime import datetime, timezone

from app.models.dataset import Dataset
from app.models.knowledge_base import BusinessMetric, BusinessEntity
from app.insight_engine.business_summary import (
    analyze_sales, detect_inventory_issues, analyze_customers, analyze_products,
)
from app.insight_engine.recommendation import generate_recommendations
from app.core.config import settings
from app.core.exceptions import BadRequestException


# Fallback keyword hints if no knowledge-base metric/entity is registered for a role
COLUMN_HINTS = {
    "date": ["date", "created_at", "order_date", "timestamp"],
    "revenue": ["revenue", "total_amount", "amount", "price", "sales"],
    "customer": ["customer", "client", "buyer"],
    "product": ["product", "item", "sku"],
    "stock": ["stock", "inventory", "quantity_available", "qty"],
    "quantity": ["quantity", "qty", "units"],
}


def _resolve_column(df: pd.DataFrame, role: str) -> str | None:
    """Best-effort match of a DataFrame column to a business role (date, revenue, etc.).
    Matching is case-insensitive. Falls back to first numeric/date column if no hint matches."""
    hints = COLUMN_HINTS.get(role, [])
    # Case-insensitive partial match
    for col in df.columns:
        col_norm = col.lower().replace("_", " ").replace("-", " ")
        if any(hint in col_norm for hint in hints):
            if role == "date":
                try:
                    parsed = pd.to_datetime(df[col].dropna().head(20), errors="coerce", format="mixed")
                    if parsed.notnull().mean() < 0.7:
                        continue
                except Exception:
                    continue
            return col

    # Smart defaults: if no hint matched, pick first column of the right dtype
    if role == "date":
        date_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
        if date_cols:
            return date_cols[0]
        # Try to detect object columns that look like dates
        for col in df.select_dtypes(include="object").columns:
            try:
                parsed = pd.to_datetime(df[col].dropna().head(20), errors="coerce", format="mixed")
                if parsed.notnull().mean() > 0.7:
                    return col
            except Exception:
                continue

    if role in ("revenue", "quantity", "stock"):
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            return num_cols[0]

    return None

def _load_dataset_df(table_name: str, max_rows: int = 200_000) -> pd.DataFrame:
    engine = create_engine(settings.DATABASE_URL)
    try:
        return pd.read_sql_table(table_name, engine).head(max_rows)
    finally:
        engine.dispose()

def generate_executive_summary(db: Session, workspace_id: int) -> dict:
    """
    Task 7: Build a full executive summary by running sales/inventory/customer/product
    analysis against the workspace's datasets, then compiling a narrative.
    """
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
    ).all()

    if not datasets:
        raise BadRequestException("No processed datasets found. Run ETL first.")

    sales_result, inventory_result, customer_result, product_result = {}, {}, {}, {}

    for ds in datasets:
        df = _load_dataset_df(ds.cleaned_table_name)
        if df.empty:
            continue

        date_col = _resolve_column(df, "date")
        revenue_col = _resolve_column(df, "revenue")
        customer_col = _resolve_column(df, "customer")
        product_col = _resolve_column(df, "product")
        stock_col = _resolve_column(df, "stock")
        qty_col = _resolve_column(df, "quantity")

        # Sales: needs date + revenue
        if date_col and revenue_col and not sales_result:
            sales_result = analyze_sales(df, date_col, revenue_col)
            sales_result["source_dataset"] = ds.original_filename

        # Inventory: needs product + stock
        if product_col and stock_col and not inventory_result:
            inventory_result = detect_inventory_issues(df, product_col, stock_col)
            inventory_result["source_dataset"] = ds.original_filename

        # Customers: needs customer + revenue
        if customer_col and revenue_col and not customer_result:
            customer_result = analyze_customers(df, customer_col, revenue_col)
            customer_result["source_dataset"] = ds.original_filename

        # Products: needs product + revenue
        if product_col and revenue_col and not product_result:
            product_result = analyze_products(df, product_col, revenue_col, qty_col)
            product_result["source_dataset"] = ds.original_filename

    recommendations = generate_recommendations(sales_result, inventory_result, customer_result, product_result)
    narrative = _build_narrative(sales_result, inventory_result, customer_result, product_result)

    return {
        "workspace_id": workspace_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "narrative": narrative,
        "sales": sales_result,
        "inventory": inventory_result,
        "customers": customer_result,
        "products": product_result,
        "recommendations": recommendations,
    }


def _build_narrative(sales: dict, inventory: dict, customers: dict, products: dict) -> str:
    """Compose a short, human-readable paragraph summary from the structured results."""
    lines = []

    if sales:
        direction_word = {"up": "grew", "down": "declined", "flat": "remained stable"}.get(sales.get("trend_direction"), "changed")
        lines.append(
            f"Total revenue reached ${sales.get('total_revenue', 0):,.2f}, and has {direction_word} "
            f"over the observed period"
            + (f" ({sales.get('overall_change_percent')}% change)." if sales.get("overall_change_percent") is not None else ".")
        )

    if customers:
        lines.append(
            f"There are {customers.get('total_unique_customers', 0)} unique customers, "
            f"averaging ${customers.get('avg_customer_value', 0):,.2f} in total spend each."
        )

    if products:
        best = products.get("best_performing_products", [])
        if best:
            lines.append(f"The top-performing product is '{best[0].get('product')}' by revenue.")

    if inventory:
        if inventory.get("out_of_stock_count", 0) > 0:
            lines.append(f"{inventory['out_of_stock_count']} product(s) are currently out of stock.")
        elif inventory.get("low_stock_count", 0) > 0:
            lines.append(f"{inventory['low_stock_count']} product(s) have low stock levels.")

    if not lines:
        lines.append("Not enough recognizable business data (revenue, customer, or product columns) was found to generate a full summary.")

    return " ".join(lines)