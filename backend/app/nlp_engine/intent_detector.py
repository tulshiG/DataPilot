# # Intent categories and the keyword patterns that signal them
# INTENT_PATTERNS = {
#     "aggregate": [
#         "total", "sum", "average", "avg", "mean", "count", "how many", "how much",
#         "amount of", "number of", "total of", "gross", "qty",
#         "what is the", "what are the",   # "What is the average order value?"
#     ],
#     "top_n": ["top", "highest", "best", "most", "largest", "maximum", "max"],
#     "bottom_n": ["bottom", "lowest", "worst", "least", "smallest", "minimum", "min"],
#     "trend": [
#         "trend", "over time", "growth", "change", "monthly", "yearly",
#         "daily", "weekly", "quarterly", "annual", "by month", "by year", "by day",
#     ],
#     "filter": ["where", "with", "having", "greater than", "less than", "equal to", "between", "below", "above"],
#     "list": ["list", "all", "show me", "display", "fetch", "get", "show"],
#     "distribution": ["distribution", "breakdown", "split", "proportion", "by category", "by segment"],
#     "compare": ["compare", "comparison", "versus", "vs", " and ", "between"],
# }

# # Special meta-intent triggers — checked FIRST before NLP pipeline
# SPECIAL_INTENT_PATTERNS = {
#     "generate_dashboard": [
#         "generate sales dashboard", "sales dashboard", "generate dashboard",
#         "create dashboard", "build dashboard", "show dashboard",
#     ],
#     "generate_insights": [
#         "generate business insights", "business insights", "generate insights",
#         "business summary", "executive summary", "generate summary",
#     ],
#     "never_sold": [
#         "never sold", "not sold", "products never sold", "items never sold",
#         "unsold products", "zero sales", "no sales",
#     ],
# }


# def detect_special_intent(cleaned_text: str) -> dict | None:
#     """
#     Check for high-level meta-queries that bypass the SQL pipeline entirely.
#     Returns a special intent dict if matched, else None.
#     """
#     for intent_key, patterns in SPECIAL_INTENT_PATTERNS.items():
#         for pattern in patterns:
#             if pattern in cleaned_text:
#                 return {
#                     "intent": intent_key,
#                     "subquery_type": None,
#                     "having_modifier": None,
#                     "confidence": "high",
#                     "limit": None,
#                     "matched_signals": {intent_key: 1},
#                     "is_special": True,
#                 }
#     return None


# def detect_intent(cleaned_text: str, tokens: list[str]) -> dict:
#     """
#     Detect the primary intent of a query using keyword matching.

#     Intent priority (when multiple match):
#       aggregate > top_n/bottom_n > trend/distribution > compare > filter > list

#     Special meta-intents (dashboard, insights, never-sold) are checked first.
#     """
#     # Check special intents first
#     special = detect_special_intent(cleaned_text)
#     if special:
#         return special

#     scores: dict[str, int] = {}

#     for intent, patterns in INTENT_PATTERNS.items():
#         matches = [p for p in patterns if p in cleaned_text]
#         if matches:
#             scores[intent] = len(matches)

#     if not scores:
#         primary_intent = "list"
#     else:
#         # Priority ordering for tie-breaking
#         PRIORITY = ["aggregate", "top_n", "bottom_n", "trend", "distribution", "compare", "filter", "list"]
#         # Pick the highest score; break ties by priority
#         max_score = max(scores.values())
#         candidates = [i for i, s in scores.items() if s == max_score]
#         primary_intent = min(candidates, key=lambda i: PRIORITY.index(i) if i in PRIORITY else 99)

#     # N extraction for top_n / bottom_n
#     limit = None
#     if primary_intent in ("top_n", "bottom_n"):
#         for token in tokens:
#             if token.isdigit():
#                 limit = int(token)
#                 break
#         if limit is None:
#             if "top" in cleaned_text or "bottom" in cleaned_text:
#                 limit = 5  # Standard dashboard default
#             else:
#                 limit = 1  # "highest", "most", "best" usually implies a single top record

#     # Subquery detection
#     subquery_type = None
#     if any(p in cleaned_text for p in ["above average", "higher than average", "greater than average",
#                                         "more than average", "above the average"]):
#         subquery_type = "above_avg"
#     elif any(p in cleaned_text for p in ["below average", "lower than average", "less than average",
#                                           "below the average"]):
#         subquery_type = "below_avg"

