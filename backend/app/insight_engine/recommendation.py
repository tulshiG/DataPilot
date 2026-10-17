def generate_recommendations(sales: dict, inventory: dict, customers: dict, products: dict) -> list[str]:
    """
    Turn raw analysis results into plain-language, actionable recommendations.
    Rule-based: each check is a simple condition -> suggestion.
    """
    recs = []

    if sales.get("trend_direction") == "down":
        recs.append(
            f"Revenue is trending down ({sales.get('overall_change_percent')}% overall). "
            "Consider reviewing recent pricing, marketing spend, or churn among top customers."
        )
    elif sales.get("trend_direction") == "up":
        recs.append(
            f"Revenue is trending up ({sales.get('overall_change_percent')}% overall). "
            "Consider increasing stock for top-performing products to sustain momentum."
        )

    if inventory.get("out_of_stock_count", 0) > 0:
        recs.append(
            f"{inventory['out_of_stock_count']} product(s) are completely out of stock. "
            "Restocking these should be a priority to avoid lost sales."
        )
    if inventory.get("low_stock_count", 0) > 0:
        recs.append(
            f"{inventory['low_stock_count']} product(s) are running low. "
            "Plan reorders soon to avoid stockouts."
        )

    if products.get("worst_performing_products"):
        worst_name = products["worst_performing_products"][0].get("product", "some products")
        recs.append(
            f"'{worst_name}' and similar low-performing products may be worth discounting, "
            "bundling, or discontinuing."
        )

    if customers.get("top_customers"):
        top_customer = customers["top_customers"][0].get("customer", "your top customer")
        recs.append(
            f"'{top_customer}' is your highest-value customer. "
            "Consider a loyalty offer or personal outreach to retain this relationship."
        )

    if sales.get("sudden_changes"):
        recs.append(
            f"{len(sales['sudden_changes'])} sudden revenue spike(s) or drop(s) were detected. "
            "Investigate these periods for one-off events (promotions, outages, seasonal effects)."
        )

    if not recs:
        recs.append("No significant issues detected. Business metrics appear stable.")

    return recs