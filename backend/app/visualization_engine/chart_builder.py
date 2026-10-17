"""
chart_builder.py
────────────────
Maps chart "intents" (detected by domain_detector) to actual chart data.
All chart functions are imported here and dispatched by intent name.

Intent naming convention:
  <what>_<chart_suffix>
  e.g. revenue_trend, category_bar, smoker_box, charges_histogram
"""

from __future__ import annotations
import pandas as pd
from typing import Optional

from app.visualization_engine.bar_chart import generate_bar_chart_data
from app.visualization_engine.line_chart import generate_line_chart_data
from app.visualization_engine.pie_chart import generate_pie_chart_data
from app.visualization_engine.scatter_plot import generate_scatter_plot_data
from app.visualization_engine.histogram import generate_histogram_data
from app.visualization_engine.box_plot import generate_box_plot_data
from app.visualization_engine.heatmap import generate_heatmap_data


# ──────────────────────────────────────────────────────────────────────────────
# Intent → builder dispatch
# ──────────────────────────────────────────────────────────────────────────────

def build_charts_from_intents(
    df: pd.DataFrame,
    dataset_name: str,
    cols: dict,
    intents: list[str],
) -> list[dict]:
    """
    Iterate over the ordered list of intents produced by the domain detector
    and build as many charts as possible from the available columns.
    Each chart is de-duplicated by (chart_type, x_axis) so we never show the
    same axis pair twice.
    """
    charts: list[dict] = []
    seen: set[tuple] = set()

    def _add(chart: dict, title: str, intent: str):
        if not chart.get("data"):
            return
        key = (chart.get("chart_type"), chart.get("x_axis_label"), chart.get("group_col"))
        if key in seen:
            return
        seen.add(key)
        chart["title"] = title
        chart["dataset_name"] = dataset_name
        chart["intent"] = intent
        charts.append(chart)

    revenue = cols.get("revenue_col")
    discount = cols.get("discount_col")
    quantity = cols.get("quantity_col")
    category = cols.get("category_col")
    status = cols.get("status_col")
    geo = cols.get("geo_col")
    product = cols.get("product_col")
    customer = cols.get("customer_col")
    date_col = cols.get("date_col")
    numeric = cols.get("numeric", [])
    categorical = cols.get("categorical", [])

    # Fallback helpers
    def first_numeric(exclude=()) -> Optional[str]:
        for c in numeric:
            if c not in exclude:
                return c
        return None

    def first_cat(exclude=()) -> Optional[str]:
        for c in categorical:
            if c not in exclude and df[c].nunique() > 1:
                return c
        return None

    def low_card_cats(min_u=2, max_u=8) -> list[str]:
        return [c for c in categorical if min_u <= df[c].nunique() <= max_u]

    def high_card_cats(min_u=9) -> list[str]:
        return [c for c in categorical if df[c].nunique() >= min_u]

    for intent in intents:

        # ── Time-series / trend charts ──────────────────────────────────────
        if intent == "revenue_trend" and date_col:
            y = revenue or first_numeric()
            if y:
                _add(
                    generate_line_chart_data(df, date_col, [y]),
                    f"{y.replace('_', ' ').title()} Over Time",
                    intent,
                )

        elif intent == "profit_trend" and date_col:
            profit_col = next((c for c in numeric if "profit" in c.lower()), None)
            if profit_col:
                _add(
                    generate_line_chart_data(df, date_col, [profit_col]),
                    "Profit Over Time",
                    intent,
                )

        elif intent == "score_trend" and date_col:
            y = revenue or first_numeric()
            if y:
                _add(
                    generate_line_chart_data(df, date_col, [y]),
                    "Score Trend Over Time",
                    intent,
                )

        elif intent == "attendance_line" and date_col:
            att = first_numeric()
            if att:
                _add(
                    generate_line_chart_data(df, date_col, [att]),
                    "Attendance Over Time",
                    intent,
                )

        elif intent == "monthly_orders_line" and date_col:
            y = revenue or quantity or first_numeric()
            if y:
                _add(
                    generate_line_chart_data(df, date_col, [y]),
                    "Monthly Orders Over Time",
                    intent,
                )

        # ── Bar charts ──────────────────────────────────────────────────────
        elif intent == "category_bar":
            x = category or first_cat()
            y = revenue or quantity or first_numeric()
            if x and y:
                _add(
                    generate_bar_chart_data(df, x, y),
                    f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "subcategory_hbar":
            sub = next((c for c in categorical if "sub" in c.lower()), None)
            y = revenue or first_numeric()
            if sub and y:
                d = generate_bar_chart_data(df, sub, y, limit=15)
                d["orientation"] = "horizontal"
                _add(d, f"{y.replace('_', ' ').title()} by Sub-Category", intent)

        elif intent in ("top_products_bar", "top_customers_bar"):
            dim_col = (product if "product" in intent else customer) or first_cat()
            y = revenue or quantity or first_numeric()
            if dim_col and y:
                label = "Products" if "product" in intent else "Customers"
                _add(
                    generate_bar_chart_data(df, dim_col, y, limit=10),
                    f"Top 10 {label} by {y.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "city_revenue_hbar":
            x = geo or first_cat()
            y = revenue or first_numeric()
            if x and y:
                d = generate_bar_chart_data(df, x, y, limit=15)
                d["orientation"] = "horizontal"
                _add(d, f"Top Cities by {y.replace('_', ' ').title()}", intent)

        elif intent == "profit_by_region_bar":
            x = geo or first_cat()
            profit = next((c for c in numeric if "profit" in c.lower()), revenue or first_numeric())
            if x and profit:
                _add(
                    generate_bar_chart_data(df, x, profit, limit=15),
                    f"Profit by {x.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "segment_bar":
            seg = next((c for c in categorical if "segment" in c.lower()), first_cat())
            y = revenue or first_numeric()
            if seg and y:
                _add(
                    generate_bar_chart_data(df, seg, y),
                    f"{y.replace('_', ' ').title()} by Segment",
                    intent,
                )

        elif intent == "department_bar":
            dep = next((c for c in categorical if any(h in c.lower() for h in ["department", "dept"])), first_cat())
            y = revenue or first_numeric()
            if dep and y:
                _add(
                    generate_bar_chart_data(df, dep, y),
                    f"{y.replace('_', ' ').title()} by Department",
                    intent,
                )

        elif intent == "children_bar":
            child = next((c for c in numeric if "child" in c.lower()), None)
            y = revenue or first_numeric()
            if child and y:
                _add(
                    generate_bar_chart_data(df, child, y),
                    "Avg Charges by Number of Children",
                    intent,
                )

        elif intent == "attendance_bar":
            att_col = next((c for c in categorical if "attend" in c.lower()), first_cat())
            y = revenue or first_numeric()
            if att_col and y:
                _add(
                    generate_bar_chart_data(df, att_col, y),
                    "Performance by Attendance",
                    intent,
                )

        elif intent == "subject_bar":
            sub = next((c for c in categorical if "subject" in c.lower() or "region" in c.lower()), first_cat())
            y = revenue or first_numeric()
            if sub and y:
                _add(
                    generate_bar_chart_data(df, sub, y, agg="mean"),
                    f"Avg Score by {sub.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "performance_bar":
            perf_col = next((c for c in categorical if any(h in c.lower() for h in ["performance", "rating", "level"])), first_cat())
            y = first_numeric()
            if perf_col and y:
                _add(
                    generate_bar_chart_data(df, perf_col, y),
                    f"{y.replace('_', ' ').title()} by Performance Level",
                    intent,
                )

        # ── Pie / Donut charts ──────────────────────────────────────────────
        elif intent == "payment_pie":
            pay = next((c for c in categorical if any(h in c.lower() for h in ["payment", "pay_method", "pay_mode"])), None)
            if pay:
                _add(generate_pie_chart_data(df, pay), "Payment Method Distribution", intent)

        elif intent == "status_donut":
            sc = status or first_cat()
            if sc and df[sc].nunique() <= 8:
                d = generate_pie_chart_data(df, sc)
                d["chart_type"] = "donut"
                _add(d, f"Order / Status Distribution by {sc.replace('_', ' ').title()}", intent)

        elif intent == "test_takers_bar":
            dbn = next((c for c in categorical if "dbn" in c.lower() or "school" in c.lower()), first_cat())
            y = revenue or first_numeric()
            if dbn and y:
                _add(
                    generate_bar_chart_data(df, dbn, y, agg="count"),
                    f"Number Of Test Takers by {dbn.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "region_pie":
            reg = geo or next((c for c in categorical if "region" in c.lower()), None)
            if reg:
                _add(generate_pie_chart_data(df, reg), "Regional Distribution", intent)

        elif intent == "gender_pie":
            gen = next((c for c in categorical if any(h in c.lower() for h in ["gender", "sex"])), None)
            if gen:
                _add(generate_pie_chart_data(df, gen), "Gender Distribution", intent)

        elif intent == "ship_mode_pie":
            ship = next((c for c in categorical if "ship" in c.lower()), None)
            if ship:
                _add(generate_pie_chart_data(df, ship), "Shipping Mode Distribution", intent)

        elif intent == "supplier_pie":
            sup = next((c for c in categorical if "supplier" in c.lower()), None)
            if sup:
                _add(generate_pie_chart_data(df, sup), "Supplier Distribution", intent)

        elif intent == "grade_pie":
            gr = next((c for c in categorical if "grade" in c.lower()), status or first_cat())
            if gr and df[gr].nunique() <= 8:
                _add(generate_pie_chart_data(df, gr), "Grade Distribution", intent)

        elif intent == "distribution_pie":
            lc = low_card_cats()
            if lc:
                _add(generate_pie_chart_data(df, lc[0]), f"Distribution by {lc[0].replace('_', ' ').title()}", intent)

        # ── Scatter charts ──────────────────────────────────────────────────
        elif intent == "discount_vs_sales_scatter":
            x = discount
            y = revenue or first_numeric(exclude=[discount] if discount else [])
            if x and y:
                _add(
                    generate_scatter_plot_data(df, x, y),
                    f"Discount vs {y.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "discount_vs_profit_scatter":
            x = discount
            profit = next((c for c in numeric if "profit" in c.lower()), revenue)
            if x and profit:
                _add(generate_scatter_plot_data(df, x, profit), "Discount vs Profit", intent)

        elif intent == "sales_vs_profit_scatter":
            profit = next((c for c in numeric if "profit" in c.lower()), None)
            sales = next((c for c in numeric if any(h in c.lower() for h in ["sales", "revenue", "amount"])), None)
            if profit and sales and profit != sales:
                _add(generate_scatter_plot_data(df, sales, profit), "Sales vs Profit", intent)

        elif intent == "age_vs_charges_scatter":
            age = next((c for c in numeric if "age" in c.lower()), None)
            charge = revenue or first_numeric(exclude=[age] if age else [])
            if age and charge:
                _add(
                    generate_scatter_plot_data(df, age, charge),
                    f"Age vs {charge.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "bmi_vs_charges_scatter":
            bmi = next((c for c in numeric if "bmi" in c.lower()), None)
            charge = revenue or first_numeric(exclude=[bmi] if bmi else [])
            if bmi and charge:
                _add(
                    generate_scatter_plot_data(df, bmi, charge),
                    f"BMI vs {charge.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "correlation_scatter" and len(numeric) >= 2:
            _add(
                generate_scatter_plot_data(df, numeric[0], numeric[1]),
                f"{numeric[0].replace('_', ' ').title()} vs {numeric[1].replace('_', ' ').title()}",
                intent,
            )

        # ── Box plots to bar charts fallback ───
        elif intent == "smoker_bar":
            smoker = next((c for c in categorical if "smok" in c.lower()), status)
            charge = revenue or first_numeric()
            if smoker and charge:
                _add(
                    generate_bar_chart_data(df, smoker, charge, agg="mean"),
                    f"Avg {charge.replace('_', ' ').title()} by Smoker",
                    intent,
                )

        elif intent == "gender_bar":
            gen = next((c for c in categorical if any(h in c.lower() for h in ["gender", "sex"])), None)
            charge = revenue or first_numeric()
            if gen and charge:
                _add(
                    generate_bar_chart_data(df, gen, charge, agg="mean"),
                    f"Avg {charge.replace('_', ' ').title()} by Gender",
                    intent,
                )

        # ── Histograms ──────────────────────────────────────────────────────
        elif intent in ("charges_histogram", "numeric_histogram", "score_histogram", "salary_histogram"):
            y = revenue or first_numeric()
            if y:
                _add(
                    generate_histogram_data(df, y),
                    f"Distribution of {y.replace('_', ' ').title()}",
                    intent,
                )

        elif intent == "bmi_histogram":
            bmi = next((c for c in numeric if "bmi" in c.lower()), None)
            if bmi:
                _add(generate_histogram_data(df, bmi), "BMI Distribution", intent)

        elif intent == "age_histogram":
            age = next((c for c in numeric if "age" in c.lower()), None)
            if age:
                _add(generate_histogram_data(df, age, bins=15), "Age Distribution", intent)

        elif intent == "stock_histogram":
            stock = next((c for c in numeric if any(h in c.lower() for h in ["stock", "quantity", "inventory"])), None)
            if stock:
                _add(generate_histogram_data(df, stock), "Stock Level Distribution", intent)

        # ── Heatmap ─────────────────────────────────────────────────────────
        elif intent == "correlation_heatmap":
            if len(cols.get("numeric", [])) >= 2:
                _add(generate_heatmap_data(df), "Correlation Heatmap", intent)

        # ── Treemap (sent as bar with treemap flag) ─────────────────────────
        elif intent == "category_profit_treemap":
            x = category or first_cat()
            profit = next((c for c in numeric if "profit" in c.lower()), revenue or first_numeric())
            if x and profit:
                d = generate_bar_chart_data(df, x, profit)
                d["chart_type"] = "treemap"
                _add(d, f"Profit Breakdown by {x.replace('_', ' ').title()}", intent)

        # ── Generic fallbacks ────────────────────────────────────────────────
        # Also handles intents not yet modelled above
        # e.g. if we see an unknown intent, try bar > pie > histogram fallback
        else:
            handled = False
            if category and revenue:
                d = generate_bar_chart_data(df, category, revenue)
                if d.get("data"):
                    d["title"] = f"{revenue.replace('_', ' ').title()} by {category.replace('_', ' ').title()}"
                    d["dataset_name"] = dataset_name
                    d["intent"] = intent
                    key = (d.get("chart_type"), d.get("x_axis_label"), None)
                    if key not in seen:
                        seen.add(key)
                        charts.append(d)
                        handled = True
            if not handled and revenue:
                d = generate_histogram_data(df, revenue)
                if d.get("data"):
                    d["title"] = f"Distribution of {revenue.replace('_', ' ').title()}"
                    d["dataset_name"] = dataset_name
                    d["intent"] = intent
                    key = (d.get("chart_type"), d.get("x_axis_label"), None)
                    if key not in seen:
                        seen.add(key)
                        charts.append(d)

    # ── Final safety net — always include 1 chart even if no intents matched ─
    if not charts:
        _add(
            _fallback_chart(df, cols, dataset_name),
            "Dataset Overview",
            "fallback",
        )

    return charts


def _fallback_chart(df: pd.DataFrame, cols: dict, dataset_name: str) -> dict:
    """Produce at least one meaningful chart from any dataset."""
    numeric = cols.get("numeric", [])
    categorical = cols.get("categorical", [])
    date_col = cols.get("date_col")

    if date_col and numeric:
        c = generate_line_chart_data(df, date_col, [numeric[0]])
        c["dataset_name"] = dataset_name
        return c
    if categorical and numeric:
        c = generate_bar_chart_data(df, categorical[0], numeric[0])
        c["dataset_name"] = dataset_name
        return c
    if numeric:
        c = generate_histogram_data(df, numeric[0])
        c["dataset_name"] = dataset_name
        return c
    return {"chart_type": "table", "data": df.head(20).to_dict(orient="records"), "dataset_name": dataset_name}
