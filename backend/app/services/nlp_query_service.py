from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
import logging

from app.llm_engine.fallback import parse_query_with_fallback
from app.nlp_engine.pipeline import NLPQueryPipeline
from app.services.history_service import log_query
from app.core.config import settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)


def _execute_sql(sql: str, params: dict) -> tuple[list[str], list[dict]]:
    # Convert psycopg2-style named placeholders to SQLAlchemy text() syntax.
    # Example: %(filter_0)s -> :filter_0
    sql = re.sub(
        r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s",
        r":\1",
        sql,
    )

    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            columns = list(result.keys())
            rows = [dict(row) for row in result.mappings().all()]
            return columns, rows
    finally:
        engine.dispose()


def run_query(
    db: Session, workspace_id: int, user_id: int, raw_query: str,
    dataset_id: int | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Main query entry point — orchestrates:
        1. Conversation context (follow-up detection)
        2. LLM SQL generation (best path — handles ANY query)
        3. LLM spec-based parsing (with RAG context)
        4. Keyword pipeline fallback
        5. Schema validation (auto-correct misspelled columns)
        6. SQL generation + validation
        7. Execution + logging
    """
    # ──────────────────────────────────────────────────────────────────────
    # Step 0: Conversation context
    # ──────────────────────────────────────────────────────────────────────
    conversation_history = None
    session = None
    try:
        from app.conversation.session_manager import get_or_create_session
        from app.conversation.context_stack import is_followup, merge_specs

        session = get_or_create_session(workspace_id, user_id, session_id)
        conversation_history = session.get_history_for_llm() if session.turn_count > 0 else None
    except Exception as e:
        logger.debug(f"Conversation context not available: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 1: Parse the query (LLM SQL → LLM spec → keyword fallback)
    # ──────────────────────────────────────────────────────────────────────
    parsed = parse_query_with_fallback(
        raw_query, db, workspace_id, dataset_id,
        conversation_history=conversation_history,
    )
    engine_used = parsed["method"]  # "llm_sql", "llm", or "keyword"

    # ──────────────────────────────────────────────────────────────────────
    # Step 2: Handle LLM-generated SQL (direct execution path)
    # ──────────────────────────────────────────────────────────────────────
    if engine_used == "llm_sql" and parsed.get("generated_sql"):
        result = _handle_llm_sql_result(
            db, workspace_id, user_id, raw_query, parsed, session
        )
        return result

    # If keyword path was used, result is a full pipeline result
    if engine_used == "keyword":
        result = _handle_keyword_result(db, workspace_id, user_id, raw_query, parsed)
        _record_conversation_turn(session, raw_query, parsed.get("query_spec"), result.get("summary"))
        return result

    # ──────────────────────────────────────────────────────────────────────
    # Step 3: LLM spec path — Follow-up merge (if conversation context exists)
    # ──────────────────────────────────────────────────────────────────────
    spec = parsed["query_spec"]
    intent_result = parsed["intent_result"]
    intent = intent_result.get("intent", "list")
    action = parsed["action"]

    try:
        if session and session.last_spec and is_followup(raw_query):
            spec = merge_specs(session.last_spec, spec, raw_query)
            logger.info(f"Follow-up detected — merged with previous spec")
    except Exception as e:
        logger.debug(f"Follow-up merge skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 4: Schema validation (auto-correct column names)
    # ──────────────────────────────────────────────────────────────────────
    validation = None
    try:
        from app.query_engine.schema_validator import validate_query_spec
        validation = validate_query_spec(db, workspace_id, spec, auto_correct=True)
        if not validation.valid:
            logger.warning(f"Schema validation failed: {validation.errors}")
    except Exception as e:
        logger.debug(f"Schema validation skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 5: SQL generation
    # ──────────────────────────────────────────────────────────────────────
    sql, params = None, {}

    if action == "execute" and spec.get("primary_table"):
        try:
            from app.nlp_engine.sql_generator import generate_sql
            sql, params = generate_sql(spec)
        except Exception as e:
            logger.warning(f"LLM spec → SQL failed: {e}, falling back to keyword pipeline")
            keyword_parsed = _run_keyword_pipeline(db, workspace_id, dataset_id, raw_query)
            result = _handle_keyword_result(db, workspace_id, user_id, raw_query, keyword_parsed)
            _record_conversation_turn(session, raw_query, spec, result.get("summary"))
            return result

    # If LLM didn't resolve a table, fall back to keyword pipeline
    if not sql:
        keyword_parsed = _run_keyword_pipeline(db, workspace_id, dataset_id, raw_query)
        result = _handle_keyword_result(db, workspace_id, user_id, raw_query, keyword_parsed)
        _record_conversation_turn(session, raw_query, spec, result.get("summary"))
        return result

    # ──────────────────────────────────────────────────────────────────────
    # Step 6: SQL safety validation
    # ──────────────────────────────────────────────────────────────────────
    try:
        from app.query_engine.sql_validator import validate_sql
        sql_check = validate_sql(sql)
        if not sql_check.safe:
            logger.error(f"SQL safety check failed: {sql_check.errors}")
            raise BadRequestException(f"Generated SQL failed safety check: {sql_check.errors}")
        sql = sql_check.final_sql  # may have LIMIT added
    except ImportError:
        pass  # sql_validator not available, proceed without
    except BadRequestException:
        raise
    except Exception as e:
        logger.debug(f"SQL validation skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 6b: SQL optimization
    # ──────────────────────────────────────────────────────────────────────
    try:
        from app.query_engine.sql_optimizer import optimize_sql
        opt_result = optimize_sql(sql, spec)
        if opt_result["was_modified"]:
            logger.info(f"SQL optimized: {opt_result['optimizations_applied']}")
            sql = opt_result["optimized_sql"]
    except Exception as e:
        logger.debug(f"SQL optimization skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 7: Execute SQL and return results
    # ──────────────────────────────────────────────────────────────────────
    try:
        columns, rows = _execute_sql(sql, params)
    except Exception as e:
        log_query(db, workspace_id, user_id, raw_query, intent=intent,
                  sql=sql, spec=spec, status="failed", error_message=str(e))
        raise BadRequestException(f"Could not process query: {str(e)}")

    summary = _build_summary(rows, columns)

    log_query(db, workspace_id, user_id, raw_query, intent=intent,
              sql=sql, spec=spec, status="success", row_count=len(rows))

    # Record in conversation
    _record_conversation_turn(session, raw_query, spec, summary, sql)

    # ──────────────────────────────────────────────────────────────────────
    # Step 8: Normalize confidence + Explainability + Chart Recommendation
    # ──────────────────────────────────────────────────────────────────────
    raw_conf = parsed["confidence"]
    if isinstance(raw_conf, dict):
        conf_score = (raw_conf.get("overall") or 50.0) / 100.0
    elif isinstance(raw_conf, (int, float)):
        conf_score = raw_conf if raw_conf <= 1 else raw_conf / 100.0
    else:
        conf_score = 0.5

    explanation = None
    try:
        from app.ml_engine.explainability import explain_query
        explanation = explain_query(
            raw_query, spec, engine_used, conf_score,
            validation.to_dict() if validation else None,
        )
    except Exception:
        pass

    chart_recommendation = None
    try:
        from app.ml_engine.chart_recommender import recommend_chart
        chart_recommendation = recommend_chart(columns, rows, spec)
    except Exception:
        pass

    return {
        "raw_query": raw_query,
        "needs_clarification": False,
        "candidates": [],
        "intent": intent,
        "matched_rule": parsed.get("matched_rule"),
        "generated_sql": sql,
        "engine_used": engine_used,
        "confidence": conf_score,
        "query_plan": spec,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "summary": summary,
        "llm_reasoning": spec.get("_llm_reasoning"),
        "session_id": session.session_id if session else None,
        "is_followup": spec.get("_is_followup", False),
        "schema_corrections": validation.corrections if validation else {},
        "explanation": explanation,
        "chart_recommendation": chart_recommendation,
    }


def _handle_llm_sql_result(
    db: Session, workspace_id: int, user_id: int,
    raw_query: str, parsed: dict, session,
) -> dict:
    """
    Handle the LLM-generated SQL path — validate, execute, return.
    This is the highest-quality path: the LLM wrote SQL directly.
    """
    sql = parsed["generated_sql"]
    params = parsed.get("sql_params", {})
    spec = parsed.get("query_spec", {})
    intent_result = parsed.get("intent_result", {})
    intent = intent_result.get("intent", "query")

    # SQL safety validation
    try:
        from app.query_engine.sql_validator import validate_sql
        sql_check = validate_sql(sql)
        if not sql_check.safe:
            logger.warning(f"LLM SQL safety check failed: {sql_check.errors}")
            # Fall back to keyword pipeline
            return _fallback_to_keyword(db, workspace_id, user_id, raw_query, session, spec)
        sql = sql_check.final_sql
    except ImportError:
        pass  # sql_validator not available, proceed with basic check
    except Exception as e:
        logger.debug(f"SQL validation skipped: {e}")

    # Execute
    try:
        columns, rows = _execute_sql(sql, params)
    except Exception as e:
        logger.warning(f"LLM SQL execution failed: {e}. Falling back to keyword pipeline.")
        log_query(db, workspace_id, user_id, raw_query, intent=intent,
                  sql=sql, spec=spec, status="failed", error_message=str(e))
        # Fall back to keyword pipeline on SQL error
        return _fallback_to_keyword(db, workspace_id, user_id, raw_query, session, spec)

    summary = _build_smart_summary(rows, columns, raw_query, intent)

    log_query(db, workspace_id, user_id, raw_query, intent=intent,
              sql=sql, spec=spec, status="success", row_count=len(rows))

    _record_conversation_turn(session, raw_query, spec, summary, sql)

    # Confidence
    raw_conf = parsed.get("confidence", {})
    if isinstance(raw_conf, dict):
        conf_score = (raw_conf.get("overall") or 80.0) / 100.0
    elif isinstance(raw_conf, (int, float)):
        conf_score = raw_conf if raw_conf <= 1 else raw_conf / 100.0
    else:
        conf_score = 0.8

    # Explainability
    explanation = parsed.get("llm_explanation") or ""
    try:
        from app.ml_engine.explainability import explain_query
        explanation = explain_query(raw_query, spec, "llm_sql", conf_score)
    except Exception:
        pass

    # Chart recommendation
    chart_recommendation = None
    try:
        from app.ml_engine.chart_recommender import recommend_chart
        chart_recommendation = recommend_chart(columns, rows, spec)
    except Exception:
        pass

    return {
        "raw_query": raw_query,
        "needs_clarification": False,
        "candidates": [],
        "intent": intent,
        "matched_rule": None,
        "generated_sql": sql,
        "engine_used": "llm_sql",
        "confidence": conf_score,
        "query_plan": spec,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "summary": summary,
        "llm_reasoning": spec.get("_llm_reasoning") or parsed.get("pipeline_trace", {}).get("llm_reasoning"),
        "session_id": session.session_id if session else None,
        "is_followup": spec.get("_is_followup", False),
        "schema_corrections": {},
        "explanation": explanation,
        "chart_recommendation": chart_recommendation,
    }


def _fallback_to_keyword(
    db: Session, workspace_id: int, user_id: int,
    raw_query: str, session, spec: dict,
) -> dict:
    """When LLM SQL execution fails, fall back to the keyword pipeline."""
    keyword_parsed = _run_keyword_pipeline(db, workspace_id, None, raw_query)
    result = _handle_keyword_result(db, workspace_id, user_id, raw_query, keyword_parsed)
    _record_conversation_turn(session, raw_query, spec, result.get("summary"))
    return result


def _record_conversation_turn(session, query, spec, summary, sql=None):
    """Record a query turn in the conversation session."""
    if not session:
        return
    try:
        from app.conversation.session_manager import record_turn
        record_turn(session, query, spec, summary, sql)
    except Exception:
        pass


def _run_keyword_pipeline(db: Session, workspace_id: int, dataset_id: int | None, raw_query: str) -> dict:
    """Run the existing keyword-based NLP pipeline and return a unified result dict."""
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
        "query_plan": result.get("query_plan", {}),
    }


def _handle_keyword_result(db: Session, workspace_id: int, user_id: int, raw_query: str, parsed: dict) -> dict:
    """Process results from the keyword-based NLP pipeline (existing logic preserved)."""
    result = parsed
    action = result["action"]
    spec = result["query_spec"]
    intent = result["intent_result"]["intent"] if isinstance(result["intent_result"], dict) else result["intent_result"]

    sql, params = None, {}

    if action == "execute" and result.get("generated_sql") and not result.get("error"):
        sql, params = result["generated_sql"], result.get("sql_params", {})

    elif action == "try_alternate":
        ranking = result.get("pipeline_trace", {}).get("dataset_ranking", [])
        for candidate in ranking[1:4]:
            alt_pipeline = NLPQueryPipeline(db, workspace_id, candidate["dataset_id"])
            alt_result = alt_pipeline.execute(raw_query)
            if alt_result["action"] == "execute" and alt_result["generated_sql"] and not alt_result["error"]:
                sql, params = alt_result["generated_sql"], alt_result["sql_params"]
                result = {
                    "method": "keyword",
                    "query_spec": alt_result["query_spec"],
                    "intent_result": alt_result["intent"],
                    "pipeline_trace": alt_result["pipeline_trace"],
                    "confidence": alt_result["confidence"],
                    "action": alt_result["action"],
                    "generated_sql": alt_result["generated_sql"],
                    "sql_params": alt_result["sql_params"],
                    "error": alt_result["error"],
                    "matched_rule": alt_result["matched_rule"],
                    "query_plan": alt_result.get("query_plan", {}),
                }
                intent = alt_result["intent"]["intent"]
                break

    # Resilience layer
    if not sql:
        primary_table = spec.get("primary_table")
        if primary_table:
            try:
                from app.nlp_engine.sql_generator import generate_sql
                sql, params = generate_sql(spec)
            except Exception:
                sql = f'SELECT * FROM "{primary_table}" LIMIT 50'
                params = {}

    if not sql:
        ranking = result.get("pipeline_trace", {}).get("dataset_ranking", [])
        candidates = [{"dataset_id": r["dataset_id"], "name": r["name"], "score": r["score"]} for r in ranking[:4]]
        log_query(db, workspace_id, user_id, raw_query, intent=intent,
                  sql=None, spec=spec, status="failed",
                  error_message="No datasets found in workspace")
        return {
            "raw_query": raw_query,
            "needs_clarification": True,
            "message": "No datasets found in this workspace. Please upload and process a dataset first.",
            "candidates": candidates,
            "confidence": result["confidence"],
            "columns": [], "rows": [], "row_count": 0,
            "intent": intent, "matched_rule": None,
            "generated_sql": None, "engine_used": "keyword", "summary": "",
        }

    # SQL safety validation for keyword pipeline too
    try:
        from app.query_engine.sql_validator import validate_sql
        sql_check = validate_sql(sql)
        if not sql_check.safe:
            raise BadRequestException(f"Generated SQL failed safety check: {sql_check.errors}")
        sql = sql_check.final_sql
    except (ImportError, BadRequestException):
        pass
    except Exception:
        pass

    try:
        columns, rows = _execute_sql(sql, params)
    except Exception as e:
        log_query(db, workspace_id, user_id, raw_query, intent=intent,
                  sql=sql, spec=spec, status="failed", error_message=str(e))
        raise BadRequestException(f"Could not process query: {str(e)}")

    summary = _build_summary(rows, columns)

    log_query(db, workspace_id, user_id, raw_query, intent=intent,
              sql=sql, spec=spec, status="success", row_count=len(rows))

    # Normalize confidence
    kw_conf = result.get("confidence", {})
    if isinstance(kw_conf, dict):
        kw_conf_score = (kw_conf.get("overall") or 50.0) / 100.0
    elif isinstance(kw_conf, (int, float)):
        kw_conf_score = kw_conf if kw_conf <= 1 else kw_conf / 100.0
    else:
        kw_conf_score = 0.5

    # Explainability + Chart Recommendation
    kw_explanation = None
    try:
        from app.ml_engine.explainability import explain_query
        kw_explanation = explain_query(raw_query, spec, "keyword", kw_conf_score)
    except Exception:
        pass

    kw_chart_rec = None
    try:
        from app.ml_engine.chart_recommender import recommend_chart
        kw_chart_rec = recommend_chart(columns, rows, spec)
    except Exception:
        pass

    return {
        "raw_query": raw_query,
        "needs_clarification": False,
        "candidates": [],
        "intent": intent,
        "matched_rule": result.get("matched_rule"),
        "generated_sql": sql,
        "engine_used": "keyword",
        "confidence": kw_conf_score,
        "query_plan": result.get("query_plan", {}),
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "summary": summary,
        "explanation": kw_explanation,
        "chart_recommendation": kw_chart_rec,
        "schema_corrections": {},
        "is_followup": False,
        "session_id": None,
    }


def _build_summary(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "No results were found for this query."
    if len(rows) == 1 and "value" in columns:
        return f"The result is {rows[0]['value']}."
    return f"Found {len(rows)} matching row(s)."


def _build_smart_summary(rows: list[dict], columns: list[str],
                         raw_query: str, intent: str) -> str:
    """Build a richer summary for LLM-generated SQL results."""
    if not rows:
        return "No results were found for this query."

    query_lower = raw_query.lower()

    # Single aggregate value
    if len(rows) == 1 and len(columns) == 1:
        val = rows[0][columns[0]]
        formatted = _format_value(val)
        if "average" in query_lower or "avg" in query_lower:
            return f"The average is {formatted}."
        if "count" in query_lower or "how many" in query_lower:
            return f"The count is {formatted}."
        if "total" in query_lower or "sum" in query_lower:
            return f"The total is {formatted}."
        return f"The result is {formatted}."

    # Single row with named value column
    if len(rows) == 1 and "value" in columns:
        val = rows[0]["value"]
        return f"The result is {_format_value(val)}."

    # Grouped results
    if any("total" in c.lower() or "sum" in c.lower() or "avg" in c.lower()
           or "count" in c.lower() or "revenue" in c.lower()
           for c in columns):
        if intent in ("top_n", "bottom_n", "ranking"):
            label = "top" if intent in ("top_n", "ranking") else "bottom"
            return f"Found {len(rows)} {label} result(s), ranked by value."

        # Find the best group and value columns
        group_col = None
        value_col = None
        for c in columns:
            cl = c.lower()
            if any(kw in cl for kw in ["total", "sum", "avg", "count", "revenue", "amount", "value"]):
                value_col = c
            elif group_col is None:
                group_col = c

        if group_col and value_col and rows:
            top_row = rows[0]
            return (
                f"Found {len(rows)} result(s). "
                f"Top entry: {top_row.get(group_col, '?')} with "
                f"{_format_value(top_row.get(value_col, '?'))}."
            )

    # Trend results
    if intent == "trend" or any("month" in c.lower() or "period" in c.lower()
                                 or "date" in c.lower() or "year" in c.lower()
                                 for c in columns):
        return f"Showing {len(rows)} time period(s) of data."

    # Window function / percentage results
    if any("pct" in c.lower() or "percent" in c.lower() or "growth" in c.lower()
           or "rank" in c.lower() or "running" in c.lower()
           for c in columns):
        return f"Computed {len(rows)} row(s) with analytical calculations."

    return f"Found {len(rows)} matching row(s)."


def _format_value(val) -> str:
    """Format a numeric or string value nicely."""
    if isinstance(val, float):
        if val == int(val):
            return f"{int(val):,}"
        return f"{val:,.2f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)
