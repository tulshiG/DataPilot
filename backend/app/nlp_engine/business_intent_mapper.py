# Maps business phrases directly to (aggregation, column-hint, sort-direction, extra-filter)
# without needing the literal word "average" or "highest" — this is what lets
# "best performing product" resolve to MAX(revenue)-style logic automatically.
BUSINESS_INTENT_RULES = [
    {"phrases": ["best performing", "best seller", "top performer"], "aggregation": "SUM", "metric_hint": ["revenue", "sales"], "sort": "DESC"},
    {"phrases": ["worst performing", "worst seller"], "aggregation": "SUM", "metric_hint": ["revenue", "sales"], "sort": "ASC"},
    {"phrases": ["most profitable"], "aggregation": "SUM", "metric_hint": ["profit"], "sort": "DESC"},
    {"phrases": ["least profitable"], "aggregation": "SUM", "metric_hint": ["profit"], "sort": "ASC"},
    {"phrases": ["biggest spender", "big customers", "big customer"], "aggregation": "SUM", "metric_hint": ["revenue", "sales", "amount"], "sort": "DESC"},
    {"phrases": ["restock", "need to reorder", "low stock", "running low"], "numeric_filter_hint": {"column_hint": ["stock", "inventory", "quantity"], "operator": "<", "threshold": 10}},
    {"phrases": ["unsold", "never sold", "no sales"], "special": "unsold"},
    {"phrases": ["declining", "dropping", "decreasing"], "trend_direction": "down"},
    {"phrases": ["growing", "increasing", "rising"], "trend_direction": "up"},
]


def match_business_intent(cleaned_text: str) -> dict | None:
    for rule in BUSINESS_INTENT_RULES:
        if any(phrase in cleaned_text for phrase in rule["phrases"]):
            return {k: v for k, v in rule.items() if k != "phrases"}
    return None


def resolve_metric_hint_to_column(metric_hints: list[str], numeric_columns: list[str], synonyms: dict) -> str | None:
    """Turn a business-intent metric hint (e.g. ['revenue','sales']) into a real column name."""
    for hint in metric_hints:
        for col in numeric_columns:
            col_lower = col.lower()
            if hint in col_lower:
                return col
            if hint in synonyms.get(col, []):
                return col
    return None