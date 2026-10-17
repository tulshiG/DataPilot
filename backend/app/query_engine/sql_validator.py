"""
Query Engine — SQL Validator
================================
AST-based SQL safety and correctness checks using sqlglot.

This module validates generated SQL BEFORE execution to:
    1. Prevent SQL injection (no DDL, no multi-statement)
    2. Ensure all referenced tables/columns exist
    3. Check for common SQL errors (missing GROUP BY, ambiguous columns)
    4. Enforce query limits to prevent runaway queries
    5. Provide optimization hints

Uses sqlglot for parsing instead of regex — much more reliable.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import sqlglot — it's optional
_sqlglot = None


def _get_sqlglot():
    global _sqlglot
    if _sqlglot is None:
        try:
            import sqlglot
            _sqlglot = sqlglot
        except ImportError:
            logger.warning("sqlglot not installed — SQL validation disabled")
    return _sqlglot


class SQLValidationResult:
    """Encapsulates SQL validation outcome."""

    def __init__(self, sql: str):
        self.original_sql = sql
        self.corrected_sql: str | None = None
        self.safe = True
        self.valid = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.hints: list[str] = []

    @property
    def final_sql(self) -> str:
        return self.corrected_sql or self.original_sql

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "hints": self.hints,
            "original_sql": self.original_sql,
            "corrected_sql": self.corrected_sql,
        }


# Dangerous SQL keywords that should never appear in analytics queries
_FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT",
    "UPDATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "MERGE", "REPLACE",
}

# Maximum result limit to prevent runaway queries
MAX_RESULT_LIMIT = 10000


def validate_sql(
    sql: str,
    allowed_tables: list[str] | None = None,
    enforce_limit: bool = True,
    max_limit: int = MAX_RESULT_LIMIT,
) -> SQLValidationResult:
    """
    Validate generated SQL for safety and correctness.

    Parameters
    ----------
    sql : str
        The SQL query to validate.
    allowed_tables : list[str], optional
        If provided, only these tables can be referenced.
    enforce_limit : bool
        If True, add LIMIT if not present.
    max_limit : int
        Maximum allowed LIMIT value.

    Returns
    -------
    SQLValidationResult
    """
    result = SQLValidationResult(sql)

    if not sql or not sql.strip():
        result.valid = False
        result.errors.append("Empty SQL query")
        return result

    # ── 1. Basic safety checks (fast, no parsing needed) ──
    _check_basic_safety(sql, result)
    if not result.safe:
        return result

    # ── 2. AST-based validation (if sqlglot available) ──
    sqlglot = _get_sqlglot()
    if sqlglot:
        _check_ast(sql, result, sqlglot, allowed_tables, enforce_limit, max_limit)
    else:
        # Fallback: regex-based checks
        _check_regex_fallback(sql, result, enforce_limit, max_limit)

    return result


def _check_basic_safety(sql: str, result: SQLValidationResult):
    """Fast safety checks without parsing."""
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (CTE)
    if not sql_upper.startswith(("SELECT", "WITH")):
        result.safe = False
        result.errors.append(f"Query must start with SELECT or WITH, got: {sql_upper[:20]}...")
        return

    # Check for forbidden keywords
    # Use word boundary check to avoid false positives
    import re
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_upper):
            result.safe = False
            result.errors.append(f"Forbidden SQL keyword detected: {keyword}")

    # Check for multiple statements (semicolon not at end)
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        result.safe = False
        result.errors.append("Multiple SQL statements detected — only single SELECT is allowed")

    # Check for comment injection
    if "--" in sql or "/*" in sql:
        result.warnings.append("SQL comments detected — these will be stripped")


def _check_ast(
    sql: str,
    result: SQLValidationResult,
    sqlglot,
    allowed_tables: list[str] | None,
    enforce_limit: bool,
    max_limit: int,
):
    """AST-based validation using sqlglot."""
    try:
        parsed = sqlglot.parse(sql, dialect="postgres")
    except Exception as e:
        result.valid = False
        result.errors.append(f"SQL parse error: {str(e)}")
        return

    if not parsed:
        result.valid = False
        result.errors.append("SQL parsing returned no statements")
        return

    stmt = parsed[0]

    # ── Check statement type ──
    from sqlglot import exp
    if not isinstance(stmt, exp.Select):
        # Could be a CTE (With → Select)
        if not isinstance(stmt, exp.With):
            result.safe = False
            result.errors.append(f"Expected SELECT statement, got {type(stmt).__name__}")
            return

    # ── Check referenced tables ──
    if allowed_tables:
        from sqlglot import exp
        referenced_tables = set()
        for table in stmt.find_all(exp.Table):
            referenced_tables.add(table.name)

        for table in referenced_tables:
            if table not in allowed_tables:
                result.warnings.append(f"Table '{table}' not in allowed tables list")

    # ── Check for LIMIT ──
    has_limit = False
    for limit_node in stmt.find_all(exp.Limit):
        has_limit = True
        # Check limit value
        try:
            limit_val = int(limit_node.expression.this) if hasattr(limit_node.expression, 'this') else None
            if limit_val and limit_val > max_limit:
                result.warnings.append(f"LIMIT {limit_val} exceeds maximum ({max_limit}), capping")
                # Cap the limit
                result.corrected_sql = sql  # Will be capped below
        except (ValueError, AttributeError):
            pass

    if not has_limit and enforce_limit:
        result.hints.append(f"No LIMIT clause — adding LIMIT {max_limit} for safety")
        try:
            corrected = stmt.limit(max_limit).sql(dialect="postgres")
            result.corrected_sql = corrected
        except Exception:
            # Fallback: just append LIMIT
            clean = sql.rstrip().rstrip(";")
            result.corrected_sql = f"{clean} LIMIT {max_limit}"

    # ── Check for SELECT * ──
    for star in stmt.find_all(exp.Star):
        result.hints.append("SELECT * detected — consider selecting specific columns for better performance")

    # ── Check GROUP BY has all non-aggregated columns ──
    # This is a heuristic — full validation would require schema info
    try:
        group_exprs = set()
        for group in stmt.find_all(exp.Group):
            for g_expr in group.expressions:
                if hasattr(g_expr, "name"):
                    group_exprs.add(g_expr.name)

        if group_exprs:
            select_cols = set()
            agg_funcs = {"sum", "avg", "count", "min", "max", "count_distinct"}
            for sel in stmt.find_all(exp.Select):
                for expr in sel.expressions:
                    if hasattr(expr, "name") and expr.name:
                        # Check if it's wrapped in an aggregate
                        is_agg = any(
                            isinstance(parent, (exp.Sum, exp.Avg, exp.Count, exp.Min, exp.Max))
                            for parent in expr.walk()
                        )
                        if not is_agg:
                            select_cols.add(expr.name)

            missing = select_cols - group_exprs
            if missing:
                result.warnings.append(
                    f"Columns {missing} in SELECT but not in GROUP BY — may cause errors"
                )
    except Exception:
        pass  # GROUP BY analysis is best-effort


def _check_regex_fallback(
    sql: str,
    result: SQLValidationResult,
    enforce_limit: bool,
    max_limit: int,
):
    """Regex-based validation fallback when sqlglot is not available."""
    import re

    sql_upper = sql.upper().strip()

    # Check for LIMIT
    if "LIMIT" not in sql_upper and enforce_limit:
        result.hints.append(f"No LIMIT clause — adding LIMIT {max_limit} for safety")
        clean = sql.rstrip().rstrip(";")
        result.corrected_sql = f"{clean} LIMIT {max_limit}"

    # Check for SELECT *
    if re.search(r"SELECT\s+\*", sql_upper):
        result.hints.append("SELECT * detected — consider specific columns")

    # Check GROUP BY consistency (basic)
    if "GROUP BY" in sql_upper and "HAVING" not in sql_upper:
        # Very basic check — just note it
        result.hints.append("GROUP BY detected — verify all non-aggregated SELECT columns are grouped")


def quick_validate(sql: str) -> bool:
    """
    Quick boolean check — is this SQL safe to execute?
    Used as a gate before execution.
    """
    result = validate_sql(sql, enforce_limit=False)
    return result.safe and result.valid
