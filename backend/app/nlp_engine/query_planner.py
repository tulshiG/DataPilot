from app.nlp_engine.indexer import SEMANTIC_ALIASES


def _classify_filter_dimension(column_name: str) -> str:
    """
    Tag a filter's semantic dimension (location, category, status, etc.) using
    the same synonym groups the indexer builds — this is what lets the plan
    say 'Location: Gujarat' / 'Category: Electronics' instead of just
    'filter: some_column = some_value', matching your multi-dimension spec.
    """
    col_lower = column_name.lower()
    for dimension, aliases in SEMANTIC_ALIASES.items():
        if any(alias in col_lower for alias in aliases):
            return dimension
    return "attribute"


def build_query_plan(spec: dict, intent_result: dict, extraction_result: dict, dataset_ranking: list[dict]) -> dict:
    """
    Convert the internal working `spec` dict into a clean, structured query
    plan — a single JSON artifact that fully describes the query before any
    SQL is written. This is the object your SQL generator should treat as its
    only input; nothing downstream should re-derive intent from raw text again.
    """
    top_dataset = dataset_ranking[0] if dataset_ranking else None
    chosen_dataset = None
    if spec.get("primary_table") and dataset_ranking:
        chosen_dataset = next(
            (d for d in dataset_ranking if d.get("table_name") == spec["primary_table"]),
            None,
        )
    chosen_dataset = chosen_dataset or top_dataset

    # Multi-dimension breakdown: classify each filter by semantic type
    # (location / category / status / attribute) rather than one flat list
    dimensions = {}
    for f in spec.get("filters", []):
        dim = _classify_filter_dimension(f["column"])
        dimensions.setdefault(dim, []).append({"column": f["column"], "value": f["value"]})
        
    plan = {
        "dataset": chosen_dataset["name"] if chosen_dataset else None,
        "table": spec.get("primary_table"),
        "dataset_confidence": (
            chosen_dataset.get("confidence")
            if chosen_dataset and "confidence" in chosen_dataset
            else chosen_dataset["score"] if chosen_dataset else None
        ),

        "intent": intent_result.get("intent"),
        "subquery_type": intent_result.get("subquery_type"),

        # select_column covers the simple case; computed_metric (e.g. derived
        # revenue = quantity * price) and multi_metrics (e.g. "quantity and
        # revenue") are just as valid a resolved metric and must count too —
        # otherwise confidence_engine.py sees "no metric" for a query that
        # actually resolved one correctly.
        "metric": (
            spec.get("select_column")
            or (spec.get("computed_metric") or {}).get("alias")
            or (spec.get("multi_metrics")[0]["alias"] if spec.get("multi_metrics") else None)
        ),
        "aggregation": (spec.get("aggregation") or "").upper() or None,

        "group_by": spec.get("group_by_column"),
        "dimensions": dimensions,          # e.g. {"location": [{"column": "state", "value": "Gujarat"}], "category": [...]}
        "filters": spec.get("filters", []), # flat list, kept for SQL generator compatibility

        "joins": spec.get("joins", []),
        "join_hops": spec.get("join_path_hops", 0),

        
        "sort": (spec.get("order_direction") or "").upper() or None,
        "sort_column": spec.get("order_by"),
        "limit": spec.get("limit"),

        "having": spec.get("having_modifier", False),
    }

    return plan
