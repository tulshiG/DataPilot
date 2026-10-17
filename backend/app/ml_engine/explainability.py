"""
Explainable AI — Query Explainer
====================================
Generates human-readable explanations of how a query was processed,
what decisions the AI made, and why.

This is critical for trust and auditability — users need to understand
*why* the system generated a particular SQL query.

Explanation includes:
    • Intent detection reasoning
    • Entity extraction details
    • Table/column resolution path
    • Filter interpretation
    • Aggregation choices
    • Confidence breakdown
    • Knowledge graph path (if multi-table)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def explain_query(
    raw_query: str,
    spec: dict,
    engine_used: str = "keyword",
    confidence: float = 0.0,
    validation_result: dict | None = None,
    join_path: dict | None = None,
) -> dict:
    """
    Generate a detailed explanation of how a query was processed.

    Parameters
    ----------
    raw_query : str
        The original natural language query.
    spec : dict
        The resolved query_spec.
    engine_used : str
        "llm" or "keyword" — which engine processed the query.
    confidence : float
        Overall confidence score.
    validation_result : dict, optional
        Schema validation results (corrections, warnings).
    join_path : dict, optional
        Knowledge graph join path if multi-table query.

    Returns
    -------
    dict with structured explanation.
    """
    explanation = {
        "query": raw_query,
        "engine": _explain_engine(engine_used),
        "steps": [],
        "confidence": _explain_confidence(confidence),
        "summary": "",
    }

    steps = explanation["steps"]

    # Step 1: Intent
    intent = spec.get("intent") or spec.get("_intent", "explore")
    steps.append({
        "step": 1,
        "name": "Intent Detection",
        "result": intent,
        "detail": _explain_intent(intent),
    })

    # Step 2: Table Resolution
    table = spec.get("primary_table")
    steps.append({
        "step": 2,
        "name": "Table Resolution",
        "result": table or "not resolved",
        "detail": f"Identified '{table}' as the primary data source." if table else "Could not determine the target table.",
    })

    # Step 3: Column Mapping
    select_col = spec.get("select_column")
    group_col = spec.get("group_by_column")
    agg = spec.get("aggregation")

    col_detail = []
    if select_col:
        col_detail.append(f"Selected column: **{select_col}**")
    if agg:
        col_detail.append(f"Aggregation: **{agg}**")
    if group_col:
        col_detail.append(f"Grouped by: **{group_col}**")

    steps.append({
        "step": 3,
        "name": "Column & Metric Resolution",
        "result": f"{agg or 'SELECT'}({select_col or '*'})" + (f" GROUP BY {group_col}" if group_col else ""),
        "detail": " | ".join(col_detail) if col_detail else "No specific columns resolved.",
    })

    # Step 4: Filters
    filters = spec.get("filters", [])
    numeric_filters = spec.get("numeric_filters", [])
    all_filters = filters + numeric_filters

    if all_filters:
        filter_details = []
        for f in all_filters:
            col = f.get("column", "?")
            op = f.get("operator", "=")
            val = f.get("value", "?")
            filter_details.append(f"{col} {op} {val}")

        steps.append({
            "step": 4,
            "name": "Filter Extraction",
            "result": f"{len(all_filters)} filter(s) applied",
            "detail": ", ".join(filter_details),
        })

    # Step 5: Schema Validation
    if validation_result:
        corrections = validation_result.get("corrections", {})
        warnings = validation_result.get("warnings", [])

        if corrections:
            correction_list = [f"'{k}' → '{v}'" for k, v in corrections.items()]
            steps.append({
                "step": 5,
                "name": "Schema Auto-Correction",
                "result": f"{len(corrections)} correction(s)",
                "detail": "Auto-corrected: " + ", ".join(correction_list),
            })

        if warnings:
            steps.append({
                "step": 5,
                "name": "Schema Warnings",
                "result": f"{len(warnings)} warning(s)",
                "detail": "; ".join(w.get("message", "") for w in warnings),
            })

    # Step 6: Join Path (if multi-table)
    if join_path and join_path.get("hops", 0) > 0:
        tables = join_path.get("tables", [])
        joins = join_path.get("joins", [])
        join_details = [
            f"{j['left_table']}.{j['left_column']} → {j['right_table']}.{j['right_column']}"
            for j in joins
        ]
        steps.append({
            "step": 6,
            "name": "Multi-Table Join",
            "result": f"{len(tables)} tables joined ({join_path['hops']} hop(s))",
            "detail": " → ".join(tables) + "\n" + "\n".join(join_details),
        })

    # Step 7: Follow-up Context
    if spec.get("_is_followup"):
        steps.append({
            "step": 7,
            "name": "Follow-up Resolution",
            "result": "Merged with previous query",
            "detail": f"This query was detected as a follow-up and merged with the previous context.",
        })

    # Generate summary
    explanation["summary"] = _generate_summary(spec, engine_used, confidence)

    return explanation


def _explain_engine(engine: str) -> dict:
    """Explain which engine was used and why."""
    if engine == "llm":
        return {
            "name": "LLM Semantic Parser",
            "description": "Query was processed using the local AI model (Ollama/Mistral) with RAG context injection.",
            "icon": "🤖",
        }
    return {
        "name": "Keyword NLP Pipeline",
        "description": "Query was processed using the rule-based keyword matching pipeline.",
        "icon": "🔤",
    }


def _explain_intent(intent: str) -> str:
    """Human-readable intent explanation."""
    intent_map = {
        "aggregate": "Detected an aggregation request (SUM, AVG, COUNT, etc.)",
        "list": "Detected a data listing request (show rows)",
        "compare": "Detected a comparison request (compare values across categories)",
        "trend": "Detected a time-series trend analysis request",
        "filter": "Detected a data filtering request",
        "count": "Detected a counting request",
        "top_n": "Detected a ranking/top-N request",
        "distribution": "Detected a distribution analysis request",
        "explore": "General data exploration query",
    }
    return intent_map.get(intent, f"Detected intent: {intent}")


def _explain_confidence(confidence: float) -> dict:
    """Explain the confidence level."""
    if confidence >= 0.9:
        level = "high"
        icon = "🟢"
        desc = "The system is very confident in this interpretation."
    elif confidence >= 0.7:
        level = "good"
        icon = "🟡"
        desc = "The system is fairly confident. Results should be accurate."
    elif confidence >= 0.5:
        level = "moderate"
        icon = "🟠"
        desc = "Moderate confidence. You may want to verify the results."
    else:
        level = "low"
        icon = "🔴"
        desc = "Low confidence. Consider rephrasing your query for better results."

    return {
        "score": round(confidence, 2),
        "level": level,
        "icon": icon,
        "description": desc,
    }


def _generate_summary(spec: dict, engine_used: str, confidence: float) -> str:
    """Generate a one-line summary of the query interpretation."""
    parts = []

    agg = spec.get("aggregation", "").upper()
    col = spec.get("select_column", "*")
    table = spec.get("primary_table", "unknown")
    group = spec.get("group_by_column")
    filters = spec.get("filters", [])

    if agg and col != "*":
        parts.append(f"Computing {agg}({col})")
    elif col != "*":
        parts.append(f"Selecting {col}")
    else:
        parts.append(f"Querying all columns")

    parts.append(f"from {table}")

    if group:
        parts.append(f"grouped by {group}")

    if filters:
        filter_parts = [f"{f.get('column')}={f.get('value')}" for f in filters[:2]]
        parts.append(f"where {', '.join(filter_parts)}")

    engine_label = "AI" if engine_used == "llm" else "keyword"
    parts.append(f"[{engine_label}, {confidence:.0%} confidence]")

    return " ".join(parts)