#     # Detect numeric threshold filter (e.g. "below 20", "above 100", "less than 50")
#     numeric_threshold = None
#     import re
#     threshold_match = re.search(
#         r"\b(?:below|under|less than|greater than|above|over|more than|equal to|=|>|<)\s+(\d+(?:\.\d+)?)",
#         cleaned_text
#     )
#     if threshold_match:
#         numeric_threshold = float(threshold_match.group(1))
#         # Determine operator
#         op_text = threshold_match.group(0).lower()
#         if any(w in op_text for w in ["below", "under", "less than", "<"]):
#             numeric_op = "lt"
#         elif any(w in op_text for w in ["above", "over", "greater than", "more than", ">"]):
#             numeric_op = "gt"
#         else:
#             numeric_op = "eq"
#     else:
#         numeric_threshold = None
#         numeric_op = None

#     having_modifier = None
#     if "having" in cleaned_text or "with total" in cleaned_text:
#         having_modifier = True

#     # Upgrade "list/filter" to "aggregate" when aggregation signals are strong
#     if primary_intent in ("list", "filter", "distribution") and any(
#         w in cleaned_text for w in ["average", "avg", "total", "sum", "count", "how many"]
#     ):
#         primary_intent = "aggregate"
#         scores["aggregate"] = scores.get("aggregate", 0) + 1

#     # Detect "by X" GROUP BY intent signals — upgrade to aggregate when grouping words are present
#     group_keywords = ["by city", "by category", "by product", "by customer", "by region",
#                       "by segment", "by month", "by year", "per city", "per category"]
#     if any(kw in cleaned_text for kw in group_keywords) and primary_intent == "list":
#         primary_intent = "aggregate"
#         scores["aggregate"] = scores.get("aggregate", 0) + 1

#     # Detect comparison intent more precisely
#     if primary_intent == "compare" and not scores.get("aggregate"):
#         primary_intent = "aggregate"
#         scores["aggregate"] = 1

#     return {
#         "intent": primary_intent,
#         "subquery_type": subquery_type,
#         "having_modifier": having_modifier,
#         "confidence": "high" if scores.get(primary_intent, 0) > 1 else "medium" if scores else "low",
#         "limit": limit,
#         "matched_signals": scores,
#         "numeric_threshold": numeric_threshold,
#         "numeric_op": numeric_op,
#         "is_special": False,
#     }
"""
Slot-filling intent detector.

WHY THIS CHANGED FROM THE ORIGINAL:
The original detect_intent() picked exactly ONE "primary_intent" out of 8
buckets and threw away every other signal in the query. That's fine for
"Show top 10 customers" but silently breaks compound queries like
"Show completed orders from Ahmedabad with stock below 20" — the moment
"below" fires the filter pattern, information about "top" or "average"
in the SAME query is lost because only one bucket can win.

This version detects every signal independently as a boolean/list "slot"
and lets query_mapper.py compose them together. `intent` (singular) is
kept for backward compatibility with any caller that still expects it —
it's now just "the slot the caller should treat as primary for backward
compat," not the only thing that was detected.
"""
import re

# INTENT_PATTERNS = {
#     "aggregate": [
#         "total", "sum", "average", "avg", "mean", "count", "how many", "how much",
#         "amount of", "number of", "total of", "gross", "qty",
#         "what is the", "what are the",
#     ],
#     "top_n": ["top", "highest", "best", "most", "largest", "maximum", "max"],
#     "bottom_n": ["bottom", "lowest", "worst", "least", "smallest", "minimum", "min"],
#     "trend": [
#         "trend", "over time", "growth", "change", "monthly", "yearly",
#         "daily", "weekly", "quarterly", "annual", "by month", "by year", "by day",
#     ],
#     "filter": ["where", "with", "having", "greater than", "less than", "equal to", "between", "below", "above"],
#     "list": ["list", "all", "show me", "display", "fetch", "get", "show"],
#     "distribution": ["distribution", "breakdown", "split", "proportion", "by category", "by segment"],
#     # NOTE: removed bare " and " — it fired on nearly every compound query
#     # (e.g. "orders above 1000 and stock below 20") and stole the slot from
#     # the real intent. Compare now requires an explicit comparison cue.
#     "compare": ["compare", "comparison", "versus", " vs ", "vs.", "difference between"],
# }
INTENT_PATTERNS = {
    "aggregate": ["total", "sum", "average", "avg", "mean", "count", "how many", "how much", "amount of", "number of", "total of", "gross", "qty"],
    "top_n": ["top", "highest", "best", "most", "largest", "maximum", "max"],
    "bottom_n": ["bottom", "lowest", "worst", "least", "smallest", "minimum", "min"],
    "filter": ["where", "with", "having", "greater than", "less than", "equal to", "between", "from", "in", "for"], 
    "trend": ["trend", "over time", "growth", "change", "monthly", "yearly", "daily"],
    "distribution": ["distribution", "breakdown", "split", "proportion", "by category", "by segment"],
    "compare": ["compare", "comparison", "versus", "vs", "difference between"],
    "list": ["list", "all", "show me", "display", "fetch", "get"],
}

