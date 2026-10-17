import pandas as pd
from app.insight_engine.trend_analysis import analyze_trend
from app.insight_engine.anomaly_detection import detect_anomalies, detect_sudden_changes


def analyze_sales(df: pd.DataFrame, date_column: str, revenue_column: str) -> dict:
    """
    Task 1: Sales trend + growth analysis.
    Reuses trend_analysis + anomaly_detection under the hood.
    """
    trend = analyze_trend(df, date_column, revenue_column, freq="M")
    spikes = detect_sudden_changes(trend.get("periods", []))
    anomalies = detect_anomalies(df, revenue_column, method="iqr")

    total_revenue = round(float(pd.to_numeric(df[revenue_column], errors="coerce").sum()), 2)
    avg_order_value = round(float(pd.to_numeric(df[revenue_column], errors="coerce").mean()), 2)

    return {
        "total_revenue": total_revenue,
        "average_order_value": avg_order_value,
        "trend_direction": trend.get("direction"),
        "overall_change_percent": trend.get("overall_change_percent"),
        "monthly_breakdown": trend.get("periods", []),
        "sudden_changes": spikes,
        "unusual_transactions": anomalies.get("anomalies", [])[:5],
    }


def detect_inventory_issues(df: pd.DataFrame, product_column: str, stock_column: str, low_stock_threshold: int = 10) -> dict:
    """
    Task 2: Flag products with low or zero stock.
    """
    if product_column not in df.columns or stock_column not in df.columns:
        return {"error": "Missing required columns"}

    df = df.copy()
    df[stock_column] = pd.to_numeric(df[stock_column], errors="coerce")

    out_of_stock = df[df[stock_column] == 0][[product_column, stock_column]]
    low_stock = df[(df[stock_column] > 0) & (df[stock_column] <= low_stock_threshold)][[product_column, stock_column]]

    return {
        "threshold_used": low_stock_threshold,
        "out_of_stock_count": len(out_of_stock),
        "out_of_stock_products": out_of_stock.rename(columns={product_column: "product", stock_column: "stock"}).to_dict(orient="records"),
        "low_stock_count": len(low_stock),
        "low_stock_products": low_stock.rename(columns={product_column: "product", stock_column: "stock"}).sort_values("stock").to_dict(orient="records")[:20],
    }


def analyze_customers(df: pd.DataFrame, customer_column: str, revenue_column: str, top_n: int = 10) -> dict:
    """
    Task 3: Identify top customers by spend and basic purchasing behavior stats.
    """
    if customer_column not in df.columns or revenue_column not in df.columns:
        return {"error": "Missing required columns"}

    df = df.copy()
    df[revenue_column] = pd.to_numeric(df[revenue_column], errors="coerce")

    grouped = df.groupby(customer_column, as_index=False).agg(
        total_spent=(revenue_column, "sum"),
        order_count=(revenue_column, "count"),
        avg_order_value=(revenue_column, "mean"),
    )

    top_customers = grouped.sort_values("total_spent", ascending=False).head(top_n)
    top_customers["total_spent"] = top_customers["total_spent"].round(2)
    top_customers["avg_order_value"] = top_customers["avg_order_value"].round(2)

    return {
        "total_unique_customers": int(df[customer_column].nunique()),
        "top_customers": top_customers.rename(columns={customer_column: "customer"}).to_dict(orient="records"),
        "avg_orders_per_customer": round(float(grouped["order_count"].mean()), 2),
        "avg_customer_value": round(float(grouped["total_spent"].mean()), 2),
    }


def analyze_products(df: pd.DataFrame, product_column: str, revenue_column: str, quantity_column: str | None = None, top_n: int = 10) -> dict:
    """
    Task 4: Detect best and worst-performing products by revenue (and quantity if available).
    """
    if product_column not in df.columns or revenue_column not in df.columns:
        return {"error": "Missing required columns"}

    df = df.copy()
    df[revenue_column] = pd.to_numeric(df[revenue_column], errors="coerce")

    agg_dict = {"total_revenue": (revenue_column, "sum"), "order_count": (revenue_column, "count")}
    if quantity_column and quantity_column in df.columns:
        df[quantity_column] = pd.to_numeric(df[quantity_column], errors="coerce")
        agg_dict["total_quantity_sold"] = (quantity_column, "sum")

    grouped = df.groupby(product_column, as_index=False).agg(**agg_dict)
    grouped["total_revenue"] = grouped["total_revenue"].round(2)

    best = grouped.sort_values("total_revenue", ascending=False).head(top_n)
    worst = grouped.sort_values("total_revenue", ascending=True).head(top_n)

    return {
        "total_unique_products": int(df[product_column].nunique()),
        "best_performing_products": best.rename(columns={product_column: "product"}).to_dict(orient="records"),
        "worst_performing_products": worst.rename(columns={product_column: "product"}).to_dict(orient="records"),
    }