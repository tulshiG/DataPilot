"""
domain_detector.py
──────────────────
Detects the semantic domain of a dataset by scanning column names and sample
values, then returns a ranked list of chart "intents" for that domain.
This makes the dashboard smart for ANY kind of dataset — medical, orders,
insurance, superstore, students, HR, inventory, etc.
"""

from __future__ import annotations
import re
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

# ──────────────────────────────────────────────
# Domain registry
# ──────────────────────────────────────────────
DOMAIN_RULES: list[dict] = [
    {
        "domain": "sales_orders",
        "label": "Sales / Orders",
        "icon": "🛒",
        "signals": ["order", "sale", "revenue", "purchase", "cart", "product", "category",
                    "payment", "shipping", "discount", "quantity", "invoice", "customer"],
        "chart_intents": [
            "revenue_trend",
            "category_bar",
            "payment_pie",
            "status_donut",
            "top_products_bar",
            "top_customers_bar",
            "city_revenue_hbar",
            "discount_vs_sales_scatter",
            "monthly_orders_line",
        ],
    },
    {
        "domain": "superstore",
        "label": "Retail / Superstore",
        "icon": "🏪",
        "signals": ["profit", "segment", "sub-category", "sub_category", "ship_mode",
                    "superstore", "furniture", "technology", "office"],
        "chart_intents": [
            "revenue_trend",
            "profit_trend",
            "category_bar",
            "subcategory_hbar",
            "profit_by_region_bar",
            "segment_bar",
            "top_customers_bar",
            "top_products_bar",
            "discount_vs_profit_scatter",
            "sales_vs_profit_scatter",
            "ship_mode_pie",
            "category_profit_treemap",
        ],
    },
    {
        "domain": "insurance",
        "label": "Insurance / Medical",
        "icon": "🏥",
        "signals": ["bmi", "smoker", "charges", "insurance", "premium", "claim",
                    "diagnosis", "patient", "age", "medical", "health", "disease",
                    "hospital", "treatment", "blood", "glucose", "cholesterol"],
        "chart_intents": [
            "age_vs_charges_scatter",
            "bmi_vs_charges_scatter",
            "smoker_bar",
            "charges_histogram",
            "bmi_histogram",
            "region_pie",
            "gender_bar",
            "children_bar",
            "correlation_heatmap",
        ],
    },
    {
        "domain": "hr_employee",
        "label": "HR / Employee",
        "icon": "👥",
        "signals": ["employee", "department", "salary", "hire_date", "joining",
                    "attendance", "login", "logout", "leave", "payroll", "designation",
                    "performance", "rating", "manager", "staff", "workforce"],
        "chart_intents": [
            "revenue_trend",
            "department_bar",
            "salary_histogram",
            "gender_pie",
            "attendance_line",
            "performance_bar",
            "age_histogram",
        ],
    },
    {
        "domain": "education",
        "label": "Education / Students",
        "icon": "🎓",
        "signals": ["student", "grade", "marks", "score", "subject", "class", "result",
                    "gpa", "attendance", "exam", "pass", "fail", "admission", "course",
                    "semester", "faculty", "roll"],
        "chart_intents": [
            "score_histogram",
            "subject_bar",
            "grade_pie",
            "test_takers_bar",
            "age_histogram",
            "attendance_bar",
            "gender_pie",
            "score_trend",
        ],
    },
    {
        "domain": "inventory",
        "label": "Inventory / Warehouse",
        "icon": "📦",
        "signals": ["inventory", "stock", "warehouse", "sku", "reorder", "supplier",
                    "item", "batch", "expiry", "shelf", "unit", "quantity_on_hand",
                    "purchase_price", "selling_price"],
        "chart_intents": [
            "category_bar",
            "stock_histogram",
            "top_products_bar",
            "revenue_trend",
            "supplier_pie",
            "category_profit_treemap",
        ],
    },
    {
        "domain": "generic",
        "label": "General Dataset",
        "icon": "📊",
        "signals": [],
        "chart_intents": [
            "revenue_trend",
            "category_bar",
            "distribution_pie",
            "numeric_histogram",
            "correlation_scatter",
        ],
    },
]


# ──────────────────────────────────────────────
# Detection logic
# ──────────────────────────────────────────────
def detect_domain(df: pd.DataFrame) -> dict:
    """
    Score each domain by how many of its signal words appear in the
    dataframe's column names (case-insensitive).
    Returns the best-matching domain dict (including its chart_intents).
    """
    col_text = " ".join(df.columns).lower()

    best_domain = DOMAIN_RULES[-1]  # fallback = generic
    best_score = 0

    for rule in DOMAIN_RULES[:-1]:  # skip generic in scoring
        score = sum(1 for sig in rule["signals"] if sig in col_text)
        if score > best_score:
            best_score = score
            best_domain = rule

    return {
        "domain": best_domain["domain"],
        "label": best_domain["label"],
        "icon": best_domain["icon"],
        "score": best_score,
        "chart_intents": best_domain["chart_intents"],
    }


# ──────────────────────────────────────────────
# Column classifier
# ──────────────────────────────────────────────
def classify_columns(df: pd.DataFrame) -> dict:
    """Classify each column into numeric / datetime / categorical buckets,
    plus domain-specific named roles."""
    numeric_cols: list[str] = df.select_dtypes(include="number").columns.tolist()
    datetime_cols: list[str] = []
    categorical_cols: list[str] = []

    for col in df.columns:
        if col in numeric_cols:
            continue
        try:
            parsed = pd.to_datetime(df[col].dropna().head(30), errors="coerce", format="mixed")
            if parsed.notnull().mean() > 0.7:
                datetime_cols.append(col)
                continue
        except Exception:
            pass
        categorical_cols.append(col)

    # Named roles — find by hint in column name
    def _find_col(hints: list[str], pool: list[str]) -> Optional[str]:
        for h in hints:
            for c in pool:
                if h in c.lower():
                    return c
        return None

    # Revenue / amount column
    revenue_col = _find_col(
        ["sales", "revenue", "amount", "total", "price", "charges", "salary", "profit", "cost", "score", "marks"],
        numeric_cols,
    )
    # Quantity column
    quantity_col = _find_col(["quantity", "qty", "units", "count", "stock"], numeric_cols)
    # Discount column
    discount_col = _find_col(["discount", "reduction", "offer"], numeric_cols)
    # Category column
    category_col = _find_col(
        ["category", "type", "segment", "class", "department", "region", "subject", "mode"],
        categorical_cols,
    )
    # Status / result column
    status_col = _find_col(
        ["status", "result", "grade", "pass", "fail", "smoker", "gender", "sex"],
        categorical_cols,
    )
    # Geographic column
    geo_col = _find_col(["state", "city", "country", "region", "location"], categorical_cols)
    # Product / item column
    product_col = _find_col(
        ["product", "item", "sku", "name", "description", "sub_category", "sub-category"],
        categorical_cols,
    )
    # Customer / user column
    customer_col = _find_col(["customer", "client", "user", "student", "employee", "patient"], categorical_cols)

    # Date column
    date_col = datetime_cols[0] if datetime_cols else None

    return {
        "numeric": numeric_cols,
        "datetime": datetime_cols,
        "categorical": categorical_cols,
        # Named roles
        "revenue_col": revenue_col,
        "quantity_col": quantity_col,
        "discount_col": discount_col,
        "category_col": category_col,
        "status_col": status_col,
        "geo_col": geo_col,
        "product_col": product_col,
        "customer_col": customer_col,
        "date_col": date_col,
    }
