"""
LLM Engine — Fallback
======================
Graceful degradation when Ollama is unavailable.

This module provides the routing logic that decides which engine to use:

    Priority order:
    1. LLM semantic parser → extract spec → LLM SQL generation (best quality)
    2. LLM semantic parser → extract spec → deterministic SQL (medium quality)
    3. Keyword-based NLP pipeline → deterministic SQL (fallback)

Design:
    • If Ollama is running → try LLM SQL generation first (handles any query)
    • If LLM SQL generation fails → use LLM spec with deterministic SQL builder
    • If Ollama is down → use existing keyword pipeline
    • Log which path was taken for debugging
    • Never crash because of LLM unavailability
"""

import logging
from sqlalchemy.orm import Session

from app.llm_engine.ollama_client import is_available as llm_is_available

logger = logging.getLogger(__name__)


def parse_query_with_fallback(
    raw_query: str,
    db: Session,
    workspace_id: int,
    dataset_id: int | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Attempt LLM-based parsing with SQL generation; fall back to keyword pipeline.

    Returns
    -------
    dict with keys:
        "method" : "llm_sql", "llm", or "keyword"
        "query_spec" : the structured spec (same format either way)
        "intent_result" : intent classification result
        "pipeline_trace" : full trace (keyword path only)
        "confidence" : confidence dict
        "action" : execute/try_alternate/escalate
        "generated_sql" : SQL string or None
        "sql_params" : dict
        "error" : error string or None
        "matched_rule" : matched business rule or None
    """
    # ---- Try LLM path first ----
    if llm_is_available():
        # ---- Pass 1: LLM Semantic Parsing (spec extraction) ----
        llm_spec = None
        try:
            from app.llm_engine.semantic_parser import parse_query as llm_parse_query
            llm_spec = llm_parse_query(raw_query, workspace_id, conversation_history)
        except Exception as e:
            logger.warning(f"LLM semantic parsing failed: {e}")

        # ---- Pass 2: LLM Direct SQL Generation ----
        try:
            from app.llm_engine.llm_sql_generator import generate_sql_with_llm
            llm_sql_result = generate_sql_with_llm(
                raw_query, workspace_id,
                spec=llm_spec,
                conversation_history=conversation_history,
            )

            if llm_sql_result and llm_sql_result.get("sql"):
                logger.info(
                    f"LLM SQL generation succeeded "
                    f"(confidence={llm_sql_result['confidence']}, "
                    f"intent={llm_sql_result['intent']})"
                )

                # Build a compatible spec from whatever the LLM gave us
                spec = llm_spec if llm_spec and llm_spec.get("_llm_parsed") else {}
                spec["_llm_sql"] = True
                spec["_llm_confidence"] = llm_sql_result["confidence"]
                spec["_llm_reasoning"] = llm_sql_result.get("reasoning", "")
                if llm_sql_result.get("tables_used"):
                    spec["primary_table"] = llm_sql_result["tables_used"][0]

                # Build intent result
                intent = llm_sql_result.get("intent", "query")
                intent_result = _build_llm_intent_result(intent, llm_sql_result["confidence"], spec)

                return {
                    "method": "llm_sql",
                    "query_spec": spec,
                    "intent_result": intent_result,
                    "pipeline_trace": {
                        "method": "llm_sql",
                        "user_query": raw_query,
                        "llm_confidence": llm_sql_result["confidence"],
                        "llm_reasoning": llm_sql_result.get("reasoning"),
                        "llm_explanation": llm_sql_result.get("explanation"),
                        "tables_used": llm_sql_result.get("tables_used", []),
                    },
                    "confidence": {
                        "dataset": llm_sql_result["confidence"] * 100,
                        "intent": 95.0 if llm_sql_result["confidence"] >= 0.8 else 75.0,
                        "metric": 90.0,
                        "join": 95.0,
                        "overall": llm_sql_result["confidence"] * 100,
                    },
                    "action": "execute" if llm_sql_result["confidence"] >= 0.5 else "try_alternate",
                    "generated_sql": llm_sql_result["sql"],
                    "sql_params": llm_sql_result.get("params", {}),
                    "error": None,
                    "matched_rule": None,
                    "llm_explanation": llm_sql_result.get("explanation"),
                }
        except Exception as e:
            logger.warning(f"LLM SQL generation failed: {e}")

        # ---- Pass 2b: Use LLM spec with deterministic SQL builder ----
        if llm_spec is not None and llm_spec.get("_llm_parsed"):
            logger.info(
                f"LLM spec parsing succeeded, using deterministic SQL "
                f"(confidence={llm_spec.get('_llm_confidence', '?')})"
            )

            from app.llm_engine.semantic_parser import get_llm_intent_result
            intent_result = get_llm_intent_result(llm_spec)

            intent = llm_spec.get("_llm_parsed_intent") or intent_result.get("intent", "list")
            llm_spec["_llm_parsed_intent"] = intent

            return {
                "method": "llm",
                "query_spec": llm_spec,
                "intent_result": intent_result,
                "pipeline_trace": {
                    "method": "llm",
                    "user_query": raw_query,
                    "llm_confidence": llm_spec.get("_llm_confidence"),
                    "llm_reasoning": llm_spec.get("_llm_reasoning"),
                },
                "confidence": {
                    "dataset": llm_spec.get("_llm_confidence", 0.5) * 100,
                    "intent": 95.0 if intent_result.get("confidence") == "high" else 75.0,
                    "metric": 90.0 if llm_spec.get("select_column") else 55.0,
                    "join": 95.0,
                    "overall": llm_spec.get("_llm_confidence", 0.5) * 100,
                },
                "action": "execute" if llm_spec.get("_llm_confidence", 0) >= 0.6 else "try_alternate",
                "generated_sql": None,  # SQL is generated downstream by sql_generator
                "sql_params": {},
                "error": None,
                "matched_rule": None,
            }

    # ---- Fallback: existing keyword-based pipeline ----
    logger.info("Using keyword-based NLP pipeline (LLM unavailable or failed)")
    from app.nlp_engine.pipeline import NLPQueryPipeline

    pipeline = NLPQueryPipeline(db, workspace_id, dataset_id)
    result = pipeline.execute(raw_query)

    return {
        "method": "keyword",
        "query_spec": result["query_spec"],
        "intent_result": result["intent"],
        "pipeline_trace": result["pipeline_trace"],
        "confidence": result["confidence"],
        "action": result["action"],
        "generated_sql": result["generated_sql"],
        "sql_params": result["sql_params"],
        "error": result["error"],
        "matched_rule": result["matched_rule"],
    }


def _build_llm_intent_result(intent: str, confidence: float, spec: dict) -> dict:
    """
    Build an intent_result dict compatible with the existing pipeline from
    LLM SQL generation results.
    """
    if confidence >= 0.8:
        conf_str = "high"
    elif confidence >= 0.5:
        conf_str = "medium"
    else:
        conf_str = "low"

    return {
        "intent": intent,
        "confidence": conf_str,
        "limit": spec.get("limit"),
        "subquery_type": spec.get("subquery_type"),
        "having_modifier": None,
        "matched_signals": {},
        "is_special": intent in ("generate_dashboard", "generate_insights"),
        "labels": {
            "ranking": "TOP" if intent == "top_n" else "BOTTOM" if intent == "bottom_n" else None,
            "aggregation_function": spec.get("aggregation"),
            "is_trend": intent == "trend",
            "has_filter_language": bool(spec.get("filters")),
            "has_subquery": spec.get("subquery_type") is not None,
            "limit": spec.get("limit"),
        },
        "slots": {
            "is_aggregate": intent in ("aggregate", "calculation"),
            "is_top_n": intent == "top_n",
            "is_bottom_n": intent == "bottom_n",
            "is_trend": intent == "trend",
            "is_distribution": intent == "distribution",
            "is_compare": intent == "compare",
            "has_filter": bool(spec.get("filters") or spec.get("numeric_filters")),
            "implies_group_by": bool(spec.get("group_by_column")),
            "thresholds": [],
            "compare_targets": [],
            "limit": spec.get("limit"),
        },
    }
