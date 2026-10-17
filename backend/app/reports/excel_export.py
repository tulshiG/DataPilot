import os
import uuid
import pandas as pd
from app.core.constants import REPORTS_DIR

def export_dataset_to_excel(df: pd.DataFrame, dataset_name: str) -> tuple[str, str]:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in dataset_name.rsplit(".", 1)[0])[:40]
    file_name = f"{safe_name}_{uuid.uuid4().hex[:8]}.xlsx"
    file_path = os.path.join(REPORTS_DIR, file_name)

    df.to_excel(file_path, index=False, engine="openpyxl")
    return file_path, file_name


def export_summary_to_excel(summary: dict, workspace_name: str) -> tuple[str, str]:
    """Export the executive summary's tabular sections as a multi-sheet Excel file."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    file_name = f"executive_summary_{uuid.uuid4().hex[:8]}.xlsx"
    file_path = os.path.join(REPORTS_DIR, file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        if summary.get("sales", {}).get("monthly_breakdown"):
            pd.DataFrame(summary["sales"]["monthly_breakdown"]).to_excel(writer, sheet_name="Sales Trend", index=False)
        if summary.get("customers", {}).get("top_customers"):
            pd.DataFrame(summary["customers"]["top_customers"]).to_excel(writer, sheet_name="Top Customers", index=False)
        if summary.get("products", {}).get("best_performing_products"):
            pd.DataFrame(summary["products"]["best_performing_products"]).to_excel(writer, sheet_name="Top Products", index=False)
        if summary.get("inventory", {}).get("low_stock_products"):
            pd.DataFrame(summary["inventory"]["low_stock_products"]).to_excel(writer, sheet_name="Low Stock", index=False)
        if summary.get("recommendations"):
            pd.DataFrame({"Recommendation": summary["recommendations"]}).to_excel(writer, sheet_name="Recommendations", index=False)

    return file_path, file_name