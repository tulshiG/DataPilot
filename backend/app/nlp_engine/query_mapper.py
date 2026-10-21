import re
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, inspect as sa_inspect, text as sql_text
from app.models.relationship import DatasetRelationship
from app.models.dataset import Dataset
from app.core.config import settings
from app.nlp_engine.entity_extractor import apply_filter_evidence_to_scores, DATASET_CONFIDENCE_THRESHOLD
from app.relationship_engine.relationship_graph import find_join_path, resolve_join_path_to_spec_joins 
NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]
ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
 
 
# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
 
def _get_table_column_types(table_name: str) -> dict[str, bool]:
    """Return {column_name -> is_numeric} for the given table, based on the
    DECLARED database column type only. See _get_table_numeric_info() below
    for a version that also catches numeric-looking data stored in a
    TEXT/VARCHAR column (very common with CSV importers that don't do type
    inference, or that bail to text on the first messy row)."""
    engine = create_engine(settings.DATABASE_URL)
    result = {}
    try:
        inspector = sa_inspect(engine)
        for col in inspector.get_columns(table_name):
            type_str = str(col["type"]).upper()
            result[col["name"]] = any(t in type_str for t in NUMERIC_TYPE_HINTS)
    except Exception:
        pass
    finally:
        engine.dispose()
    return result
 
 
# Matches plain numbers optionally wrapped in currency/thousands formatting:
# "1234", "1234.5", "$1,234.50", "-42", "12%". Empty/whitespace-only doesn't match.
_NUMERIC_LIKE_RE = re.compile(r"^\s*-?[$€₹]?\s*[\d,]+(\.\d+)?\s*%?\s*$")
 
# Fraction of sampled non-null values that must look numeric before we trust
# a text-typed column as usable for SUM/AVG/comparison. Conservative on
# purpose: a false positive here means we'd try to CAST genuinely
# non-numeric text and the query fails loudly (safe); a false negative just
# means we miss a derivable metric (also safe, just less helpful).
_NUMERIC_SNIFF_THRESHOLD = 0.7
_NUMERIC_SNIFF_SAMPLE_SIZE = 25
 
 
def _sample_column_looks_numeric(table_name: str, col_name: str) -> bool:
    """Sample a handful of non-null values from a TEXT/VARCHAR column and
    check whether most of them look like numbers (possibly with $, commas,
    % formatting). Used to rescue columns like quantity/unit_price that a
    CSV import stored as text instead of a numeric type."""
    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql_text(
                    f'SELECT "{col_name}" FROM "{table_name}" '
                    f'WHERE "{col_name}" IS NOT NULL LIMIT {_NUMERIC_SNIFF_SAMPLE_SIZE}'
                )
            ).fetchall()
    except Exception:
        return False
    finally:
        engine.dispose()
 
    values = [str(r[0]) for r in rows if r[0] is not None and str(r[0]).strip() != ""]
    if len(values) < 3:  # not enough signal either way
        return False
    matches = sum(1 for v in values if _NUMERIC_LIKE_RE.match(v))
    return (matches / len(values)) >= _NUMERIC_SNIFF_THRESHOLD
 
 
def _get_table_numeric_info(table_name: str) -> dict[str, dict]:
    """
    Return {column_name -> {"is_numeric": bool, "soft": bool}} for a table.
 
    "is_numeric" is True if the column is usable in SUM/AVG/comparisons —
    either because the DB column type is genuinely numeric, OR because it's
    text-typed but sampling shows the data is consistently numeric-looking
    (e.g. unit_price stored as VARCHAR "19.99" or "$19.99").
 
    "soft" is True only in that second case — callers must wrap the column
    reference in a cleaning CAST (see _numeric_ref) rather than using it
    raw, since comparing/aggregating a text column directly will error or
    silently sort as text in most SQL engines.
    """
    engine = create_engine(settings.DATABASE_URL)
    declared: dict[str, str] = {}
    try:
        inspector = sa_inspect(engine)
        for col in inspector.get_columns(table_name):
            declared[col["name"]] = str(col["type"]).upper()
    except Exception:
        pass
    finally:
        engine.dispose()
 
    info: dict[str, dict] = {}
    id_like = ID_LIKE_HINTS
    for col_name, type_str in declared.items():
        is_declared_numeric = any(t in type_str for t in NUMERIC_TYPE_HINTS)
        if is_declared_numeric:
            info[col_name] = {"is_numeric": True, "soft": False}
            continue
        # Only bother sniffing text-like columns, and skip obvious ID/code
        # columns even if they happen to look numeric (order_id etc. should
        # never be summed/averaged).
        is_text_like = "CHAR" in type_str or "TEXT" in type_str
        if is_text_like and not any(h in col_name.lower() for h in id_like):
            if _sample_column_looks_numeric(table_name, col_name):
                info[col_name] = {"is_numeric": True, "soft": True}
                continue
        info[col_name] = {"is_numeric": False, "soft": False}
    return info
 
 
def _numeric_ref(table_name: str, col_name: str, numeric_info: dict[str, dict] | None = None) -> str:
    """
    Build a SQL expression that safely reads a numeric value out of
    "table"."col" — a plain qualified reference for genuinely numeric
    columns, or a cleaning CAST for text-typed columns that sniffed as
    numeric-like (strips $, commas, %, whitespace before casting).
    """
    numeric_info = numeric_info or {}
    is_soft = numeric_info.get(col_name, {}).get("soft", False)
    qualified = f'"{table_name}"."{col_name}"'
    if not is_soft:
        return qualified
    # Strip currency symbols / thousands separators / percent signs, then
    # cast. NULLIF guards against an all-symbols-no-digits value becoming ''
    # (which CAST ... AS NUMERIC would otherwise error on).
    cleaned = f"NULLIF(regexp_replace({qualified}::text, '[^0-9.\\-]', '', 'g'), '')"
    return f"CAST({cleaned} AS NUMERIC)"
 
 
def _get_table_columns_with_types(table_name: str) -> list[dict]:
    """Return all columns with name + type string for the given table."""
    engine = create_engine(settings.DATABASE_URL)
    result = []
    try:
        inspector = sa_inspect(engine)
        for col in inspector.get_columns(table_name):
            result.append({"name": col["name"], "type_str": str(col["type"]).upper()})
    except Exception:
        pass
    finally:
        engine.dispose()
    return result
 
 
def _find_best_numeric_column(num_cols: list[str], tokens: list[str], cleaned_text: str) -> str | None:
    """Score numeric columns against query tokens and return the best match."""
    import difflib
    best_col, best_score = None, 0
    for col_name in num_cols:
        if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
            continue
        col_words = col_name.lower().replace("_", " ").split()
        score = 0
        for w in col_words:
            for qt in tokens:
                fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
                if fuzz > 0.8:
                    score += 2 * fuzz
        # Boost revenue/amount/sales columns
        col_lower = col_name.lower()
        if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
            score += 2
        if score > best_score:
            best_score, best_col = score, col_name
    return best_col
 
 
def _find_column_by_hint(hint: str, table_name: str) -> str | None:
    """
    Find the best column in 'table_name' that matches 'hint'.
    Uses substring and fuzzy matching for better resolution.
    """
    cols = _get_table_columns_with_types(table_name)
    if not cols:
        return None
 
    # Exact match first
    for col in cols:
        if col["name"].lower() == hint:
            return col["name"]
 
    import difflib
    best_match = None
    best_score = 0
    # Prefix/suffix match & Fuzzy
    for col in cols:
        name = col["name"].lower().replace("_", " ")
        if hint in name or name.startswith(hint) or name.endswith(hint):
            return col["name"]
        
        # Fuzzy match simulating Levenshtein
        fuzz = difflib.SequenceMatcher(None, hint, name).ratio()
        for w in name.split():
            fuzz_w = difflib.SequenceMatcher(None, hint, w).ratio()
            if fuzz_w > fuzz:
                fuzz = fuzz_w
        if fuzz > 0.8 and fuzz > best_score:
            best_score = fuzz
            best_match = col["name"]
            
    if best_match:
        return best_match
 
    return None
 
 
