import os
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from app.core.constants import REPORTS_DIR


def generate_pdf_report(summary: dict, workspace_name: str) -> tuple[str, str]:
    """
    Build a PDF executive report from the summary dict produced by
    generate_executive_summary(). Returns (file_path, file_name).
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    file_name = f"executive_summary_{uuid.uuid4().hex[:8]}.pdf"
    file_path = os.path.join(REPORTS_DIR, file_name)

    doc = SimpleDocTemplate(file_path, pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=20, spaceAfter=6)
    heading_style = styles["Heading2"]
    body_style = styles["Normal"]

    story = []

    # Title
    story.append(Paragraph(f"Executive Summary — {workspace_name}", title_style))
    # story.append(Paragraph(f"Generated: {datetime.fromisoformat(summary['generated_at']).strftime('%B %d, %Y %H:%M UTC')}", body_style))
    generated_at = summary["generated_at"].replace("Z", "+00:00")
    story.append(Paragraph(f"Generated: {datetime.fromisoformat(generated_at).strftime('%B %d, %Y %H:%M UTC')}", body_style))
    story.append(Spacer(1, 16))

    # Narrative
    story.append(Paragraph("Overview", heading_style))
    story.append(Paragraph(summary.get("narrative", "No summary available."), body_style))
    story.append(Spacer(1, 12))

    # Sales section
    sales = summary.get("sales", {})
    if sales:
        story.append(Paragraph("Sales Performance", heading_style))
        sales_table_data = [
            ["Metric", "Value"],
            ["Total Revenue", f"${sales.get('total_revenue', 0):,.2f}"],
            ["Average Order Value", f"${sales.get('average_order_value', 0):,.2f}"],
            ["Trend Direction", str(sales.get("trend_direction", "N/A")).capitalize()],
            ["Overall Change", f"{sales.get('overall_change_percent', 'N/A')}%"],
        ]
        story.append(_make_table(sales_table_data))
        story.append(Spacer(1, 12))

    # Customers section
    customers = summary.get("customers", {})
    if customers and customers.get("top_customers"):
        story.append(Paragraph("Top Customers", heading_style))
        rows = [["Customer", "Total Spent", "Orders"]]
        for c in customers["top_customers"][:10]:
            rows.append([str(c.get("customer")), f"${c.get('total_spent', 0):,.2f}", str(c.get("order_count", ""))])
        story.append(_make_table(rows))
        story.append(Spacer(1, 12))

    # Products section
    products = summary.get("products", {})
    if products and products.get("best_performing_products"):
        story.append(Paragraph("Best Performing Products", heading_style))
        rows = [["Product", "Total Revenue"]]
        for p in products["best_performing_products"][:10]:
            rows.append([str(p.get("product")), f"${p.get('total_revenue', 0):,.2f}"])
        story.append(_make_table(rows))
        story.append(Spacer(1, 12))

    # Inventory section
    inventory = summary.get("inventory", {})
    if inventory and (inventory.get("out_of_stock_count") or inventory.get("low_stock_count")):
        story.append(Paragraph("Inventory Alerts", heading_style))
        story.append(Paragraph(
            f"Out of stock: {inventory.get('out_of_stock_count', 0)} — "
            f"Low stock: {inventory.get('low_stock_count', 0)}", body_style
        ))
        story.append(Spacer(1, 12))

    # Recommendations
    recs = summary.get("recommendations", [])
    if recs:
        story.append(PageBreak())
        story.append(Paragraph("Recommendations", heading_style))
        for r in recs:
            story.append(Paragraph(f"• {r}", body_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    return file_path, file_name


def _make_table(data: list[list[str]]) -> Table:
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90e2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table