# Module 9: full aggregation function vocabulary, not just sum/avg/count/min/max
AGGREGATION_FUNCTIONS = {
    "total number": "COUNT",
    "total": "SUM", "sum": "SUM", "gross": "SUM",
    "average": "AVG", "avg": "AVG", "mean": "AVG",
    "highest": "MAX", "max": "MAX", "maximum": "MAX",
    "lowest": "MIN", "min": "MIN", "minimum": "MIN",
    "number": "COUNT", "how many": "COUNT", "count": "COUNT",
    "distinct": "COUNT_DISTINCT", "unique": "COUNT_DISTINCT",
    "median": "MEDIAN",
    "variance": "VARIANCE",
    "std deviation": "STDDEV", "standard deviation": "STDDEV", "stddev": "STDDEV",
}
_IMPLICIT_EQ_RE = re.compile(r"\b(age|stock|quantity|qty|price|revenue|amount|sales|inventory|count|bmi|children)\s+(\d+(?:\.\d+)?)\b", re.I)

def detect_aggregation_function(cleaned_text: str) -> str | None:
    """Module 9 — map the query's wording directly to a SQL aggregation function."""
    if not cleaned_text:
        return None
    
    # Check multi-word phrases first so 'std deviation' wins over a stray 'deviation'
    for phrase in sorted(AGGREGATION_FUNCTIONS.keys(), key=len, reverse=True):
        if phrase in cleaned_text:
            res = AGGREGATION_FUNCTIONS[phrase]
            return res.upper() if res else None
    return None

def detect_intent(cleaned_text: str, tokens: list[str]) -> dict:
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        matches = [p for p in patterns if p in cleaned_text]
        if matches:
            scores[intent] = len(matches)

    primary_intent = max(scores, key=scores.get) if scores else "list"

    limit = None
    if primary_intent in ("top_n", "bottom_n"):
        for token in tokens:
            if token.isdigit():
                limit = int(token)
                break
        if limit is None:
            limit = 5

    subquery_type = None
    if any(p in cleaned_text for p in ["above average", "higher than average", "greater than average", "more than average"]):
        subquery_type = "above_avg"
    elif any(p in cleaned_text for p in ["below average", "lower than average", "less than average"]):
        subquery_type = "below_avg"

    having_modifier = "having" in cleaned_text or "with total" in cleaned_text

    # Module 5: MULTI-LABEL output — every dimension classified simultaneously,
    # not collapsed into a single "primary_intent" string. Downstream code can
    # still use `intent` for backwards compatibility, but `labels` is the real
    # multi-dimensional classification your spec asks for.
    labels = {
        "ranking": "TOP" if primary_intent == "top_n" else "BOTTOM" if primary_intent == "bottom_n" else None,
        "aggregation_function": detect_aggregation_function(cleaned_text),
        "is_trend": primary_intent == "trend",
        "has_filter_language": primary_intent == "filter" or "filter" in scores,
        "has_subquery": subquery_type is not None,
        "limit": limit,
    }

    return {
        "intent": primary_intent,
        "labels": labels,
        "subquery_type": subquery_type,
        "having_modifier": having_modifier,
        "confidence": "high" if scores.get(primary_intent, 0) > 1 else "medium" if scores else "low",
        "limit": limit,
        "matched_signals": scores,
    }

SPECIAL_INTENT_PATTERNS = {
    "generate_dashboard": [
        "generate sales dashboard", "sales dashboard", "generate dashboard",
        "create dashboard", "build dashboard", "show dashboard",
    ],
    "generate_insights": [
        "generate business insights", "business insights", "generate insights",
        "business summary", "executive summary", "generate summary",
    ],
    "never_sold": [
        "never sold", "not sold", "products never sold", "items never sold",
        "unsold products", "zero sales", "no sales",
    ],
}