def _find_column_by_role(role: str, table_name: str) -> str | None:
    """
    Find a column matching a semantic role like 'customer', 'product', 'category', 'city'.
    Uses the COLUMN_ROLE_HINTS from entity_extractor.
    """
    from app.nlp_engine.entity_extractor import COLUMN_ROLE_HINTS
    hints = COLUMN_ROLE_HINTS.get(role, [role])
    cols = _get_table_columns_with_types(table_name)
    if not cols:
        return None
 
    # Exact match first
    for hint in hints:
        for col in cols:
            if col["name"].lower() == hint:
                return col["name"]
 
    import difflib
    best_match = None
    best_score = 0
    # Partial match & Fuzzy
    for hint in hints:
        for col in cols:
            name = col["name"].lower().replace("_", " ")
            if hint in name:
                return col["name"]
            fuzz = difflib.SequenceMatcher(None, hint, name).ratio()
            for w in name.split():
                fuzz_w = difflib.SequenceMatcher(None, hint, w).ratio()
                if fuzz_w > fuzz:
                    fuzz = fuzz_w
            if fuzz > 0.85 and fuzz > best_score:
                best_score = fuzz
                best_match = col["name"]
                
    if best_match:
        return best_match
 
    return None
 
 
def _find_date_column(table_name: str) -> str | None:
    """Find the primary date/timestamp column in a table."""
    cols = _get_table_columns_with_types(table_name)
    date_priority = ["order_date", "date", "created_at", "updated_at", "timestamp", "sale_date",
                     "purchase_date", "transaction_date"]
 
    # Favor exact known date column names (regardless of strict type since SQLite might store as TEXT)
    for priority in date_priority:
        for col in cols:
            if col["name"].lower() == priority or col["name"].lower().replace(" ", "_") == priority:
                return col["name"]
 
    # Second fallback: any column that actually has a DATE type in the DB schema
    for col in cols:
        if any(t in col["type_str"] for t in DATE_TYPE_HINTS):
            return col["name"]
            
    # Final fallback: any column with "date" or "time" in it
    for col in cols:
        name_lower = col["name"].lower()
        if "date" in name_lower or "time" in name_lower:
            return col["name"]
 
    return None
 
 
def _find_all_table_columns(table_name: str) -> list[str]:
    """Return all column names for the given table."""
    return [c["name"] for c in _get_table_columns_with_types(table_name)]
 
 
# Known categorical attributes people commonly ask about that may or may not
# exist in a given dataset. Extend this map as new missing-column complaints
# come in (e.g. "age_group": ["teen", "senior", ...]).
UNRESOLVED_ATTRIBUTE_TERMS: dict[str, list[str]] = {
    "gender": ["male", "female", "men", "women", "man", "woman", "gender", "sex"],
}
 
 
def _query_references_missing_attribute(query_cleaned: str, table_name: str | None) -> str | None:
    """
    Return the attribute name (e.g. "gender") if the query mentions a term
    tied to that attribute (e.g. "male") but the table has no column that
    could plausibly represent it. Returns None if the attribute isn't
    referenced, or if a matching column does exist.
    """
    if not table_name:
        return None
    cols_lower = [c.lower() for c in _find_all_table_columns(table_name)]
    if not cols_lower:
        return None
    for attribute, terms in UNRESOLVED_ATTRIBUTE_TERMS.items():
        if any(term in query_cleaned for term in terms):
            has_matching_col = any(
                attribute in col or any(term in col for term in terms) for col in cols_lower
            )
            if not has_matching_col:
                return attribute
    return None
 
 
# ---------------------------------------------------------------------------
# Core query spec builder
# ---------------------------------------------------------------------------
 
def _resolve_compare_dimension_column(
    compare_targets: list[str],
    col_value_map: dict[tuple, list],
    primary_table: str | None,
    joined_tables: set[str],
) -> tuple[tuple[str, str], list] | None:
    """
    Pick the single filter column that is the actual comparison dimension in
    a 'compare X and Y <metric>' query (e.g. 'compare Ahmedabad and Surat
    revenue' -> city), using the intent detector's explicit compare_targets
    (['ahmedabad', 'surat']) as ground truth instead of just counting which
    filter columns happen to carry more than one value.

    WHY THIS EXISTS: the previous logic (further below) required EXACTLY ONE
    column in col_value_map to have multiple values before it would build a
    GROUP BY at all. In practice a single filter candidate like "Ahmedabad"
    can fuzzy-match value dictionaries on MORE than one column (e.g. city
    *and* state, if a state value loosely overlaps), so both "city" (2+
    values) and "state" (2 values) end up as multi-value columns. That made
    len(multi_value_cols) == 1 false, the whole comparison-detection branch
    got skipped, and the query fell all the way through to a bare
    unaggregated row dump with every one of those columns filtered — the
    "SELECT * ... WHERE city IN (...) AND state IN (...) LIMIT 500" bug.

    Instead, score each candidate column by how many of the EXPLICIT
    compare_targets it actually covers (i.e. its matched values really
    correspond to what the user typed), and pick the best-covering column.
    A spurious cross-match (e.g. state) will cover at most one target by
    coincidence, while the real dimension (city) covers all of them.
    """
    if not compare_targets:
        return None

    best_key, best_values, best_coverage = None, None, 0
    for (f_table, f_col), values in col_value_map.items():
        if f_table != primary_table and f_table not in joined_tables:
            continue
        covered = 0
        for target in compare_targets:
            t_lower = target.lower()
            if any(t_lower in str(v).lower() or str(v).lower() in t_lower for v in values):
                covered += 1
        # Prefer higher coverage; break ties toward the column that carries
        # more of the matched values overall (less likely to be a stray hit).
        if covered > best_coverage or (covered == best_coverage and covered and len(values) > len(best_values or [])):
            best_coverage = covered
            best_key = (f_table, f_col)
            best_values = values

    # Require this column to explain at least 2 of the compare targets (or
    # all of them, for the rare single-target case) before trusting it as
    # THE comparison dimension — otherwise fall back to the generic path.
    if best_key and best_coverage >= min(2, len(compare_targets)):
        return best_key, best_values
    return None


