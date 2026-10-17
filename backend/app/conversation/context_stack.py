"""
Conversational Analytics — Context Stack
==========================================
Detects follow-up queries and merges them with the previous query context.

Follow-up detection patterns:
    • Pronoun references: "filter that", "sort it", "show me those"
    • Modification requests: "now by region", "instead of city", "add a filter"
    • Continuation: "what about", "how about", "same but", "also show"
    • Drill-down: "break that down by", "zoom into", "details for"

When a follow-up is detected, the previous spec is used as a base
and the new query modifies it — rather than starting from scratch.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Follow-up detection patterns
_FOLLOWUP_PATTERNS = [
    # Pronoun references
    r"\b(that|those|this|these|it|them)\b",
    # Modification
    r"\b(now|instead|but|also|add|remove|change|switch|replace)\b",
    # Continuation
    r"\b(what about|how about|same but|same for|and also|also show)\b",
    # Drill-down
    r"\b(break.+down|drill.+into|zoom.+into|details? for|more detail)\b",
    # Sort/filter modifications
    r"\b(sort|order|filter|limit|top|bottom|ascending|descending)\s+(that|it|them|this|the)\b",
]

# Compiled patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _FOLLOWUP_PATTERNS]


def is_followup(query: str, has_previous: bool = True) -> bool:
    """
    Detect if a query is a follow-up to a previous query.

    Parameters
    ----------
    query : str
        The current user query.
    has_previous : bool
        Whether there is a previous turn in the conversation.

    Returns
    -------
    bool
        True if this looks like a follow-up.
    """
    if not has_previous:
        return False

    query_lower = query.lower().strip()

    # Very short queries are likely follow-ups
    if len(query_lower.split()) <= 3:
        return True

    # Check patterns
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(query_lower):
            return True

    return False


def merge_specs(
    previous_spec: dict,
    new_spec: dict,
    query: str,
) -> dict:
    """
    Merge a new (partial) spec into a previous spec for follow-up queries.

    Strategy:
        • New metric → replaces previous metric
        • New group_by → replaces previous group_by
        • New filters → added to (not replacing) previous filters
        • New sort → replaces previous sort
        • New limit → replaces previous limit
        • Table carries over from previous if not specified

    Parameters
    ----------
    previous_spec : dict
        The full spec from the previous turn.
    new_spec : dict
        The spec from the current (follow-up) turn. May be partial.
    query : str
        The raw query text for pattern detection.

    Returns
    -------
    dict
        Merged spec.
    """
    merged = dict(previous_spec)
    query_lower = query.lower()

    # ── Table: carry over ──
    if new_spec.get("primary_table"):
        merged["primary_table"] = new_spec["primary_table"]

    # ── Metric: replace if new one provided ──
    if new_spec.get("select_column"):
        merged["select_column"] = new_spec["select_column"]
        if new_spec.get("aggregation"):
            merged["aggregation"] = new_spec["aggregation"]

    # ── Group by: replace on "by X" or "instead of" ──
    if new_spec.get("group_by_column"):
        if _is_replacement(query_lower, "group"):
            merged["group_by_column"] = new_spec["group_by_column"]
            merged.pop("additional_group_by", None)
        else:
            merged["group_by_column"] = new_spec["group_by_column"]

    # ── Filters: additive by default, replace on "only" ──
    if new_spec.get("filters"):
        if _is_replacement(query_lower, "filter"):
            merged["filters"] = new_spec["filters"]
        else:
            existing = merged.get("filters", [])
            # Don't duplicate filters on the same column
            existing_cols = {f.get("column") for f in existing}
            for f in new_spec["filters"]:
                if f.get("column") not in existing_cols:
                    existing.append(f)
                else:
                    # Replace existing filter for same column
                    existing = [e for e in existing if e.get("column") != f.get("column")]
                    existing.append(f)
            merged["filters"] = existing

    if new_spec.get("numeric_filters"):
        existing_nf = merged.get("numeric_filters", [])
        existing_nf_cols = {f.get("column") for f in existing_nf}
        for f in new_spec["numeric_filters"]:
            if f.get("column") not in existing_nf_cols:
                existing_nf.append(f)
            else:
                existing_nf = [e for e in existing_nf if e.get("column") != f.get("column")]
                existing_nf.append(f)
        merged["numeric_filters"] = existing_nf

    # ── Sort: replace ──
    if new_spec.get("order_by"):
        merged["order_by"] = new_spec["order_by"]
    if new_spec.get("order_direction"):
        merged["order_direction"] = new_spec["order_direction"]

    # Handle "sort descending" / "sort ascending" without explicit column
    if re.search(r"\b(descending|desc)\b", query_lower) and not new_spec.get("order_by"):
        merged["order_direction"] = "DESC"
    if re.search(r"\b(ascending|asc)\b", query_lower) and not new_spec.get("order_by"):
        merged["order_direction"] = "ASC"

    # ── Limit: replace ──
    if new_spec.get("limit") is not None:
        merged["limit"] = new_spec["limit"]

    # Handle "top N" / "bottom N" in follow-up
    top_match = re.search(r"\btop\s+(\d+)\b", query_lower)
    if top_match:
        merged["limit"] = int(top_match.group(1))
        merged["order_direction"] = "DESC"

    bottom_match = re.search(r"\bbottom\s+(\d+)\b", query_lower)
    if bottom_match:
        merged["limit"] = int(bottom_match.group(1))
        merged["order_direction"] = "ASC"

    # ── Time filter: replace ──
    if new_spec.get("time_filter"):
        merged["time_filter"] = new_spec["time_filter"]
    if new_spec.get("period"):
        merged["period"] = new_spec["period"]

    # Mark as merged follow-up
    merged["_is_followup"] = True
    merged["_previous_query"] = previous_spec.get("_raw_query", "")

    return merged


def _is_replacement(query_lower: str, context: str) -> bool:
    """Check if the query implies replacement vs. addition."""
    replacement_patterns = [
        r"\binstead\b", r"\brather\b", r"\breplace\b",
        r"\bonly\b", r"\bjust\b", r"\bswitch\b",
    ]
    for pattern in replacement_patterns:
        if re.search(pattern, query_lower):
            return True
    return False