# Operator lexicon shared by threshold extraction below.
_OP_WORDS = {
    "below": "lt", "under": "lt", "less than": "lt", "<": "lt",
    "above": "gt", "over": "gt", "greater than": "gt", "more than": "gt", ">": "gt",
    "equal to": "eq", "=": "eq",
}
# Longest phrases first so "less than" matches before a stray "less".
_OP_PATTERN = "|".join(sorted((re.escape(k) for k in _OP_WORDS), key=len, reverse=True))
_THRESHOLD_RE = re.compile(
    rf"\b(?:{_OP_PATTERN})\s+(\d+(?:\.\d+)?)"
)
_BETWEEN_RE = re.compile(
    r"\bbetween\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)"
)


def detect_special_intent(cleaned_text: str) -> dict | None:
    for intent_key, patterns in SPECIAL_INTENT_PATTERNS.items():
        for pattern in patterns:
            if pattern in cleaned_text:
                return {
                    "intent": intent_key,
                    "subquery_type": None,
                    "having_modifier": None,
                    "confidence": "high",
                    "limit": None,
                    "matched_signals": {intent_key: 1},
                    "numeric_threshold": None,
                    "numeric_op": None,
                    "is_special": True,
                    # Full slot set with zero/false defaults so callers
                    # don't get KeyError when reading any slot field.
                    "slots": {
                        "is_aggregate": False,
                        "is_top_n": False,
                        "is_bottom_n": False,
                        "is_trend": False,
                        "is_distribution": False,
                        "is_compare": False,
                        "has_filter": False,
                        "implies_group_by": False,
                        "thresholds": [],
                        "compare_targets": [],
                        "limit": None,
                    },
                }
    return None


def _extract_all_thresholds(cleaned_text: str) -> list[dict]:
    """
    Return EVERY numeric threshold/range in the query, not just the first.
    Handles both single comparisons ("stock below 20", "price above 1000")
    and ranges ("between 500 and 2000"). Multiple of either kind in one
    query are all captured, in order of appearance.
    """
    # results: list[dict] = []

    # for m in _BETWEEN_RE.finditer(cleaned_text):
    #     results.append({
    #         "op": "between",
    #         "low": float(m.group(1)),
    #         "high": float(m.group(2)),
    #         "span": m.span(),
    #     })

    # for m in _THRESHOLD_RE.finditer(cleaned_text):
    #     # Skip if this match falls inside an already-captured "between X and Y"
    #     if any(r["span"][0] <= m.start() < r["span"][1] for r in results if r["op"] == "between"):
    #         continue
    #     matched_phrase = m.group(0).lower()
    #     op = None
    #     for phrase, code in sorted(_OP_WORDS.items(), key=lambda kv: -len(kv[0])):
    #         if matched_phrase.startswith(phrase):
    #             op = code
    #             break
    #     results.append({"op": op or "eq", "value": float(m.group(1)), "span": m.span()})

    # results.sort(key=lambda r: r["span"][0])
    # for r in results:
    #     r.pop("span", None)
    # return results
    results: list[dict] = []

    for m in _BETWEEN_RE.finditer(cleaned_text):
        results.append({
            "op": "between", "low": float(m.group(1)), "high": float(m.group(2)), "span": m.span(),
        })

    for m in _THRESHOLD_RE.finditer(cleaned_text):
        if any(r["span"][0] <= m.start() < r["span"][1] for r in results if r["op"] == "between"):
            continue
        matched_phrase = m.group(0).lower()
        op = None
        for phrase, code in sorted(_OP_WORDS.items(), key=lambda kv: -len(kv[0])):
            if matched_phrase.startswith(phrase):
                op = code
                break
        results.append({"op": op or "eq", "value": float(m.group(1)), "span": m.span()})

    # NEW: Catch implicit equalities like "age 30"
    for m in _IMPLICIT_EQ_RE.finditer(cleaned_text):
        if any(r["span"][0] <= m.start() < r["span"][1] for r in results):
            continue
        results.append({"op": "eq", "value": float(m.group(2)), "span": m.span()})

    results.sort(key=lambda r: r["span"][0])
    for r in results:
        r.pop("span", None)
    return results