def map_to_query_spec(
    db: Session,
    workspace_id: int,
    intent_result: dict,
    extraction_result: dict,
    filters: list[dict] | None = None,
    dataset_ranking: list = None,
    business_intent:list=None,
    
) -> dict:
    """
    Build a structured query specification from NLP artefacts.
 
    Capabilities:
    - Resolves primary table from metrics, entities, or fallback datasets.
    - Handles GROUP BY column hints ('by cities' → GROUP BY city).
    - Handles date-based grouping ('monthly' → DATE_TRUNC('month', date_col)).
    - Supports multi-table filters via DatasetRelationship joins.
    - Multiple filters on the same column become an IN clause.
    - Handles 'never sold' LEFT JOIN + IS NULL pattern.
    - Handles numeric threshold filters (stock < 20).
    - Handles 'top N customers by revenue' with GROUP BY + ORDER BY.
    """
    spec = {
        "primary_table": None,
        "select_column": None,
        "aggregation": None,
        "group_by_column": None,        # Fully-qualified or bare column name
        "date_trunc_group": None,       # e.g. "month" → DATE_TRUNC('month', ...)
        "date_trunc_col": None,         # The date column to truncate
        "joins": [],
        "order_by": None,
        "order_direction": (
            "desc" if intent_result["intent"] == "top_n"
            else "asc" if intent_result["intent"] == "bottom_n"
            else None
        ),
        "limit": intent_result.get("limit"),
        "intent": intent_result["intent"],
        "subquery_type": intent_result.get("subquery_type"),
        "having_modifier": intent_result.get("having_modifier"),
        "subquery_column": None,
        "filters": [],
        "numeric_filters": [],         # Numeric threshold filters like stock < 20
        "special_query": None,         # For 'never_sold', 'left_join_null' patterns
        "dataset_confidence": None,
    }
 
    metrics = extraction_result.get("metrics", [])
    entities = extraction_result.get("entities", [])
    fallback_datasets = extraction_result.get("fallback_datasets", [])
    auto_metric = extraction_result.get("auto_metric")
    group_by_hint = extraction_result.get("group_by_hint")
    query_cleaned = extraction_result.get("_query_cleaned", "")
    query_tokens = extraction_result.get("_query_tokens", [])
    intent = intent_result["intent"]
    compare_targets = intent_result.get("slots", {}).get("compare_targets", [])
    ranking = dataset_ranking or extraction_result.get("dataset_ranking")
    business = business_intent or extraction_result.get("business_intent")
 
    # NOTE: ranking and business are used ONLY as fallback table resolvers
    # below (around step 9). We must NOT return early here — doing so
    # would skip ALL metric/aggregation/GROUP BY/filter/JOIN resolution,
    # making every query return a raw table dump.
        
    # Handle special meta-intents — return minimal spec for routing in query_service
    if intent_result.get("is_special"):
        spec["intent"] = intent
        # Resolve primary table by SCORE, not raw list order — a workspace
        # with several datasets should get the one that best matches the
        # query text (filename, column overlap), not whichever was uploaded
        # first / queried from the DB first.
        scored = extraction_result.get("dataset_scores", [])
        spec["dataset_candidates"] = scored
        if scored:
            spec["primary_table"] = scored[0]["table_name"]
        elif extraction_result.get("candidate_datasets"):
            spec["primary_table"] = extraction_result["candidate_datasets"][0]["table_name"]
        return spec
 
    # ------------------------------------------------------------------
    # Handle "never sold" special query type
    # ------------------------------------------------------------------
    if intent == "never_sold":
        # Need products table + orders/sales table, LEFT JOIN, WHERE orders IS NULL
        spec["special_query"] = "never_sold"
        scored = extraction_result.get("dataset_scores", [])
        spec["dataset_candidates"] = scored
        if scored:
            spec["primary_table"] = scored[0]["table_name"]
        else:
            all_datasets = extraction_result.get("candidate_datasets", [])
            if all_datasets:
                spec["primary_table"] = all_datasets[0]["table_name"]
        return spec
 
    # ------------------------------------------------------------------
    # 1. Resolve metric → primary table + aggregation column
    # ------------------------------------------------------------------
    # Only these intents actually want an aggregated value. For "list"/"filter"
    # intents we should never let a metric guess force spec["aggregation"] —
    # that was turning plain row-listing queries (e.g. "Show customer names
    # with their orders") into single aggregated numbers.
    AGGREGATING_INTENTS = {"aggregate", "top_n", "bottom_n", "trend", "distribution", "compare"}
 
    # ------------------------------------------------------------------
    # Score-based dataset resolution.
    #
    # Previously this picked metrics[0] / entities[0] / fallback_datasets[0]
    # — i.e. whichever list happened to be non-empty first, regardless of
    # how well OTHER workspace datasets actually matched the query. With
    # multiple uploaded datasets that's the direct cause of "always answers
    # from one dataset": two datasets can both have a metric named
    # "revenue", and the first one inserted always won.
    #
    # Now: re-rank the pre-computed dataset_scores (entity_extractor.py)
    # with filter-value evidence (resolved later in the pipeline than
    # entities/metrics), then pick metrics/entities belonging to the
    # highest-scoring dataset — not just index [0] of whichever list.
    # ------------------------------------------------------------------
    dataset_scores = extraction_result.get("dataset_scores", [])
    dataset_scores = apply_filter_evidence_to_scores(dataset_scores, filters or [])
    # Keep the re-ranked scores on the spec so the API layer can show
    # "Did you mean X?" alternatives without recomputing anything.
    spec["dataset_candidates"] = dataset_scores
 
    top_dataset_id = dataset_scores[0]["dataset_id"] if dataset_scores else None
    top_score = dataset_scores[0]["score"] if dataset_scores else 0
    # When there is only ONE dataset in the whole workspace (or only one
    # was scored at all), there is nothing to disambiguate against — the
    # confidence threshold exists to pick between competing datasets, not
    # to second-guess the only option there is. Never block on it here.
    single_dataset_workspace = len(dataset_scores) <= 1
    # Soft ambiguity signal — used only for annotation/logging, NEVER blocks execution.
    # The system ALWAYS auto-picks the top-scoring dataset and executes the query.
    # (Previously this caused a "needs_clarification" hard stop that returned no data.)
    runner_up_score = dataset_scores[1]["score"] if len(dataset_scores) > 1 else -1
    is_ambiguous = (
        top_score > 0
        and runner_up_score > 0
        and (top_score - runner_up_score) <= 1
        and top_score < DATASET_CONFIDENCE_THRESHOLD + 2
    )
    spec["dataset_ambiguous"] = is_ambiguous  # informational only, does not block
 
    # Prefer the metric/entity that actually lives on the top-scoring dataset.
    # Fall back to metrics[0]/entities[0] only if none matches the top dataset
    # (keeps old behavior as a safety net rather than a first line of defense).
    metrics_on_top = [m for m in metrics if m["dataset_id"] == top_dataset_id] if top_dataset_id else []
    entities_on_top = [e for e in entities if e["dataset_id"] == top_dataset_id] if top_dataset_id else []
 
    resolved_metric = None
    primary_table_confidence = "none"   # "high" = explicit metric/entity match, "low" = auto-guessed
    if metrics_on_top:
        resolved_metric = {
            "dataset_id": metrics_on_top[0]["dataset_id"],
            "column_name": metrics_on_top[0]["column_name"],
            "aggregation": metrics_on_top[0]["aggregation"],
        }
        primary_table_confidence = "high"
    elif metrics:
        resolved_metric = {
            "dataset_id": metrics[0]["dataset_id"],
            "column_name": metrics[0]["column_name"],
            "aggregation": metrics[0]["aggregation"],
        }
        primary_table_confidence = "high"
    elif auto_metric and (not top_dataset_id or auto_metric.get("dataset_id") == top_dataset_id):
        resolved_metric = auto_metric
        primary_table_confidence = "low"
    # NOTE: intentionally NOT falling back to `auto_metric` here when its
    # dataset_id disagrees with top_dataset_id. That fallback used to fire
    # unconditionally whenever the check above failed — i.e. precisely when
    # the auto-detected metric's column lives on a DIFFERENT dataset than
    # the one the resolver scored highest (post filter-evidence re-ranking).
    # Accepting it anyway is what let e.g. "average order amount" pull a
    # numeric column from an unrelated dataset (ds_38_insurance) while the
    # rest of the plan (entities, group-by) resolved against the correct
    # top-scoring dataset (ds_37_order_list) — producing a spec that
    # references two different tables. If they disagree, trust the dataset
    # resolver and let primary_table fall through to the score-based
    # resolution further below instead.
 
    # Re-point entity resolution at the top-scoring dataset when available,
    # without discarding entities entirely if the top dataset has none.
    if entities_on_top:
        entities = entities_on_top
 
    if resolved_metric:
        # Override aggregation if explicit keywords are used in the query
        if "average" in query_cleaned or "avg" in query_cleaned or "mean" in query_cleaned:
            resolved_metric["aggregation"] = "avg"
        elif "count" in query_cleaned:
            resolved_metric["aggregation"] = "count"
        elif "max" in query_cleaned or "highest" in query_cleaned:
            resolved_metric["aggregation"] = "max"
        elif "min" in query_cleaned or "lowest" in query_cleaned:
            resolved_metric["aggregation"] = "min"
 
        metric_dataset = db.query(Dataset).filter(Dataset.id == resolved_metric["dataset_id"]).first()
        if metric_dataset:
            spec["primary_table"] = metric_dataset.cleaned_table_name
            if intent in AGGREGATING_INTENTS:
                spec["select_column"] = resolved_metric["column_name"]
                spec["aggregation"] = resolved_metric["aggregation"]
 
                # ----------------------------------------------------------------
                # Let an EXPLICIT metric word in the query text override whichever
                # column was pre-resolved as "the metric" for this dataset.
                #
                # Previously, only the aggregation function (avg/count/max/min)
                # was re-checked against the query text above — the *column*
                # itself was never re-checked. That meant a query saying
                # "revenue" could silently return numbers from a pre-resolved
                # "quantity" column (or vice versa) whenever that column had
                # been auto-picked as the dataset's default metric for an
                # unrelated earlier query. Money words and count words are not
                # interchangeable, so we resolve the column explicitly here.
                # ----------------------------------------------------------------
                METRIC_WORD_COLUMN_HINTS = {
                    "revenue": ["revenue", "amount", "sales_value", "total_price", "sale_amount", "total_amount"],
                    "sales value": ["revenue", "amount", "sales_value", "total_price", "total_amount"],
                    "money": ["revenue", "amount", "total_price", "total_amount"],
                    "quantity": ["quantity", "qty", "units"],
                    "units sold": ["quantity", "qty", "units"],
                    "how many sold": ["quantity", "qty", "units"],
                }
                numeric_info_override = _get_table_numeric_info(spec["primary_table"])
                for phrase, col_hints in METRIC_WORD_COLUMN_HINTS.items():
                    if phrase in query_cleaned:
                        override_col = None
                        for col_name, info in numeric_info_override.items():
                            if info["is_numeric"] and any(h in col_name.lower() for h in col_hints):
                                override_col = col_name
                                break
                        if override_col:
                            spec["select_column"] = override_col
                            spec["select_column_needs_cast"] = numeric_info_override[override_col]["soft"]
                        break
 
        # If entity is on a different dataset, join it in
        # if entities and entities[0]["dataset_id"] != resolved_metric["dataset_id"]:
        #     entity = entities[0]
        #     entity_dataset = db.query(Dataset).filter(Dataset.id == entity["dataset_id"]).first()
        #     path = _find_relationship_path(db, workspace_id, resolved_metric["dataset_id"], entity["dataset_id"])
        #     if path and entity_dataset:
        #         for curr_id, nxt_id, rel in path:
        #             curr_ds = db.query(Dataset).filter(Dataset.id == curr_id).first()
        #             nxt_ds = db.query(Dataset).filter(Dataset.id == nxt_id).first()
        #             if curr_ds and nxt_ds:
        #                 join_entry = _build_join_entry(rel, curr_ds, nxt_ds)
        #                 if join_entry not in spec["joins"]:
        #                     spec["joins"].append(join_entry)
        #         spec["group_by_column"] = (
        #             f'"{entity_dataset.cleaned_table_name}"."{entity["identifier_column"]}"'
        #         )
        if entities and entities[0]["dataset_id"] != resolved_metric["dataset_id"]:
 
            entity = entities[0]
            entity_dataset = db.query(Dataset).filter(Dataset.id == entity["dataset_id"]).first()
 
            join_path = find_join_path(db, workspace_id, resolved_metric["dataset_id"], entity["dataset_id"])
 
            if join_path is not None:  # empty list means same dataset, non-None means a real path was found
                spec_joins = resolve_join_path_to_spec_joins(db, join_path)
                spec["joins"].extend(spec_joins)
                spec["group_by_column"] = f'"{entity_dataset.cleaned_table_name}"."{entity["identifier_column"]}"'
                spec["join_path_hops"] = len(join_path)  # useful for confidence scoring in Step 5
                
                # If entity is on the SAME dataset, just use its identifier column for grouping
            elif entities and entities[0]["dataset_id"] == resolved_metric["dataset_id"]:
                entity = entities[0]
                spec["group_by_column"] = f'"{metric_dataset.cleaned_table_name}"."{entity["identifier_column"]}"'
        
        if not spec.get("group_by_column") and intent in ("top_n", "bottom_n"):
            if not spec.get("aggregation"):
                spec["order_by"] = spec["select_column"]
 
    elif entities:
        entity_dataset = db.query(Dataset).filter(Dataset.id == entities[0]["dataset_id"]).first()
        if entity_dataset:
            spec["primary_table"] = entity_dataset.cleaned_table_name
            primary_table_confidence = "high"
    # elif fallback_datasets:
    #     # Prefer the fallback dataset that also scored highest, rather than
    #     # always index [0] (filename matches can still collide across
    #     # multiple similarly-named uploads).
    #     top_fallback = next(
    #         (fd for fd in fallback_datasets if fd["id"] == top_dataset_id), fallback_datasets[0]
    #     )
    #     spec["primary_table"] = top_fallback["table_name"]
    #     primary_table_confidence = "high"
    # elif top_dataset_id and (
    #     top_score >= DATASET_CONFIDENCE_THRESHOLD
    #     or single_dataset_workspace
    #     or (top_score > 0 and runner_up_score <= 0)
    # ):
    #     top_ds = db.query(Dataset).filter(Dataset.id == top_dataset_id).first()
    #     if top_ds:
    #         spec["primary_table"] = top_ds.cleaned_table_name
    #         primary_table_confidence = "medium"
    
    elif extraction_result.get("dataset_scores"):
        ranking = extraction_result["dataset_scores"]
        if ranking:
            spec["primary_table"] = ranking[0]["table_name"]
            spec["dataset_confidence"] = ranking[0].get("confidence", ranking[0]["score"])
    elif fallback_datasets:
        spec["primary_table"] = fallback_datasets[0]["table_name"]
 
    # ------------------------------------------------------------------
    # 2. Resolve GROUP BY from hint (e.g. "by cities" / "monthly" / "by customer")
    # ------------------------------------------------------------------
    if group_by_hint and spec["primary_table"] and not spec["group_by_column"]:
        if group_by_hint["type"] == "date_trunc":
            period = group_by_hint["period"]
            date_col = _find_date_column(spec["primary_table"])
            if date_col:
                spec["date_trunc_group"] = period
                spec["date_trunc_col"] = date_col
                # Date-grouped queries always need an aggregation
                if not spec["aggregation"]:
                    spec["aggregation"] = "sum"
                    # Pick best numeric column as the metric
                    _numeric_info_tmp = _get_table_numeric_info(spec["primary_table"])
                    num_cols = [c for c, info in _numeric_info_tmp.items() if info["is_numeric"]
                                and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                    best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                    spec["select_column"] = best_num or (num_cols[0] if num_cols else "*")
                    spec["select_column_needs_cast"] = bool(best_num) and _numeric_info_tmp.get(best_num, {}).get("soft", False)
 
        elif group_by_hint["type"] == "column":
            hints =group_by_hint.get("hints", [])
            # Try to find the column directly first
            # col = _find_column_by_hint(hint, spec["primary_table"]) 
            for hint in hints:
                col = _find_column_by_hint(
                    hint,
                    spec["primary_table"],
                )
                if not col:
                    col = _find_column_by_role(hint, spec["primary_table"])
                if col:
                    spec["group_by_column"] = f'"{spec["primary_table"]}"."{col}"'
                    # Ensure aggregation is set for grouped queries
                    if not spec["aggregation"]:
                        spec["aggregation"] = "sum"
                        _numeric_info_tmp = _get_table_numeric_info(spec["primary_table"])
                        num_cols = [c for c, info in _numeric_info_tmp.items() if info["is_numeric"]
                                    and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                        best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                        spec["select_column"] = best_num or (num_cols[0] if num_cols else "*")
                        spec["select_column_needs_cast"] = bool(best_num) and _numeric_info_tmp.get(best_num, {}).get("soft", False)
    
    # ------------------------------------------------------------------
    # 2b. Handle "top N X by revenue" pattern explicitly
    #     e.g. "Show top 5 customers by revenue"
    # ------------------------------------------------------------------
    if intent in ("top_n", "bottom_n") and not spec["group_by_column"] and spec["primary_table"]:
        # Look for dimension word in query to use as GROUP BY
        DIMENSION_ROLES = ["customer", "product", "city", "category", "region", "segment", "state", "country"]
        for role in DIMENSION_ROLES:
            if role in query_cleaned:
                col = _find_column_by_role(role, spec["primary_table"])
                if col:
                    spec["group_by_column"] = f'"{spec["primary_table"]}"."{col}"'
                    # Ensure aggregation for grouping
                    if not spec["aggregation"] and resolved_metric:
                        spec["aggregation"] = resolved_metric.get("aggregation", "sum")
                    elif not spec["aggregation"]:
                        spec["aggregation"] = "sum"
                        _numeric_info_tmp = _get_table_numeric_info(spec["primary_table"])
                        num_cols = [c for c, info in _numeric_info_tmp.items() if info["is_numeric"]
                                    and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                        best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                        spec["select_column"] = best_num or (num_cols[0] if num_cols else "*")
                        spec["select_column_needs_cast"] = bool(best_num) and _numeric_info_tmp.get(best_num, {}).get("soft", False)
                    break
 
    # ------------------------------------------------------------------
    # 3. Set ORDER BY for grouped queries
    # ------------------------------------------------------------------
    if spec.get("date_trunc_group"):
        spec["order_by"] = "period"
        spec["order_direction"] = "asc"
    elif spec["group_by_column"] and not spec.get("order_by"):
        spec["order_by"] = "value" if spec["aggregation"] else spec["select_column"]
        if intent in ("top_n", "bottom_n"):
            spec["order_direction"] = "desc" if intent == "top_n" else "asc"
        else:
            spec["order_direction"] = "desc"   # Default: highest first
 
    # ------------------------------------------------------------------
    # 5. Subquery column resolution (above/below average)
    # ------------------------------------------------------------------
    if spec["subquery_type"] and not spec.get("subquery_column"):
        numeric_info_sq: dict[str, dict] = {}
        try:
            numeric_info_sq = _get_table_numeric_info(spec["primary_table"]) if spec["primary_table"] else {}
        except Exception:
            pass
        num_cols = [c for c, info in numeric_info_sq.items() if info["is_numeric"]]
        best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned) if num_cols else None
        spec["subquery_column"] = best_num or (num_cols[0] if num_cols else None)
        if best_num:
            spec["subquery_column_needs_cast"] = numeric_info_sq.get(best_num, {}).get("soft", False)
 
    # ------------------------------------------------------------------
    # 5b. Implicit GROUP BY for subquery-type queries (above/below average)
    #
    # "Which products sold more than average" names a dimension ("product")
    # directly as the subject of the question — it does NOT use the "by X"
    # phrasing that group_by_hint (step 2) looks for. Without this block,
    # such queries fell through to sql_generator's row-level branch
    # (WHERE col >= (SELECT AVG(col) FROM table)), which filters individual
    # transaction rows with no grouping and no product name attached —
    # and, further downstream, often collapsed into a bare COUNT(*).
    #
    # Here we scan the query text for a known dimension word and, if found,
    # resolve it to a real column so the result comes back as
    # "product_name, total_sold" rows instead of a single number.
    # ------------------------------------------------------------------
    if spec["subquery_type"] and not spec.get("group_by_column") and spec["primary_table"]:
        DIMENSION_ROLES = ["product", "customer", "city", "state", "category", "region", "employee"]
        for role in DIMENSION_ROLES:
            if role in query_cleaned:
                col = _find_column_by_role(role, spec["primary_table"])
                if col:
                    spec["group_by_column"] = f'"{spec["primary_table"]}"."{col}"'
                    if not spec["aggregation"]:
                        spec["aggregation"] = "sum"
                        numeric_info_5b = _get_table_numeric_info(spec["primary_table"])
                        num_cols = [c for c, info in numeric_info_5b.items() if info["is_numeric"]
                                    and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                        best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                        spec["select_column"] = best_num or (num_cols[0] if num_cols else None)
                        if best_num:
                            spec["select_column_needs_cast"] = numeric_info_5b.get(best_num, {}).get("soft", False)
                    if not spec.get("order_by"):
                        spec["order_by"] = "value"
                        spec["order_direction"] = "desc"
                break
 
    # ------------------------------------------------------------------
    # 6. Handle "Show customer names with their orders" — JOIN query
    #    Look for multi-table keywords
    # ------------------------------------------------------------------
    if not spec["joins"] and spec["primary_table"]:
        join_keywords = {
            "order": ["order", "orders", "purchase", "transaction"],
            "customer": ["customer", "customers", "client"],
            "product": ["product", "products", "item"],
        }
        # If query references multiple table-like concepts, try to JOIN
        if _should_join_tables(query_cleaned, join_keywords):
            all_datasets = extraction_result.get("candidate_datasets", [])
            for ds_info in all_datasets:
                if ds_info["table_name"] != spec["primary_table"]:
                    # Find relationship
                    primary_ds = db.query(Dataset).filter(
                        Dataset.cleaned_table_name == spec["primary_table"]
                    ).first()
                    other_ds = db.query(Dataset).filter(Dataset.id == ds_info["id"]).first()
                    if primary_ds and other_ds:
                        path = _find_relationship_path(db, workspace_id, primary_ds.id, other_ds.id)
                        if path:
                            for curr_id, nxt_id, rel in path:
                                curr_ds = db.query(Dataset).filter(Dataset.id == curr_id).first()
                                nxt_ds = db.query(Dataset).filter(Dataset.id == nxt_id).first()
                                if curr_ds and nxt_ds:
                                    join_entry = _build_join_entry(rel, curr_ds, nxt_ds)
                                    if join_entry not in spec["joins"]:
                                        spec["joins"].append(join_entry)
                            break
 
    # ------------------------------------------------------------------
    # 7. Multi-table filter resolution with smart deduplication
    # ------------------------------------------------------------------
    if filters:
        if not spec["primary_table"]:
            spec["primary_table"] = filters[0]["table_name"]
 
        # Group filters by (table, column) to detect multi-value situations
        # e.g. city=Ahmedabad AND city=Surat → should become city IN (...)
        col_value_map: dict[tuple, list] = {}
        for f in filters:
            # Skip filters that wrongly match dimension columns when we already have GROUP BY
            if spec["group_by_column"] and not _is_specific_filter(f, query_cleaned):
                continue
            key = (f["table_name"], f["column"])
            col_value_map.setdefault(key, []).append(f["value"])

        # --------------------------------------------------------------
        # 6b. Resolve the TRUE comparison dimension for "compare X and Y"
        # queries before anything downstream treats every fuzzy-matched
        # column as equally valid.
        #
        # extract_filter_values() matches candidate words against EVERY
        # column's value dictionary across the dataset, so a single word
        # like "Ahmedabad" can land on more than one column (e.g. city AND,
        # spuriously, state) if the fuzzy scores happen to clear the
        # threshold on both. When that happens col_value_map ends up with
        # more than one "multi-value" column, the later "exactly one
        # multi-value column" check (7a/7b below) refuses to pick a GROUP BY
        # at all, and the query silently degrades into an unaggregated
        # "SELECT * ... WHERE city IN (...) AND state IN (...) LIMIT 500"
        # dump -- filtered on every polluted column, grouped/aggregated on
        # none of them.
        #
        # The intent detector already isolated the literal words the user
        # is comparing (compare_targets, e.g. ["ahmedabad", "surat"]) with
        # conservative, noise-resistant logic. Use that as ground truth to
        # pick the one column that actually explains those words, and drop
        # every other column's matches -- they were never part of what the
        # user was comparing.
        # --------------------------------------------------------------
        if intent == "compare" and compare_targets:
            joined_tables_for_compare = {spec["primary_table"]} | {j["table"] for j in spec["joins"]}
            resolved = _resolve_compare_dimension_column(
                compare_targets, col_value_map, spec["primary_table"], joined_tables_for_compare
            )
            if resolved:
                resolved_key, resolved_values = resolved
                col_value_map = {resolved_key: resolved_values}

        # --------------------------------------------------------------
        # 7a. Let strong filter evidence correct a weak table guess.
        #
        # e.g. "Compare Ahmedabad and Surat revenue" — if the metric-scoring
        # step only had a WEAK (auto-detected) guess for primary_table, but
        # "Ahmedabad"/"Surat" were found to literally exist in a *different*
        # dataset with no relationship to join through, that dataset is
        # almost certainly the one the user meant — not the auto-guessed one.
        # Without this, the filter was silently dropped and the query ran
        # unfiltered against the wrong table.
        # --------------------------------------------------------------
        if primary_table_confidence == "low" and col_value_map:
            filter_tables = {t for (t, _c) in col_value_map}
            if spec["primary_table"] not in filter_tables and len(filter_tables) == 1:
                (only_filter_table,) = filter_tables
                spec["primary_table"] = only_filter_table
                spec["joins"] = []
                spec["group_by_column"] = None
                if intent in AGGREGATING_INTENTS:
                    numeric_info_7a = _get_table_numeric_info(only_filter_table)
                    num_cols = [c for c, info in numeric_info_7a.items() if info["is_numeric"]
                                and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                    best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                    spec["select_column"] = best_num or (num_cols[0] if num_cols else "*")
                    if best_num:
                        spec["select_column_needs_cast"] = numeric_info_7a.get(best_num, {}).get("soft", False)
                    if not spec.get("aggregation"):
                        spec["aggregation"] = "sum"
                    # NOTE: this is a provisional single-column guess. If the
                    # query actually says "revenue" (or quantity/money
                    # phrasing), step 10 below recomputes select_column into
                    # a proper computed_metric/multi_metrics (deriving
                    # quantity * unit_price when there's no direct revenue
                    # column) and that takes precedence in sql_generator.
 
        all_datasets = db.query(Dataset).filter(Dataset.workspace_id == workspace_id).all()
        table_to_ds: dict[str, Dataset] = {d.cleaned_table_name: d for d in all_datasets}
        joined_tables: set[str] = ({spec["primary_table"]} | {j["table"] for j in spec["joins"]})
                                                             
        for (filter_table, filter_col), values in col_value_map.items():
            if filter_table == spec["primary_table"] or filter_table in joined_tables:
                if len(values) == 1:
                    spec["filters"].append({
                        "column": filter_col, "value": values[0], "table": filter_table,
                    })
                else:
                    # Multi-value → IN clause
                    spec["filters"].append({
                        "column": filter_col, "value": values, "table": filter_table, "op": "in",
                    })
                continue
 
            # Cross-table filter: resolve path using BFS graph search
            primary_ds = table_to_ds.get(spec["primary_table"])
            filter_ds = table_to_ds.get(filter_table)
            if primary_ds and filter_ds:
                join_path = find_join_path(db, workspace_id, primary_ds.id, filter_ds.id)
                if join_path is not None:
                    spec_joins = resolve_join_path_to_spec_joins(db, join_path)
                    
                    # Deduplicate joins before appending
                    for j in spec_joins:
                        if j not in spec["joins"]:
                            spec["joins"].append(j)
                    
                    joined_tables.add(filter_table)
                    filter_entry = {
                        "column": filter_col, 
                        "table": filter_table,
                        "value": values[0] if len(values) == 1 else values,
                    }
                    if len(values) > 1:
                        filter_entry["op"] = "in"
                    spec["filters"].append(filter_entry)
                else:
                    spec.setdefault("dropped_filters", []).append(filter_entry)
 
        # If comparing filtered cities/regions → add GROUP BY that dimension
        if len(col_value_map) >= 1 and not spec["group_by_column"] and not spec.get("date_trunc_group"):
            # Find the column(s) that carry MULTIPLE values — that's the
            # comparison dimension (e.g. city IN (Ahmedabad, Surat)).
            #
            # NOTE: this used to require len(col_value_map) == 1, i.e. ALL
            # filters had to collapse into a single column. That meant a
            # query like "Compare Ahmedabad and Surat revenue of keyboard"
            # — which has TWO filter columns, city (multi-value) AND
            # product (single-value "keyboard") — never matched, so
            # GROUP BY/aggregation were never set up and the query fell
            # back to a bare row COUNT. A single-value filter like a
            # product name is a plain WHERE-equality constraint, not part
            # of the comparison, so it shouldn't block detection of the
            # actual multi-value comparison column.
            multi_value_cols = [
                (key, values) for key, values in col_value_map.items() if len(values) > 1
            ]
            # Only treat this as a "comparison" if:
            #  (a) the intent actually implies a metric/breakdown (aggregate/top_n/
            #      bottom_n/trend/distribution/compare) — a plain filter/list query
            #      that happens to match 2 values (e.g. a stray synonym duplicate
            #      for "female") should NOT be forced into a GROUP BY it never asked for.
            #  (b) the multi-value column actually lives on primary_table, or on a
            #      table we've already joined in — otherwise we'd qualify GROUP BY
            #      with a table that never appears in FROM/JOIN, which Postgres
            #      rejects with "missing FROM-clause entry".
            # NOTE: intentionally NOT the full AGGREGATING_INTENTS set here.
            # That set includes plain "aggregate", which is what let a query
            # like "total number of female" — ONE explicit filter value,
            # count intent, no "by X"/breakdown wording at all — get promoted
            # into "GROUP BY sex" the moment extract_filter_values happened
            # to also fuzzy-match "male" on the same column (e.g. a stray
            # near-duplicate/synonym hit). The comment above already said
            # this shouldn't happen; the gate just didn't enforce it. A bare
            # aggregate query only earns a breakdown here if it explicitly
            # asked for one ("by X", "per X", etc. — implies_group_by).
            # Genuine comparison-shaped intents (compare/top_n/bottom_n/
            # trend/distribution) always legitimately want the breakdown.
            COMPARISON_LIKE_INTENTS = {"compare", "top_n", "bottom_n", "trend", "distribution"}
            if (
                len(multi_value_cols) == 1
                and (
                    intent in COMPARISON_LIKE_INTENTS
                    or (intent == "aggregate" and intent_result.get("slots", {}).get("implies_group_by"))
                )
            ):
                (f0_table, f0_col), f0_values = multi_value_cols[0]
                if f0_table == spec["primary_table"] or f0_table in joined_tables:
                    # Multiple values on same column → GROUP BY + IN
                    spec["group_by_column"] = f'"{f0_table}"."{f0_col}"'
                    if not spec.get("order_by"):
                        spec["order_by"] = "value"
                        spec["order_direction"] = "desc"
                    # Ensure aggregation. Prefer an explicitly resolved metric; only
                    # fall back to guessing a numeric column when the query text
                    # actually signals a sum-like metric is wanted. Otherwise default
                    # to COUNT(*), which is always a safe, meaningful fallback —
                    # unlike SUM of an arbitrary first numeric column.
                    if not spec["aggregation"] and spec["primary_table"]:
                        _numeric_info_tmp = _get_table_numeric_info(spec["primary_table"])
                        num_cols = [c for c, info in _numeric_info_tmp.items() if info["is_numeric"]
                                    and not any(h in c.lower() for h in ID_LIKE_HINTS)]
                        best_num = _find_best_numeric_column(num_cols, query_tokens, query_cleaned)
                        if best_num:
                            spec["aggregation"] = "sum"
                            spec["select_column"] = best_num
                            spec["select_column_needs_cast"] = _numeric_info_tmp.get(best_num, {}).get("soft", False)
                        else:
                            # No numeric column clearly matched the query wording —
                            # don't guess. Count rows per group instead.
                            spec["aggregation"] = "count"
                            spec["select_column"] = "*"
 
    # ------------------------------------------------------------------
    # 7b. Secondary dimension breakdown.
    #
    # "Compare Ahmedabad and Surat revenue" only ever grouped by the
    # filtered dimension (city). If the user *also* names another
    # dimension — "which product sells best in each city", "product
    # demand in both cities" — that second dimension was silently
    # dropped instead of becoming a compound GROUP BY (city, product).
    # ------------------------------------------------------------------
    if spec.get("group_by_column") and not isinstance(spec["group_by_column"], list) and spec["primary_table"]:
        existing_col = spec["group_by_column"].split(".")[-1].strip('"')
        SECONDARY_DIMENSION_ROLES = [
            "product", "category", "segment", "region", "state", "customer", "brand",
        ]
        for role in SECONDARY_DIMENSION_ROLES:
            if role in query_cleaned:
                col = _find_column_by_role(role, spec["primary_table"]) or _find_column_by_hint(role, spec["primary_table"])
                if col and col.lower() != existing_col.lower():
                    spec["group_by_column"] = [spec["group_by_column"], f'"{spec["primary_table"]}"."{col}"']
                break
 
    # ------------------------------------------------------------------
    # 7c. Fallback COUNT(*) for generic aggregate intent.
    #
    # Moved to run AFTER filter/group-by resolution (was previously step 4,
    # running *before* the city-comparison / revenue-detection logic above).
    # Firing early meant it locked in aggregation="count" the moment the
    # query contained a word like "total", so the later logic that
    # correctly picked SUM(revenue) for "Compare X and Y revenue" queries
    # never got a chance to run (it only applies when spec["aggregation"]
    # is still unset). Running it last means any explicit metric/GROUP BY
    # already resolved above always wins.
    #
    # Also now guarded: if the query names a specific attribute/value
    # (e.g. "male") that has no matching column anywhere in the dataset,
    # we do NOT silently count every row and imply that's the answer.
    # Instead we flag needs_clarification so the caller can tell the user
    # the column doesn't exist, rather than returning a misleading number.
    # ------------------------------------------------------------------
    if not resolved_metric and intent == "aggregate" and not spec.get("aggregation"):
        if (
            intent_result.get("matched_signals", {}).get("aggregate", 0) > 0
            or any(w in query_cleaned for w in ["count", "how many", "number of", "total", "no of"])
        ):
            missing_attr = _query_references_missing_attribute(query_cleaned, spec["primary_table"])
            if missing_attr:
                spec["needs_clarification"] = True
                spec["clarification_reason"] = (
                    f"This looks like it's asking about '{missing_attr}', but "
                    f"'{spec['primary_table']}' has no column for that. Available "
                    f"columns: {', '.join(_find_all_table_columns(spec['primary_table']))}."
                )
            else:
                # ------------------------------------------------------------
                # FIX: "total revenue" / "total sales" / "sum of X" were
                # landing here (resolved_metric never got set upstream, e.g.
                # no registered BusinessMetric matched) and blindly turned
                # into COUNT(*) — i.e. "how many rows in the whole table" —
                # instead of SUM(revenue). "total"/"sum"/"amount"/etc. mean
                # the user wants a numeric aggregate of SOME column, not a
                # row count. Only fall through to true COUNT(*) when the
                # query is actually asking "how many rows / how many X"
                # with no accompanying numeric-metric wording, or when no
                # usable numeric column exists on the table at all.
                # ------------------------------------------------------------
                # wants_row_count = any(
                #     w in query_cleaned for w in ["how many", "number of", "no. of", "count of"]
                # ) and not any(
                #     w in query_cleaned for w in [
                #         "total", "sum", "revenue", "sales", "amount", "profit",
                #         "quantity", "income", "spending", "spend", "value",
                #     ]
                # )
                count_phrase = any(w in query_cleaned for w in ["how many", "number of", "no of", "count of"])
                metric_word = any(w in query_cleaned for w in [
                    "revenue", "sales", "amount", "profit", "quantity", "income", "spending", "spend", "value"
                ])  # dropped "total"/"sum" — those are generic aggregation words, not column names
                wants_row_count = count_phrase and not metric_word
 
                best_num_fb = None
                if spec["primary_table"] and not wants_row_count:
                    numeric_info_fb = _get_table_numeric_info(spec["primary_table"])
                    num_cols_fb = [
                        c for c, info in numeric_info_fb.items()
                        if info["is_numeric"] and not any(h in c.lower() for h in ID_LIKE_HINTS)
                    ]
                    best_num_fb = _find_best_numeric_column(num_cols_fb, query_tokens, query_cleaned)
 
                if best_num_fb:
                    spec["aggregation"] = "sum"
                    spec["select_column"] = best_num_fb
                    numeric_info_fb = numeric_info_fb if 'numeric_info_fb' in locals() else {}
                    spec["select_column_needs_cast"] = numeric_info_fb.get(best_num_fb, {}).get("soft", False)
                else:
                    spec["aggregation"] = "count"
                    spec["select_column"] = "*"
 
    # ------------------------------------------------------------------
    # 8. Handle numeric threshold filters (stock below 20, price above 100)
    # ------------------------------------------------------------------
    numeric_threshold = intent_result.get("numeric_threshold")
    numeric_op = intent_result.get("numeric_op")
    if numeric_threshold is not None and spec["primary_table"]:
        # Find best matching numeric column based on query context. Uses
        # _get_table_numeric_info() (declared-numeric OR sniffed-numeric
        # text columns) rather than the declared-type-only map, so a
        # threshold like "stock below 20" still works when stock/quantity
        # was imported as TEXT/VARCHAR.
        numeric_info = _get_table_numeric_info(spec["primary_table"])
        col_types = {c: info["is_numeric"] for c, info in numeric_info.items()}
        # Look for stock/inventory columns first
        NUMERIC_FILTER_ROLES = {
            "stock": ["stock", "inventory", "quantity_available", "qty"],
            "quantity": ["quantity", "qty"],
            "price": ["price", "cost", "rate"],
            "age": ["age", "years"],
        }
        found_col = None
        for role_hint, col_hints in NUMERIC_FILTER_ROLES.items():
            if role_hint in query_cleaned or any(h in query_cleaned for h in col_hints):
                for col_name, is_num in col_types.items():
                    if is_num and any(h in col_name.lower() for h in col_hints):
                        found_col = col_name
                        break
            if found_col:
                break
        # Fallback: best numeric column
        if not found_col:
            num_cols = [c for c, is_num in col_types.items() if is_num
                        and not any(h in c.lower() for h in ID_LIKE_HINTS)]
            found_col = _find_best_numeric_column(num_cols, query_tokens, query_cleaned) if num_cols else None
 
        if found_col:
            op_symbol = {"lt": "<", "gt": ">", "eq": "="}.get(numeric_op or "lt", "<")
            spec["numeric_filters"].append({
                "column": found_col,
                "op": op_symbol,
                "value": numeric_threshold,
                "table": spec["primary_table"],
                "needs_cast": numeric_info.get(found_col, {}).get("soft", False),
            })
 
    # ------------------------------------------------------------------
    # 9. Fallback if primary_table is STILL completely unknown
    #
    # Previously this silently grabbed candidate_datasets[0] — i.e. picked
    # an arbitrary dataset and answered from it with zero indication to the
    # user that it was guessing. Now: use the ranked scores computed above.
    # Only auto-pick if the top dataset clears the confidence bar; otherwise
    # surface the ranked candidates so the caller (query_service / API
    # layer) can ask the user to clarify instead of quietly returning the
    # wrong dataset's data.
    # ------------------------------------------------------------------
    if not spec["primary_table"]:
        scored = spec.get("dataset_candidates") or extraction_result.get("dataset_scores", [])
        # AUTO-DETECT: Always pick the top-scoring dataset. NEVER return needs_clarification
        # just because two datasets scored similarly. The user wants an answer, not a riddle.
        # The `dataset_ambiguous` flag is already set above for logging.
        if scored and scored[0]["score"] > 0:
            # Pick the highest-scoring dataset unconditionally.
            spec["primary_table"] = scored[0]["table_name"]
            spec["dataset_resolution_confidence"] = (
                "high" if scored[0]["score"] >= DATASET_CONFIDENCE_THRESHOLD + 2
                else "medium" if scored[0]["score"] >= DATASET_CONFIDENCE_THRESHOLD
                else "low"
            )
        elif scored:
            # Scores are zero (no column overlap, no metrics, no filters) — still
            # pick the first alphabetically so the user gets SOME answer rather than nothing.
            spec["primary_table"] = scored[0]["table_name"]
            spec["dataset_resolution_confidence"] = "low"
        elif extraction_result.get("candidate_datasets"):
            # Absolute fallback: use whatever candidate dataset was found.
            candidates = extraction_result["candidate_datasets"]
            spec["primary_table"] = candidates[0]["table_name"]
            spec["dataset_resolution_confidence"] = "low"
 
    # ------------------------------------------------------------------
    # 10. Final money/quantity metric validation + multi-metric support
    #
    # Two problems this fixes:
    #
    # (a) A query saying "revenue" could still silently end up pointing at
    #     a "quantity" column whenever that was the only numeric column
    #     scored anywhere upstream (e.g. the low-confidence table-guess
    #     correction in step 7a just grabs whatever numeric column exists).
    #     That produced a technically-valid but WRONG answer with no
    #     indication anything was off. If the dataset has no revenue/amount
    #     column — and no quantity+price pair to derive one from — we now
    #     say so explicitly instead of quietly substituting quantity.
    #
    # (b) "Compare Ahmedabad and Surat revenue" only ever returned ONE
    #     number. If the query names more than one metric (e.g. "quantity
    #     and revenue", or the word "both"), return both as separate
    #     columns in the same grouped result instead of picking just one.
    # ------------------------------------------------------------------
    if spec["primary_table"] and spec.get("aggregation") and not spec.get("needs_clarification"):
        MONEY_PHRASES = ["revenue", "sales value", "money", "turnover", "sales amount", "total sales"]
        MONEY_COL_HINTS = ["revenue", "amount", "sales_value", "total_price", "sale_amount", "total_amount"]
        PRICE_COL_HINTS = ["price", "rate", "unit_price", "unit_cost", "cost"]
        QTY_PHRASES = ["quantity", "units sold", "how many sold", "no of units", "no. of units"]
        QTY_COL_HINTS = ["quantity", "qty", "units"]
 
        # NOTE: was _get_table_column_types(), which only trusts the
        # DECLARED database column type. Many CSV-upload pipelines store
        # every column as TEXT/VARCHAR regardless of content, which made
        # quantity/unit_price invisible here even though they held plain
        # numbers — money_col/qty_col/price_col all came back None and the
        # code fell straight into the "no revenue/amount/price column"
        # clarification, even for a perfectly answerable quantity*price
        # query. _get_table_numeric_info() additionally samples text
        # columns and recognizes numeric-looking data.
        numeric_info = _get_table_numeric_info(spec["primary_table"])
        numeric_cols = [c for c, info in numeric_info.items() if info["is_numeric"]]
 
        def _first_matching(hints: list[str]) -> str | None:
            for c in numeric_cols:
                if any(h in c.lower() for h in hints):
                    return c
            return None
 
        def _agg_ref(col_name: str) -> str:
            # Wraps the column in a cleaning CAST if it was only recognized
            # as numeric via sampling (soft=True); otherwise a plain
            # qualified reference, same as before.
            return _numeric_ref(spec["primary_table"], col_name, numeric_info)
 
        wants_money = any(p in query_cleaned for p in MONEY_PHRASES)
        wants_qty = any(p in query_cleaned for p in QTY_PHRASES)
        wants_both = "both" in query_cleaned or (wants_money and wants_qty)
 
        resolved_metrics: list[dict] = []   # [{"expr": "...", "alias": "..."}]
 
        if wants_money or wants_both:
            money_col = _first_matching(MONEY_COL_HINTS)
            if money_col:
                resolved_metrics.append({
                    "expr": f'{spec["aggregation"].upper()}({_agg_ref(money_col)})',
                    "alias": "revenue",
                })
            else:
                # No direct revenue/amount column — try deriving it from
                # quantity * unit price, which is how "revenue" usually
                # exists implicitly in order-line-level datasets.
                qty_col = _first_matching(QTY_COL_HINTS)
                price_col = _first_matching(PRICE_COL_HINTS)
                if qty_col and price_col:
                    resolved_metrics.append({
                        "expr": (
                            f'{spec["aggregation"].upper()}({_agg_ref(qty_col)} '
                            f'* {_agg_ref(price_col)})'
                        ),
                        "alias": "revenue",
                    })
                elif wants_money and not wants_both:
                    # Explicitly asked for money and there is truly no way
                    # to produce it — say so instead of silently returning
                    # quantity (or anything else) labeled as revenue.
                    spec["needs_clarification"] = True
                    spec["clarification_reason"] = (
                        f"'{spec['primary_table']}' has no revenue/amount/price column, so I can't "
                        f"compute revenue. Available columns: {', '.join(_find_all_table_columns(spec['primary_table']))}."
                    )
 
        if not spec.get("needs_clarification") and (wants_qty or wants_both):
            qty_col = _first_matching(QTY_COL_HINTS)
            if qty_col:
                resolved_metrics.append({
                    "expr": f'{spec["aggregation"].upper()}({_agg_ref(qty_col)})',
                    "alias": "quantity",
                })
            elif wants_qty and not wants_both:
                spec["needs_clarification"] = True
                spec["clarification_reason"] = (
                    f"'{spec['primary_table']}' has no quantity/units column. "
                    f"Available columns: {', '.join(_find_all_table_columns(spec['primary_table']))}."
                )
 
        if not spec.get("needs_clarification") and resolved_metrics:
            # De-dupe (in case money and quantity resolved to the same thing)
            seen_aliases = set()
            deduped = []
            for m in resolved_metrics:
                if m["alias"] not in seen_aliases:
                    seen_aliases.add(m["alias"])
                    deduped.append(m)
            resolved_metrics = deduped
 
            if len(resolved_metrics) > 1:
                spec["multi_metrics"] = resolved_metrics
            elif len(resolved_metrics) == 1:
                # Single explicit metric resolved here — this is the
                # authoritative answer to "what does revenue/quantity mean
                # in THIS query," overriding whatever column upstream steps
                # guessed at.
                spec["computed_metric"] = resolved_metrics[0]
 
    return spec
 
 
# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
 
def _should_join_tables(query_cleaned: str, join_keywords: dict) -> bool:
    """
    Detect if the query references multiple table concepts that warrant a JOIN.
    e.g. "customer names with their orders" → True
    """
    found = sum(1 for kw_list in join_keywords.values()
                if any(kw in query_cleaned for kw in kw_list))
    return found >= 2
 
 
def _is_specific_filter(f: dict, query_cleaned: str) -> bool:
    """
    Return True if this filter represents a specific value the user mentioned
    (e.g. "Ahmedabad", "Electronics") rather than a generic dimension match.
 
    Filter values come from extract_filter_values()'s fuzzy match against the
    dataset's value_dictionary, and already carry a "match_score" (>0.72,
    enforced upstream). Requiring the DB value to also appear VERBATIM in the
    cleaned query double-counts that check and fails on ordinary morphology
    ("electronic" -> "Electronics", "customer" -> "Customers", typos, etc.),
    silently dropping filters that were correctly resolved. Trust the
    upstream fuzzy score instead; fall back to the verbatim check only for
    filters that somehow lack a match_score (e.g. constructed by other code
    paths).
    """
    if "match_score" in f:
        return f["match_score"] > 0.72
    value_lower = str(f.get("value", "")).lower()
    return value_lower in query_cleaned
 
 
from collections import deque, defaultdict
 
def _find_relationship_path(db: Session, workspace_id: int, a_id: int, b_id: int) -> list:
    """Return the shortest path of validated relationships using BFS.
    Returns a list of tuples: (current_ds_id, next_ds_id, relationship)."""
    if a_id == b_id:
        return []
        
    rels = (
        db.query(DatasetRelationship)
        .filter(
            DatasetRelationship.workspace_id == workspace_id,
            DatasetRelationship.is_validated == "valid"
        ).all()
    )
    
    adj = defaultdict(list)
    for r in rels:
        adj[r.source_dataset_id].append((r.target_dataset_id, r))
        adj[r.target_dataset_id].append((r.source_dataset_id, r))
        
    queue = deque([(a_id, [])])
    visited = {a_id}
    
    while queue:
        curr, path = queue.popleft()
        if curr == b_id:
            return path
            
        for nxt, rel in adj[curr]:
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [(curr, nxt, rel)]))
                
    return None
 
def find_join_path(db: Session, workspace_id: int, a_id: int, b_id: int):
    return _find_relationship_path(db, workspace_id, a_id, b_id)
 
def resolve_join_path_to_spec_joins(db: Session, join_path: list) -> list:
    spec_joins = []
    for curr_id, nxt_id, rel in join_path:
        curr_ds = db.query(Dataset).filter(Dataset.id == curr_id).first()
        nxt_ds = db.query(Dataset).filter(Dataset.id == nxt_id).first()
        if curr_ds and nxt_ds:
            spec_joins.append(_build_join_entry(rel, curr_ds, nxt_ds))
    return spec_joins
 
 
def _build_join_entry(rel, left_ds: Dataset, right_ds: Dataset) -> dict:
    """Build a join descriptor with correct column orientation."""
    if rel.source_dataset_id == left_ds.id:
        left_col, right_col = rel.source_column, rel.target_column
    else:
        left_col, right_col = rel.target_column, rel.source_column
    return {
        "table": right_ds.cleaned_table_name,
        "left_table": left_ds.cleaned_table_name,
        "left_column": left_col,
        "right_column": right_col,
    }
