"""
LLM Engine — Semantic Parser
================================
The main entry point for LLM-based query understanding.

Flow:
    1. Receive raw user query
    2. Retrieve relevant context via RAG
    3. Build prompt with context + query
    4. Call Ollama LLM for structured JSON extraction
    5. Validate response with Pydantic
    6. Convert to the internal query_spec format expected by sql_generator.py

This module NEVER generates SQL.  It produces a structured spec that feeds
into the existing deterministic query engine (query_mapper → sql_generator).

The key design decision: the LLM output is translated into the SAME spec
format that the existing keyword-based pipeline produces, so sql_generator.py
doesn't need to change at all.
"""

import logging

from app.rag_engine.rag_retriever import retrieve_context
from app.rag_engine.context_assembler import assemble_context
from app.llm_engine.ollama_client import chat, is_available
from app.llm_engine.prompt_templates import build_messages
from app.llm_engine.response_validator import validate_llm_response, LLMQuerySpec

logger = logging.getLogger(__name__)


def parse_query(raw_query: str, workspace_id: int,
                conversation_history: list[dict] | None = None) -> dict | None:
    """
    Parse a natural language query using the LLM + RAG pipeline.

    Parameters
    ----------
    raw_query : str
        The user's natural language query.
    workspace_id : int
        Workspace for RAG context retrieval.
    conversation_history : list[dict], optional
        Previous conversation turns for follow-up resolution.

    Returns
    -------
    dict or None
        A query_spec dict compatible with the existing sql_generator.py,
        or None if the LLM is unavailable or fails.
    """
    if not is_available():
        logger.info("Ollama not available — LLM parsing skipped")
        return None

    # Step 1: Retrieve RAG context
    chunks = retrieve_context(workspace_id, raw_query, k=8)
    context_text = assemble_context(chunks)

    # Step 2: Build LLM messages
    messages = build_messages(raw_query, context_text, conversation_history)

    # Step 3: Call LLM
    logger.info(f"Calling LLM for query: '{raw_query[:80]}...'")
    raw_response = chat(messages, temperature=0.1, format_json=True)

    if raw_response is None:
        logger.warning("LLM returned no response")
        return None

    # Step 4: Validate response
    spec = validate_llm_response(raw_response)
    if spec is None:
        logger.warning("LLM response failed validation")
        return None

    # Step 5: Convert to internal query_spec format
    return _convert_to_query_spec(spec, raw_query)


def _convert_to_query_spec(llm_spec: LLMQuerySpec, raw_query: str) -> dict:
    """
    Convert the validated LLM output into the internal query_spec format
    that sql_generator.py expects.

    This is the bridge between the new LLM-based parser and the existing
    deterministic query engine.  The mapping preserves every field that
    sql_generator.py reads from the spec.
    """
    spec: dict = {}

    # Intent mapping
    intent = llm_spec.intent
    is_special = intent in ("generate_dashboard", "generate_insights")

    # Table resolution
    if llm_spec.tables:
        spec["primary_table"] = llm_spec.tables[0]

    # Metric / select column
    if llm_spec.metrics:
        primary_metric = llm_spec.metrics[0]
        spec["select_column"] = primary_metric.column
        spec["aggregation"] = primary_metric.aggregation

        if len(llm_spec.metrics) > 1:
            spec["multi_metrics"] = [
                {"column": m.column, "aggregation": m.aggregation, "alias": m.column}
                for m in llm_spec.metrics
            ]

    # Group by
    if llm_spec.group_by:
        spec["group_by_column"] = llm_spec.group_by[0]
        if len(llm_spec.group_by) > 1:
            spec["additional_group_by"] = llm_spec.group_by[1:]

    # Filters — convert from LLM format to existing spec format
    filters = []
    for f in llm_spec.filters:
        filter_entry = {"column": f.column, "value": f.value}
        if f.operator and f.operator != "eq":
            filter_entry["operator"] = f.operator
        filters.append(filter_entry)
    if filters:
        spec["filters"] = filters

    # Numeric filters (threshold-style)
    numeric_filters = []
    for f in llm_spec.filters:
        if f.operator in ("gt", "gte", "lt", "lte", "between") and isinstance(f.value, (int, float)):
            op_map = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
            numeric_filters.append({
                "column": f.column,
                "operator": op_map.get(f.operator, "="),
                "value": f.value,
            })
    if numeric_filters:
        spec["numeric_filters"] = numeric_filters

    # Time range
    if llm_spec.time_range:
        spec["time_filter"] = {
            "column": llm_spec.time_range.column,
            "start": llm_spec.time_range.start,
            "end": llm_spec.time_range.end,
        }
        if llm_spec.time_range.granularity:
            spec["period"] = llm_spec.time_range.granularity

    # Sort / Order
    if llm_spec.sort and llm_spec.sort.column:
        spec["order_by"] = llm_spec.sort.column
        spec["order_direction"] = llm_spec.sort.direction or "DESC"

    # Limit
    if llm_spec.limit:
        spec["limit"] = llm_spec.limit

    # Subquery
    if llm_spec.subquery_type:
        spec["subquery_type"] = llm_spec.subquery_type

    # LLM-specific metadata
    spec["_llm_confidence"] = llm_spec.confidence
    spec["_llm_reasoning"] = llm_spec.reasoning
    spec["_llm_parsed"] = True
    spec["_llm_parsed_intent"] = intent  # CRITICAL: must be set for get_llm_intent_result()
    spec["_raw_query"] = raw_query

    return spec


def get_llm_intent_result(llm_spec_dict: dict) -> dict:
    """
    Convert the LLM-produced spec into the intent_result format that the
    existing pipeline expects (compatibility with query_planner, confidence_engine, etc.).
    """
    intent = llm_spec_dict.get("_llm_parsed_intent", "list")
    confidence = llm_spec_dict.get("_llm_confidence", 0.5)

    # Map LLM confidence (0-1 float) to the existing string system
    if confidence >= 0.8:
        conf_str = "high"
    elif confidence >= 0.5:
        conf_str = "medium"
    else:
        conf_str = "low"

    return {
        "intent": intent,
        "confidence": conf_str,
        "limit": llm_spec_dict.get("limit"),
        "subquery_type": llm_spec_dict.get("subquery_type"),
        "having_modifier": None,
        "matched_signals": {},
        "is_special": intent in ("generate_dashboard", "generate_insights"),
        "labels": {
            "ranking": "TOP" if intent == "top_n" else "BOTTOM" if intent == "bottom_n" else None,
            "aggregation_function": llm_spec_dict.get("aggregation"),
            "is_trend": intent == "trend",
            "has_filter_language": bool(llm_spec_dict.get("filters")),
            "has_subquery": llm_spec_dict.get("subquery_type") is not None,
            "limit": llm_spec_dict.get("limit"),
        },
        "slots": {
            "is_aggregate": intent == "aggregate" or bool(llm_spec_dict.get("aggregation")),
            "is_top_n": intent == "top_n",
            "is_bottom_n": intent == "bottom_n",
            "is_trend": intent == "trend",
            "is_distribution": intent == "distribution",
            "is_compare": intent == "compare",
            "has_filter": bool(llm_spec_dict.get("filters") or llm_spec_dict.get("numeric_filters")),
            "implies_group_by": bool(llm_spec_dict.get("group_by_column")),
            "thresholds": [],
            "compare_targets": [],
            "limit": llm_spec_dict.get("limit"),
        },
    }
