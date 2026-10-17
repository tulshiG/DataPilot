"""
LLM Engine — Direct SQL Generator
====================================
Lets the LLM generate actual PostgreSQL SQL from natural language.

This is the key upgrade over the spec-based approach: instead of forcing
the LLM to output a rigid JSON spec (which then gets compiled by the
deterministic sql_generator), we give the LLM the full database schema
and let it write SQL directly.

Why this is better:
    • Handles ANY SQL construct: window functions, CTEs, CASE/WHEN,
      percentiles, running totals, pivots, correlations, etc.
    • The LLM understands the user's intent holistically, not through
      a lossy structured intermediate representation.
    • The deterministic pipeline still exists as a fallback.

Safety:
    • All generated SQL goes through sql_validator.py (no DDL, no mutations)
    • LIMIT is enforced (max 1000 rows)
    • Only SELECT statements are allowed
    • Parameters are extracted where possible
"""

import json
import logging
import re

from app.llm_engine.ollama_client import chat, is_available
from app.llm_engine.prompt_templates import build_sql_generation_messages
from app.rag_engine.rag_retriever import retrieve_context
from app.rag_engine.context_assembler import assemble_context

logger = logging.getLogger(__name__)

# Maximum rows we allow in generated SQL
MAX_RESULT_ROWS = 1000


def generate_sql_with_llm(
    raw_query: str,
    workspace_id: int,
    spec: dict | None = None,
    conversation_history: list[dict] | None = None,
) -> dict | None:
    """
    Ask the LLM to generate SQL directly from a natural language query.

    Parameters
    ----------
    raw_query : str
        The user's natural language query.
    workspace_id : int
        Workspace for RAG context retrieval.
    spec : dict, optional
        An already-parsed spec from the semantic parser (provides hints).
    conversation_history : list[dict], optional
        Previous conversation turns for follow-up resolution.

    Returns
    -------
    dict or None
        {
            "sql": str,              # The generated SQL
            "params": dict,          # Extracted parameters (if any)
            "explanation": str,      # Human-readable explanation
            "confidence": float,     # 0.0 - 1.0
            "intent": str,           # Detected intent
            "tables_used": list,     # Tables referenced
        }
        Returns None if the LLM is unavailable or generation fails.
    """
    if not is_available():
        logger.info("Ollama not available — LLM SQL generation skipped")
        return None

    # Step 1: Retrieve rich RAG context (schema, columns, relationships, samples)
    chunks = retrieve_context(workspace_id, raw_query, k=12)
    context_text = assemble_context(chunks, max_tokens_estimate=3000)

    # Step 2: Add spec hints if available (helps LLM understand what tables/cols match)
    spec_hint = ""
    if spec:
        hint_parts = []
        if spec.get("primary_table"):
            hint_parts.append(f"Primary table: {spec['primary_table']}")
        if spec.get("select_column"):
            hint_parts.append(f"Metric column: {spec['select_column']}")
        if spec.get("group_by_column"):
            hint_parts.append(f"Group by: {spec['group_by_column']}")
        if spec.get("filters"):
            hint_parts.append(f"Filters detected: {json.dumps(spec['filters'])}")
        if spec.get("aggregation"):
            hint_parts.append(f"Aggregation: {spec['aggregation']}")
        if hint_parts:
            spec_hint = "\n\nPre-parsed hints from keyword analysis:\n" + "\n".join(f"- {h}" for h in hint_parts)

    # Step 3: Build LLM messages
    messages = build_sql_generation_messages(
        raw_query, context_text + spec_hint, conversation_history
    )

    # Step 4: Call LLM
    logger.info(f"LLM SQL generation for: '{raw_query[:80]}...'")
    raw_response = chat(messages, temperature=0.1, format_json=True)

    if raw_response is None:
        logger.warning("LLM returned no response for SQL generation")
        return None

    # Step 5: Validate and clean the response
    return _validate_sql_response(raw_response, raw_query)


def _validate_sql_response(raw_response: dict, raw_query: str) -> dict | None:
    """
    Validate the LLM's SQL generation response.
    Ensures safety, adds LIMIT, extracts metadata.
    """
    if not isinstance(raw_response, dict):
        logger.warning("LLM SQL response is not a dict")
        return None

    sql = raw_response.get("sql", "").strip()
    if not sql:
        logger.warning("LLM returned empty SQL")
        return None

    # Strip markdown code fences if present
    sql = _strip_code_fences(sql)

    # Safety check: only SELECT statements
    sql_normalized = sql.strip().upper()
    if not sql_normalized.startswith("SELECT") and not sql_normalized.startswith("WITH"):
        logger.warning(f"LLM generated non-SELECT SQL: {sql[:100]}")
        return None

    # Block dangerous keywords
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER",
                  "CREATE", "GRANT", "REVOKE", "EXECUTE", "EXEC"]
    sql_upper = sql.upper()
    for kw in dangerous:
        # Check for keyword as whole word (not part of column name)
        if re.search(rf'\b{kw}\b', sql_upper):
            logger.warning(f"LLM generated SQL with dangerous keyword: {kw}")
            return None

    # Enforce LIMIT
    if not re.search(r'\bLIMIT\b', sql_upper):
        sql = sql.rstrip(';').rstrip() + f" LIMIT {MAX_RESULT_ROWS}"

    # Extract limit value and cap it
    limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
    if limit_match:
        limit_val = int(limit_match.group(1))
        if limit_val > MAX_RESULT_ROWS:
            sql = re.sub(
                r'\bLIMIT\s+\d+',
                f'LIMIT {MAX_RESULT_ROWS}',
                sql,
                flags=re.IGNORECASE
            )

    # Remove any trailing semicolons (prevents multi-statement injection)
    sql = sql.rstrip(';').strip()

    # Build result
    confidence = raw_response.get("confidence", 0.7)
    if isinstance(confidence, (int, float)):
        confidence = max(0.0, min(1.0, float(confidence)))
    else:
        confidence = 0.7

    return {
        "sql": sql,
        "params": raw_response.get("params", {}),
        "explanation": raw_response.get("explanation", ""),
        "confidence": confidence,
        "intent": raw_response.get("intent", "query"),
        "tables_used": raw_response.get("tables_used", []),
        "reasoning": raw_response.get("reasoning", ""),
    }


def _strip_code_fences(sql: str) -> str:
    """Remove markdown code fences from SQL if the LLM wrapped them."""
    # ```sql ... ```
    match = re.search(r'```(?:sql)?\s*([\s\S]*?)```', sql)
    if match:
        return match.group(1).strip()
    return sql
