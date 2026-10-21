

from app.nlp_engine.entity_extractor import MAX_DATASET_SCORE  # noqa: F401 (kept for compatibility)

def compute_plan_confidence(query_plan: dict, intent_result: dict) -> dict:
    """
    Combine per-stage confidence signals into one overall score, following
    Module 14: Dataset, Column/Metric, Intent, and Join each contribute,
    weighted by how much they matter to getting the right answer.
    """
    # NOTE: dataset_confidence is ALREADY on a 0-100 scale by the time it
    # gets here — query_planner.py sets it from either
    # dataset_scores[i]["confidence"] (entity_extractor's own 0-100
    # normalization) or dataset_ranking[i]["score"] (dataset_resolver.py's
    # weighted-average fuzzy score, also 0-100). Re-dividing it by
    # MAX_DATASET_SCORE (~24, a completely different raw integer scale)
    # whenever it happened to be <= 24 was silently INFLATING weak/borderline
    # dataset matches instead of leaving them weak — the opposite of what
    # this function should do.
    dataset_conf = query_plan.get("dataset_confidence") or 0.0
 
    intent_conf_map = {"high": 95.0, "medium": 75.0, "low": 45.0}
    intent_conf = intent_conf_map.get(intent_result.get("confidence"), 45.0)

    # A resolved metric/aggregation or an explicit COUNT(*) both count as a confident metric match.
    # Row-level filter/list queries ("bmi > 30", "list all electronic products") legitimately have
    # NO metric or aggregation by design — that's not a failed resolution, it's the correct shape
    # for that intent. Only treat "no metric" as weak when the intent actually implies one should
    # exist (aggregate/top_n/bottom_n/trend/distribution/compare) — otherwise a well-formed
    # filter-only plan was getting scored as if it were an ambiguous "show me stuff" query, pushing
    # otherwise-correct plans out of the >=65 execute band.
    slots = intent_result.get("slots", {})
    metric_expected = (
        slots.get("is_aggregate")
        or slots.get("is_top_n")
        or slots.get("is_bottom_n")
        or slots.get("is_trend")
        or slots.get("is_distribution")
        or slots.get("is_compare")
        or intent_result.get("intent") in ("aggregate", "top_n", "bottom_n", "trend", "distribution", "compare")
    )
    has_metric = bool(query_plan.get("metric")) or query_plan.get("aggregation") == "COUNT"
    if not metric_expected:
        metric_conf = 90.0  # filter/list query with no metric expected — nothing to ding
    else:
        metric_conf = 90.0 if has_metric else 55.0

    hops = query_plan.get("join_hops", 0)
    if hops == 0:
        join_conf = 95.0  # no join needed, nothing to get wrong
    else:
        join_conf = max(40.0, 95.0 - (hops * 15.0))  # each extra hop compounds risk of a wrong path

    overall = round(
        dataset_conf * 0.40 + intent_conf * 0.20 + metric_conf * 0.25 + join_conf * 0.15, 1
    )

    return {
        "dataset": round(dataset_conf, 1),
        "intent": intent_conf,
        "metric": metric_conf,
        "join": join_conf,
        "overall": overall,
    }


def decide_action(confidence: dict) -> str:
    """
    Recalibrated thresholds.

    WHY THIS CHANGED: the original >=90 "execute" bar was never actually
    reachable by compute_plan_confidence()'s own formula. dataset_conf is a
    weighted blend of 5 fuzzy-match signals (table/column/value/relationship/
    metric) that essentially never all max out together — even a clean,
    fully-resolved query (correct table, column, value, and metric all
    matched) tops out around 85-88 overall. That meant `action` was almost
    never "execute", generate_sql() was almost never called, and every query
    silently fell through to whatever generic fallback the caller uses when
    there's no SQL — the "I always just get SELECT * LIMIT 50" symptom.

    New thresholds are based on what this formula actually produces for a
    correctly-resolved query (~80-90) vs a genuinely weak/ambiguous one
    (~40-60) vs a near-total miss (<40). Tune further once you can see real
    confidence numbers flowing through (log query_plan["confidence"]).
    """
    overall = confidence["overall"]
    if overall >= 65:
        return "execute"
    if overall >= 40:
        return "try_alternate"
    return "escalate"