def _extract_compare_targets(cleaned_text: str, tokens: list[str]) -> list[str]:
    """
    For explicit compare queries ('compare Ahmedabad and Surat revenue'),
    pull out the two-plus things being compared so query_mapper can build
    a multi-branch (CASE WHEN / UNION) comparison instead of one number.
    Looks for capitalized-in-original-text tokens joined by 'and'/'vs' near
    a compare cue. This intentionally stays conservative — better to return
    nothing than a wrong guess, since query_mapper falls back to normal
    single-value handling when compare_targets is empty.
    """
    if not any(c in cleaned_text for c in ["compare", " vs ", "vs.", "versus"]):
        return []

    # Pull the word right before "and"/"vs" and the word right after — these
    # are almost always the two entities being compared, regardless of how
    # much metric/aggregation wording surrounds them ("compare monthly
    # revenue of Ahmedabad and Surat" -> ahmedabad, surat).
    m = re.search(r"([a-z]+)\s+and\s+([a-z]+)", cleaned_text)
    if not m:
        m = re.search(r"([a-z]+)\s+vs\.?\s+([a-z]+)", cleaned_text)
    if not m:
        return []

    stop = {"revenue", "sales", "orders", "products", "customers",
            "total", "monthly", "yearly", "quantity", "amount"}
    a, b = m.group(1).strip(), m.group(2).strip()
    if a in stop or b in stop or len(a) < 3 or len(b) < 3:
        return []
    return [a, b]


def detect_intent(cleaned_text: str, tokens: list[str]) -> dict:
    special = detect_special_intent(cleaned_text)
    if special:
        return special

    scores: dict[str, int] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        matches = [p for p in patterns if p in cleaned_text]
        if matches:
            scores[intent] = len(matches)

    # ---- slot detection (independent booleans/values, not mutually exclusive) ----
    thresholds = _extract_all_thresholds(cleaned_text)
    compare_targets = _extract_compare_targets(cleaned_text, tokens)

    is_aggregate = "aggregate" in scores or any(
        w in cleaned_text for w in ["average", "avg", "total", "sum", "count", "how many"]
    )
    is_top_n = "top_n" in scores
    is_bottom_n = "bottom_n" in scores
    is_trend = "trend" in scores
    is_distribution = "distribution" in scores
    is_compare = bool(compare_targets) or "compare" in scores
    has_filter = bool(thresholds) or "filter" in scores

    group_keywords = ["by city", "by category", "by product", "by customer", "by region",
                       "by segment", "by month", "by year", "per city", "per category"]
    implies_group_by = any(kw in cleaned_text for kw in group_keywords)
    if implies_group_by:
        is_aggregate = True

    subquery_type = None
    if any(p in cleaned_text for p in ["above average", "higher than average", "greater than average",
                                        "more than average", "above the average"]):
        subquery_type = "above_avg"
    elif any(p in cleaned_text for p in ["below average", "lower than average", "less than average",
                                          "below the average"]):
        subquery_type = "below_avg"

    having_modifier = "having" in cleaned_text or "with total" in cleaned_text

    # ---- backward-compatible single "primary_intent" for old callers ----
    PRIORITY = ["aggregate", "top_n", "bottom_n", "trend", "distribution", "compare", "filter", "list"]
    if is_aggregate:
        primary_intent = "aggregate"
    elif is_top_n:
        primary_intent = "top_n"
    elif is_bottom_n:
        primary_intent = "bottom_n"
    elif is_trend:
        primary_intent = "trend"
    elif is_distribution:
        primary_intent = "distribution"
    elif is_compare:
        primary_intent = "compare"
    elif has_filter:
        primary_intent = "filter"
    else:
        primary_intent = "list"

    limit = None
    if is_top_n or is_bottom_n:
        for token in tokens:
            if token.isdigit():
                limit = int(token)
                break
        if limit is None:
            limit = 5 if ("top" in cleaned_text or "bottom" in cleaned_text) else 1

    # Legacy single-threshold fields (first threshold found), kept so any
    # existing caller reading numeric_threshold/numeric_op doesn't break.
    legacy_threshold, legacy_op = None, None
    for t in thresholds:
        if t["op"] != "between":
            legacy_threshold, legacy_op = t["value"], t["op"]
            break

    return {
        "intent": primary_intent,
        "subquery_type": subquery_type,
        "having_modifier": having_modifier or None,
        "confidence": "high" if scores.get(primary_intent, 0) > 1 or thresholds else ("medium" if scores else "low"),
        "limit": limit,
        "matched_signals": scores,
        "numeric_threshold": legacy_threshold,
        "numeric_op": legacy_op,
        "is_special": False,
        # ---- new: full slot set for compound-query handling ----
        "slots": {
            "is_aggregate": is_aggregate,
            "is_top_n": is_top_n,
            "is_bottom_n": is_bottom_n,
            "is_trend": is_trend,
            "is_distribution": is_distribution,
            "is_compare": is_compare,
            "has_filter": has_filter,
            "implies_group_by": implies_group_by,
            "thresholds": thresholds,          # ALL thresholds/ranges, in order
            "compare_targets": compare_targets,  # e.g. ["ahmedabad", "surat"]
            "limit": limit,
            
        },
    }