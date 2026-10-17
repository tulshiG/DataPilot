# # -------------------------------------------------------------

# import re
# from sqlalchemy.orm import Session
# from sqlalchemy import create_engine, text as sql_text, inspect
# from app.models.knowledge_base import BusinessEntity, BusinessMetric
# from app.models.dataset import Dataset
# from app.core.config import settings
 
# # ---------------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------------
 
# ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
# NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
# DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]
 
# SEMANTIC_ALIASES = {
#     "revenue": ["revenue", "sales", "amount", "total_amount", "total_sales", "price"],
#     "orders": ["order_id", "orders", "order_count", "transaction_id"],
#     "customers": ["customer_id", "customer_name", "customer", "client", "user"],
#     "profit": ["profit", "net_profit", "gross_profit", "margin"],
#     "quantity": ["quantity", "qty", "count", "volume"],
#     "stock": ["stock", "inventory", "quantity_available", "quantity_on_hand"],
# }
 
# # Words that are part of query structure / analytical intent — NEVER filter candidates.
# # Prevents "all" → matching "Allahabad", "revenue" → matching product names, etc.
# # NOTE: "city", "category", "customer", "product" removed from here since they
# # are needed as GROUP BY hints. They stay in QUERY_ACTION_CAPS only.
# QUERY_STRUCTURAL_TERMS: set[str] = {
#     # Query action verbs
#     "show", "display", "list", "find", "get", "fetch", "give", "tell",
#     "what", "which", "how", "where", "when", "who", "why",
#     # Aggregation & metric words
#     "revenue", "sales", "profit", "income", "amount", "total", "sum", "count",
#     "average", "avg", "mean", "maximum", "minimum", "number", "value",
#     # Ranking
#     "top", "bottom", "highest", "lowest", "best", "worst", "most", "least",
#     # Time/trend
#     "monthly", "yearly", "daily", "weekly", "annual", "quarterly",
#     "month", "year", "day", "week", "quarter", "trend", "time",
#     # Analytical structure
#     "distribution", "comparison", "analysis", "breakdown", "growth",
#     "above", "below", "greater", "less", "between", "never", "sold",
#     # Quantifiers
#     "all", "every", "each", "any", "some", "both", "few", "many",
#     # Generic column-group hints (safe to exclude from filter search)
#     "region", "regions", "segment", "segments",
#     "state", "states", "country", "countries", "territory", "territories",
#     "stock", "price", "discount", "quantity",
#     # Generic filler
#     "please", "need", "want", "give", "with", "their", "data",
#     "report", "result", "results", "per", "using", "based",
#     "purchase", "purchases", "compare", "versus", "generate", "create",
#     "business", "insights", "dashboard", "trend", "sales",
#     "order", "orders",
# }
 
# # Capitalized words that are query structure — not data values
# QUERY_ACTION_CAPS: set[str] = {
#     "Show", "Display", "List", "Find", "Get", "Fetch", "Give", "Tell",
#     "What", "Which", "How", "Where", "When", "Who", "Why", "Compare",
#     "Top", "Bottom", "Above", "Below", "Never", "All", "By", "Generate",
#     "Create", "Build", "Their", "With",
# }
 
# # Irregular plural → singular mapping (for GROUP BY hint normalization)
# IRREGULAR_PLURALS: dict[str, str] = {
#     "cities": "city",
#     "categories": "category",
#     "countries": "country",
#     "companies": "company",
#     "territories": "territory",
#     "subsidiaries": "subsidiary",
#     "subcategories": "subcategory",
#     "states": "state",
#     "regions": "region",
#     "segments": "segment",
#     "quantities": "quantity",
#     "customers": "customer",
#     "products": "product",
#     "orders": "order",
# }
 
# # Date period keywords for GROUP BY date_trunc detection
# DATE_PERIOD_HINTS: dict[str, str] = {
#     "month": "month", "monthly": "month",
#     "year": "year", "yearly": "year", "annual": "year", "annually": "year",
#     "day": "day", "daily": "day",
#     "week": "week", "weekly": "week",
#     "quarter": "quarter", "quarterly": "quarter",
# }
 
# # Column roles for GROUP BY resolution — maps query words to column name hints
# COLUMN_ROLE_HINTS: dict[str, list[str]] = {
#     "city": ["city", "ship_city", "billing_city", "location", "town"],
#     "category": ["category", "product_category", "item_category", "type"],
#     "product": ["product", "product_name", "item", "sku", "item_name"],
#     "customer": ["customer", "customer_name", "client", "buyer", "name"],
#     "region": ["region", "area", "zone"],
#     "segment": ["segment", "group", "tier"],
#     "state": ["state", "province"],
#     "country": ["country", "nation"],
#     "order": ["order_id", "order", "transaction"],
# }
 
 
# # ---------------------------------------------------------------------------
# # Public extraction functions
# # ---------------------------------------------------------------------------
 
# def extract_entities_and_metrics(
#     db: Session, workspace_id: int, tokens: list[str], cleaned_text: str,
#     dataset_id_filter: int | None = None,
# ) -> dict:
#     """
#     Match query tokens against registered BusinessMetric/BusinessEntity.
#     Falls back to auto-detecting a numeric column from the dataset schema.
 
#     Also scores EVERY workspace dataset against the query (see
#     score_dataset_candidates) so downstream code can pick the best dataset
#     across the whole workspace instead of whichever metric/entity happened
#     to be matched first.
#     """
#     entities = db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()
#     metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()
 
#     if dataset_id_filter:
#         datasets = [d for d in datasets if d.id == dataset_id_filter]
#         entities = [e for e in entities if e.dataset_id == dataset_id_filter]
#         metrics = [m for m in metrics if m.dataset_id == dataset_id_filter]
 
#     matched_entities = []
#     for entity in entities:
#         name_lower = entity.name.lower()
#         if name_lower in cleaned_text or any(tok in name_lower for tok in tokens):
#             matched_entities.append(entity)
 
#     matched_metrics = []
#     for metric in metrics:
#         key_lower = metric.metric_key.lower()
#         name_lower = metric.name.lower()
        
#         if re.search(rf"\b{re.escape(key_lower)}\b", cleaned_text) or any(
#             re.search(rf"\b{re.escape(word)}\b", cleaned_text) for word in name_lower.split()
#         ):
#             matched_metrics.append(metric)
 
#     matched_datasets = []
#     if not matched_entities:
#         for ds in datasets:
#             stub = ds.original_filename.rsplit(".", 1)[0].lower()
#             if stub in cleaned_text or stub.rstrip("s") in tokens:
#                 matched_datasets.append(ds)
 
#     auto_metric = None
#     if not matched_metrics:
#         auto_metric = _auto_match_metric(datasets, tokens, cleaned_text)
 
#     # ------------------------------------------------------------------
#     # NEW: score every candidate dataset against the query so the caller
#     # can rank them instead of blindly taking metrics[0]/entities[0].
#     # ------------------------------------------------------------------
#     dataset_scores = score_dataset_candidates(
#         datasets=datasets,
#         tokens=tokens,
#         cleaned_text=cleaned_text,
#         matched_entities=matched_entities,
#         matched_metrics=matched_metrics,
#         matched_datasets=matched_datasets,
#     )
 
#     return {
#         "entities": [
#             {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "identifier_column": e.identifier_column}
#             for e in matched_entities
#         ],
#         "metrics": [
#             {
#                 "id": m.id, "name": m.name, "metric_key": m.metric_key,
#                 "dataset_id": m.dataset_id, "column_name": m.column_name,
#                 "aggregation": m.aggregation,
#             }
#             for m in matched_metrics
#         ],
#         "fallback_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in matched_datasets
#         ],
#         "auto_metric": auto_metric,
#         "candidate_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in datasets
#         ],
#         # Ranked list of every workspace dataset with a confidence score and
#         # human-readable reasons. Highest score first. Empty list == no
#         # datasets in workspace at all.
#         "dataset_scores": dataset_scores,
#     }
 
 
# # ---------------------------------------------------------------------------
# # Dataset scoring — replaces "first metric/entity/dataset found wins"
# # ---------------------------------------------------------------------------
 
# # Minimum score (out of the weights below) before we trust a dataset choice
# # without asking the user to confirm. Tune based on observed false-positive rate.
# DATASET_CONFIDENCE_THRESHOLD = 3

# # How much each kind of signal counts toward a dataset's score. Centralized
# # here so tuning doesn't require touching query_mapper.py.
# SCORE_WEIGHTS = {
#     "explicit_metric": 5,     # a registered BusinessMetric on this dataset matched query text
#     "explicit_entity": 5,     # a registered BusinessEntity on this dataset matched query text
#     "filename_match": 4,      # dataset filename/stub literally appears in the query
#     "filter_value_hit": 4,    # a value the user typed was actually found IN this dataset's data
#     "column_name_overlap": 1, # per query token that overlaps a column name in this dataset (capped)
#     "domain_keyword": 2,      # query mentions a domain-specific term suggesting this dataset
# }
# MAX_COLUMN_OVERLAP_SCORE = 3  # cap so a wide table doesn't win purely on column-name volume

# # Domain keyword signals per dataset filename pattern.
# # If the dataset filename contains any of the keys, and the query contains any of the
# # associated terms, boosted by `domain_keyword` weight.
# DOMAIN_KEYWORD_SIGNALS: dict[str, list[str]] = {
#     "insurance": ["insurance", "premium", "claim", "charges", "bmi", "smoker", "insured",
#                   "deductible", "coverage", "policy", "beneficiary"],
#     "order": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
#               "product", "sales", "revenue", "category", "sub-category"],
#     "sales": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
#               "product", "sales", "revenue", "category"],
#     "student": ["student", "score", "grade", "exam", "marks", "pass", "fail", "gpa"],
#     "employee": ["employee", "salary", "department", "hire", "position", "role", "payroll"],
#     "inventory": ["stock", "inventory", "warehouse", "sku", "reorder", "quantity"],
#     "medical": ["patient", "diagnosis", "hospital", "doctor", "treatment", "medication"],
# }
# MAX_DATASET_SCORE = (
#     SCORE_WEIGHTS["explicit_metric"]
#     + SCORE_WEIGHTS["explicit_entity"]
#     + SCORE_WEIGHTS["filename_match"]
#     + SCORE_WEIGHTS["filter_value_hit"]
#     + MAX_COLUMN_OVERLAP_SCORE * SCORE_WEIGHTS["column_name_overlap"]
#     + SCORE_WEIGHTS["domain_keyword"]
# )


# def _attach_dataset_confidence(dataset_scores: list[dict]) -> list[dict]:
#     """Normalize raw dataset match scores into a 0-100 confidence scale."""
#     for entry in dataset_scores:
#         entry["confidence"] = round(
#             min(100.0, (entry["score"] / MAX_DATASET_SCORE) * 100.0), 1
#         ) if MAX_DATASET_SCORE else 0.0
#     return dataset_scores
 
 
# def score_dataset_candidates(
#     datasets: list,
#     tokens: list[str],
#     cleaned_text: str,
#     matched_entities: list | None = None,
#     matched_metrics: list | None = None,
#     matched_datasets: list | None = None,
#     filter_hits: list[dict] | None = None,
# ) -> list[dict]:
#     """
#     Score every workspace dataset against the current query so the caller
#     can pick the best match instead of an arbitrary "first found" dataset.
 
#     Returns a list of dicts sorted by score (descending):
#         {
#             "dataset_id": int,
#             "table_name": str,
#             "name": str,
#             "score": int,
#             "reasons": list[str],   # human-readable, safe to show to the user
#         }
#     """
#     matched_entities = matched_entities or []
#     matched_metrics = matched_metrics or []
#     matched_datasets = matched_datasets or []
#     filter_hits = filter_hits or []
 
#     entity_ds_ids = {e.dataset_id for e in matched_entities}
#     metric_ds_ids = {m.dataset_id for m in matched_metrics}
#     filename_ds_ids = {d.id for d in matched_datasets}
#     filter_hit_ds_ids = {f["dataset_id"] for f in filter_hits if "dataset_id" in f}
 
#     # Open ONE engine/inspector for the whole scoring pass rather than one
#     # per dataset — this runs on every query, so it needs to stay cheap.
#     engine = create_engine(settings.DATABASE_URL)
#     try:
#         inspector = inspect(engine)
 
#         scored: list[dict] = []
#         for ds in datasets:
#             score = 0
#             reasons: list[str] = []
 
#             if ds.id in metric_ds_ids:
#                 score += SCORE_WEIGHTS["explicit_metric"]
#                 reasons.append("a business metric on this dataset matched the query")
 
#             if ds.id in entity_ds_ids:
#                 score += SCORE_WEIGHTS["explicit_entity"]
#                 reasons.append("a business entity on this dataset matched the query")
 
#             if ds.id in filename_ds_ids:
#                 score += SCORE_WEIGHTS["filename_match"]
#                 reasons.append(f"the dataset name '{ds.original_filename}' appears in the query")
 
#             if ds.id in filter_hit_ds_ids:
#                 score += SCORE_WEIGHTS["filter_value_hit"]
#                 reasons.append("a value mentioned in the query was found in this dataset's data")
 
#             # Column-name overlap — cheap signal that works even with zero
#             # registered metrics/entities (many workspaces won't have them set up).
#             try:
#                 col_names = [c["name"] for c in inspector.get_columns(ds.cleaned_table_name)]
#             except Exception:
#                 col_names = []
#             overlap = 0
#             import difflib
#             for col in col_names:
#                 col_words = col.lower().replace("_", " ").split()
#                 is_match = False
#                 for w in col_words:
#                     if w in tokens or w in cleaned_text:
#                         is_match = True
#                         break
#                     # Fuzzy match with tokens
#                     for t in tokens:
#                         if difflib.SequenceMatcher(None, w, t.lower()).ratio() > 0.8:
#                             is_match = True
#                             break
#                     if is_match:
#                         break
#                 if is_match:
#                     overlap += 1
                    
#             if overlap:
#                 col_score = min(overlap, MAX_COLUMN_OVERLAP_SCORE) * SCORE_WEIGHTS["column_name_overlap"]
#                 score += col_score
#                 reasons.append(f"{overlap} column name(s) relate to words in the query")
 
#             # Domain keyword signal: if the query uses domain-specific terms that
#             # match this dataset's domain, boost its score.
#             ds_name_lower = ds.original_filename.lower()
#             for domain_key, domain_terms in DOMAIN_KEYWORD_SIGNALS.items():
#                 if domain_key in ds_name_lower:
#                     matched_domain_terms = [t for t in domain_terms if t in cleaned_text]
#                     if matched_domain_terms:
#                         score += SCORE_WEIGHTS["domain_keyword"]
#                         reasons.append(f"domain terms {matched_domain_terms[:2]} matched dataset '{ds.original_filename}'")
#                     break

#             scored.append({
#                 "dataset_id": ds.id,
#                 "table_name": ds.cleaned_table_name,
#                 "name": ds.original_filename,
#                 "score": score,
#                 "reasons": reasons,
#             })
#     finally:
#         engine.dispose()

#     scored = _attach_dataset_confidence(scored)
#     scored.sort(key=lambda s: s["score"], reverse=True)
#     return scored


# def apply_filter_evidence_to_scores(dataset_scores: list[dict], filters: list[dict]) -> list[dict]:
#     """
#     Re-rank dataset scores once filter values are known.
 
#     Filters are resolved in a later pipeline stage than the initial entity/
#     metric scoring (forward_chaining.py runs preprocess -> intent ->
#     entities/metrics -> group_by -> filters, in that order), so this is
#     called from query_mapper.py right before the primary_table decision to
#     fold in "this literal value was actually found in dataset X's data" —
#     one of the strongest possible signals for which dataset the user means.
#     Returns a NEW sorted list; does not mutate the input.
#     """
#     if not filters:
#         return dataset_scores
 
#     hit_ds_ids: dict[int, int] = {}
#     for f in filters:
#         ds_id = f.get("dataset_id")
#         if ds_id is None:
#             continue
#         hit_ds_ids[ds_id] = hit_ds_ids.get(ds_id, 0) + 1
 
#     if not hit_ds_ids:
#         return dataset_scores
  
#     updated = []
#     for entry in dataset_scores:
#         new_entry = dict(entry)
#         hits = hit_ds_ids.get(entry["dataset_id"], 0)
#         if hits:
#             new_entry["score"] = entry["score"] + hits * SCORE_WEIGHTS["filter_value_hit"]
#             new_entry["reasons"] = entry["reasons"] + [
#                 f"{hits} value(s) from the query were found in this dataset's data"
#             ]
#         updated.append(new_entry)
  
#     updated = _attach_dataset_confidence(updated)
#     updated.sort(key=lambda s: s["score"], reverse=True)
#     return updated
 
 
# def extract_group_by_hint(cleaned_text: str, tokens: list[str]) -> dict | None:
#     """
#     Detect GROUP BY intent from patterns like:
#       'by cities', 'by category', 'per month', 'monthly revenue', 'yearly trend',
#       'by customer', 'by product', etc.
 
#     Returns one of:
#       {"type": "date_trunc", "period": "month"}    — for date-based grouping
#       {"type": "column",    "hints": ["city"]}     — for column-based grouping
#       None                                          — no group-by detected
#     """
#     # Check for time-based keywords anywhere in the query (monthly, yearly, etc.)
#     for keyword, period in DATE_PERIOD_HINTS.items():
#         if keyword in cleaned_text:
#             return {"type": "date_trunc", "period": period}
 
#     # Match ALL explicit "by [WORD]" or "per [WORD]" patterns — not just the first.
#     # This fixes queries like "bottom 3 cities by sales" where re.search() would
#     # find "by sales" first, skip it (sales is a skip word), and return None
#     # without ever seeing "cities". Now we try every match in order.
#     #
#     # skip_words includes metric words (sales, revenue, quantity…) so that
#     # "by quantity sold" or "by revenue" doesn't suppress detection of the actual
#     # dimension (product, city, etc.) elsewhere in the query.
#     skip_words = {
#         "revenue", "sales", "value", "amount", "total", "top", "bottom",
#         "their", "using", "quantity", "qty", "stock", "count", "price",
#         "cost", "rate", "profit", "income",
#     }
#     by_matches = re.findall(r"\b(?:by|per)\s+(?:all\s+|each\s+)?(\w+)", cleaned_text)
#     for by_word in by_matches:
#         by_word = by_word.lower()
#         if by_word in skip_words:
#             continue
#         # Check for date period in the "by X" word
#         if by_word in DATE_PERIOD_HINTS:
#             return {"type": "date_trunc", "period": DATE_PERIOD_HINTS[by_word]}
#         # Normalize irregular plural to singular for column matching
#         normalized = IRREGULAR_PLURALS.get(by_word, by_word)
#         return {"type": "column", "hints": [normalized]}
 
#     # Also check dimension words embedded in the query WITHOUT explicit "by/per".
#     # Handles: "Show revenue city", "city revenue", "category distribution",
#     # AND plural forms like "bottom 3 cities by sales" (where "by sales" was
#     # skipped above but "cities" → "city" can still be found here).
#     DIMENSION_WORDS = {
#         "city": "city", "cities": "city",
#         "category": "category", "categories": "category",
#         "product": "product", "products": "product",
#         "customer": "customer", "customers": "customer",
#         "region": "region", "regions": "region",
#         "segment": "segment", "segments": "segment",
#         "state": "state", "states": "state",
#         "country": "country", "countries": "country",
#     }
#     # Context signals that indicate we're in an aggregation/breakdown query.
#     AGG_CONTEXT = [
#         "revenue", "sales", "amount", "total", "distribution",
#         "breakdown", "comparison", "generate", "top", "bottom",
#         "average", "count", "how many",
#     ]
#     for word, hint in DIMENSION_WORDS.items():
#         # Only if there's also a revenue/aggregation context
#         if word in cleaned_text and any(agg in cleaned_text for agg in
#                                          ["revenue", "sales", "amount", "total", "distribution",
#                                           "breakdown", "comparison", "generate"]):
#             return {"type": "column", "hints": [hint]}
 
#     return None
 
 
# def extract_numeric_threshold_filter(
#     cleaned_text: str,
#     table_name: str,
#     dataset_id: int,
# ) -> list[dict]:
#     """
#     Detect numeric threshold conditions like "stock below 20", "price above 100".
#     Returns a list of filter dicts for the query spec.
#     """
#     # Pattern: <column_hint> <operator> <number>  OR  <operator> <number>
#     # patterns = [
#     #     # "stock below 20" / "quantity less than 10"
#     #     re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count)\b"
#     #                r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to)\s+"
#     #                r"(\d+(?:\.\d+)?)", re.I),
#     #     # Reversed: "below 20 stock"
#     #     re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
#     #                r"\s+(?:stock|items|units|products)", re.I),
#     # ]
#     patterns = [
#         # NEW: Made the operator block (?:...)? optional and added bmi/children fields
#         re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count|bmi|children)\b"
#                    r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to|=|>|<)?\s*"
#                    r"(\d+(?:\.\d+)?)", re.I),
#         re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
#                    r"\s+(?:stock|items|units|products|years|age)", re.I),
#     ]
 
#     OPERATOR_MAP = {
#         "below": "<", "under": "<", "less than": "<",
#         "above": ">", "over": ">", "greater than": ">", "more than": ">",
#         "equal to": "=",
#     }
 
#     # found = []
#     # for pattern in patterns:
#     #     match = pattern.search(cleaned_text)
#     #     if match:
#     #         groups = match.groups()
#     #         col_hint = groups[0].lower() if len(groups) > 1 else "stock"
#     #         value = float(groups[-1])
#     #         # Determine operator from match text
#     #         matched_str = match.group(0).lower()
#     #         op = "<"  # default
#     #         for op_word, op_sym in OPERATOR_MAP.items():
#     #             if op_word in matched_str:
#     #                 op = op_sym
#     #                 break
#     #         found.append({
#     #             "column_hint": col_hint,
#     #             "op": op,
#     #             "value": value,
#     #             "dataset_id": dataset_id,
#     #             "table_name": table_name,
#     #             "is_numeric": True,
#     #         })
#     #         break  # Only one threshold per query for now
 
#     # return found
#     found = []
#     for pattern in patterns:
#         for match in pattern.finditer(cleaned_text):  # NEW: using finditer to capture all
#             groups = match.groups()
#             col_hint = groups[0].lower() if len(groups) > 1 else "stock"
#             value = float(groups[-1])
#             matched_str = match.group(0).lower()
            
#             op = "="  # NEW: Default to equal for implicit ranges like "age 30"
#             for op_word, op_sym in OPERATOR_MAP.items():
#                 if re.search(rf"\b{re.escape(op_word)}\b", matched_str) or op_word in matched_str:
#                     op = op_sym
#                     break
                    
#             found.append({
#                 "column_hint": col_hint,
#                 "op": op,
#                 "value": value,
#                 "dataset_id": dataset_id,
#                 "table_name": table_name,
#                 "is_numeric": True,
#             })
#     return found
 
 
# def extract_filter_values(
#     db: Session, workspace_id: int, tokens: list[str], raw_text: str,
#     dataset_id_filter: int | None = None,
# ) -> list[dict]:
#     """
#     Detect specific filter values by matching candidates against actual DB values.
 
#     CANDIDATE STRATEGY (critical for avoiding filter pollution):
#     Only use HIGH-CONFIDENCE candidates:
#       1. Capitalized proper-noun words from the raw text (Ahmedabad, Electronics)
#          — but NOT generic query-action words (Show, Compare, Top, etc.)
#       2. Underscore-pattern tokens from raw text (Customer_1273, Product_ABC)
#       3. Mixed-case bi-grams like "New York" (both words capitalized)
#       4. Lowercase non-structural words (for values like "female", "electronics")
    
#     Intentionally EXCLUDED:
#       - Pure structural/analytical terms (revenue, sales, total, etc.)
#       - Short tokens (< 3 chars)
#       - Pure numbers
 
#     This prevents queries like "Show revenue by all cities" from generating
#     spurious WHERE clauses for customer_name, city, and product_name.
#     """
#     # 1. Capitalized proper nouns — exclude generic query-action caps
#     capitalized = [
#         w for w in re.findall(r"\b[A-Z][a-zA-Z0-9\-]+\b", raw_text)
#         if w not in QUERY_ACTION_CAPS and len(w) >= 3
#     ]
 
#     # 2. Underscore tokens — IDs and coded identifiers
#     underscore_tokens = re.findall(r"\b[A-Za-z]\w*_\w+\b", raw_text)
 
#     # 3. Capitalized bi-grams (e.g. "New York", "South East")
#     words = raw_text.split()
#     cap_bigrams = [
#         f"{words[i]} {words[i+1]}"
#         for i in range(len(words) - 1)
#         if words[i][0].isupper() and words[i+1][0].isupper()
#         and words[i] not in QUERY_ACTION_CAPS
#         and words[i+1] not in QUERY_ACTION_CAPS
#     ]
 
#     # 4. Lowercase non-structural words — for filter values like "electronics", "city names"
#     cleaned_words = [re.sub(r'[^a-zA-Z0-9\-_]', '', w).lower() for w in words]
#     regular_words = [
#         w for w in cleaned_words
#         if len(w) >= 3 and not w.isdigit() and w not in QUERY_STRUCTURAL_TERMS
#     ]
 
#     # Combine and deduplicate, filtering short/numeric strings
#     candidates = list(set(
#         c for c in (capitalized + underscore_tokens + cap_bigrams + regular_words + [w.lower() for w in capitalized])
#         if len(c) >= 3 and not c.isdigit()
#     ))
 
#     if not candidates:
#         return []
 
#     # Always scan ALL workspace datasets to catch cross-table filter values
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()
#     if dataset_id_filter:
#         # Prefer the specified dataset but also scan others for cross-table joins
#         target = [d for d in datasets if d.id == dataset_id_filter]
#         others = [d for d in datasets if d.id != dataset_id_filter]
#         datasets = target + others
 
#     if not datasets:
#         return []
 
#     import difflib
#     seen_keys: set[tuple] = set()
#     filters_found: list[dict] = []
    
#     for ds in datasets:
#         profile = ds.profile_json or {}
#         nlp_index = profile.get("nlp_index", {})
#         # FIX: indexer stores as "value_dictionary" (lowercase underscore), not "Value Dictionary"
#         value_dict = nlp_index.get("value_dictionary") or nlp_index.get("Value Dictionary") or {}
        
#         for candidate in candidates:
#             c_lower = candidate.lower()
#             best_match = None
#             best_score = 0
#             best_cols = []
            
#             # Fuzzy match candidate against value dictionary keys
#             for val_key, cols in value_dict.items():
#                 if not isinstance(val_key, str):
#                     continue
#                 val_lower = val_key.lower()
#                 # Try rapidfuzz first for speed and accuracy; fall back to difflib
#                 try:
#                     from rapidfuzz import fuzz as rfuzz
#                     score = rfuzz.ratio(c_lower, val_lower) / 100.0
#                     score = max(score, rfuzz.partial_ratio(c_lower, val_lower) / 100.0)
#                 except ImportError:
#                     score = difflib.SequenceMatcher(None, c_lower, val_lower).ratio()
#                 # Boost substrings (exact word match within value)
#                 if val_lower.startswith(c_lower) or val_lower.endswith(c_lower) or c_lower in val_lower or val_lower in c_lower:
#                     score = max(score, 0.88)
#                 if score > best_score:
#                     best_score = score
#                     best_match = val_key
#                     best_cols = cols if isinstance(cols, list) else [cols]
            
#             # Lower threshold to 0.72 to catch fuzzy/typo inputs while avoiding false positives
#             # NOTE: this must stay INSIDE the `for candidate in candidates:` loop above —
#             # it used to be de-indented one level (into the `for ds in datasets:` loop),
#             # which meant only the LAST candidate processed for a dataset was ever matched
#             # or appended. That silently dropped every earlier filter value in a query
#             # (e.g. "Compare Ahmedabad and Surat" would only ever keep "Surat"), and could
#             # also leak a stale best_match/best_cols from one candidate onto another.
#             if best_score > 0.72 and best_match:
#                 for col in best_cols:
#                     result_key = (ds.id, ds.cleaned_table_name, col, best_match)
#                     if result_key not in seen_keys:
#                         seen_keys.add(result_key)
#                         filters_found.append({
#                             "dataset_id": ds.id,
#                             "table_name": ds.cleaned_table_name,
#                             "column": col,
#                             "value": best_match,
#                             "match_score": round(best_score, 3),
#                         })
#             else:
#                 # Index had no answer for this candidate on this dataset —
#                 # fall back to live DB values instead of giving up.
#                 engine = create_engine(settings.DATABASE_URL)
#                 try:
#                     for m in _live_categorical_fallback(engine, ds.cleaned_table_name, candidate):
#                         result_key = (ds.id, ds.cleaned_table_name, m["column"], m["value"])
#                         if result_key not in seen_keys:
#                             seen_keys.add(result_key)
#                             filters_found.append({
#                                 "dataset_id": ds.id,
#                                 "table_name": ds.cleaned_table_name,
#                                 "column": m["column"],
#                                 "value": m["value"],
#                                 "match_score": m["match_score"],
#                             })
#                 finally:
#                     engine.dispose()

    
        
                        
#     return filters_found
# # ------------------------------------------------------------------------------
# def _live_categorical_fallback(engine, table_name: str, candidate: str, threshold: float = 0.72) -> list[dict]:
#     from sqlalchemy import inspect as sa_inspect, text as sql_text
#     from rapidfuzz import fuzz as rfuzz

#     matches = []
#     try:
#         inspector = sa_inspect(engine)
#         columns_info = inspector.get_columns(table_name)
#     except Exception:
#         return matches

#     with engine.connect() as conn:
#         for col in columns_info:
#             type_str = str(col["type"]).upper()
#             if not any(t in type_str for t in ("CHAR", "TEXT", "VARCHAR")):
#                 continue
#             col_name = col["name"]

#             # ---- NEW: Boolean flag inference (fixes "smoker" issue) ----
#             if candidate.lower() == col_name.lower():
#                 try:
#                     bool_rows = conn.execute(
#                         sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 50')
#                     ).fetchall()
#                     bool_vals = {str(r[0]).lower() for r in bool_rows if r[0] is not None}
                    
#                     if 'yes' in bool_vals:
#                         matches.append({"column": col_name, "value": "yes", "match_score": 1.0})
#                         continue
#                     elif 'true' in bool_vals:
#                         matches.append({"column": col_name, "value": "true", "match_score": 1.0})
#                         continue
#                 except Exception:
#                     pass
#             # ------------------------------------------------------------

#             try:
#                 distinct_count = conn.execute(
#                     sql_text(f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"')
#                 ).scalar()
#                 if not distinct_count or distinct_count > 200:
#                     continue

#                 rows = conn.execute(
#                     sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 200')
#                 ).fetchall()
#             except Exception:
#                 continue

#             for (val,) in rows:
#                 if val is None:
#                     continue
#                 val_str = str(val)
#                 score = rfuzz.ratio(candidate.lower(), val_str.lower()) / 100.0
#                 score = max(score, rfuzz.partial_ratio(candidate.lower(), val_str.lower()) / 100.0)
#                 if val_str.lower() in candidate.lower() or candidate.lower() in val_str.lower():
#                     score = max(score, 0.88)
#                 if score > threshold:
#                     matches.append({"column": col_name, "value": val_str, "match_score": round(score, 3)})
#     return matches
 
 
# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------
 
# # def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
# #     """
# #     Scan numeric columns across datasets and score against query tokens.
# #     Uses fuzzy matching to improve column resolution.
# #     """
# #     engine = create_engine(settings.DATABASE_URL)
# #     candidates = []
    
# #     import difflib

# #     try:
# #         inspector = inspect(engine)
# #         for ds in datasets:
# #             try:
# #                 columns_info = inspector.get_columns(ds.cleaned_table_name)
# #             except Exception:
# #                 continue

# #             for col in columns_info:
# #                 col_name = col["name"]
# #                 type_str = str(col["type"]).upper()
# #                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
# #                     continue
# #                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
# #                     continue

# #                 col_words = col_name.lower().replace("_", " ").split()
# #                 score = 0
                
# #                 # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
# #                 for w in col_words:
# #                     for qt in tokens: 
# #                         fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
# #                         if fuzz > 0.8:
# #                             score += 2 * fuzz
                
# #                 # Semantic Aliases
# #                 for term in tokens:
# #                     term_lower = term.lower()
# #                     if term_lower in SEMANTIC_ALIASES:
# #                         for alias in SEMANTIC_ALIASES[term_lower]:
# #                             if alias in col_name.lower():
# #                                 score += 3

# #                 # Boost revenue/sales/amount columns as default metric
# #                 col_lower = col_name.lower()
# #                 if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
# #                     score += 1

# #                 if score > 0:
# #                     candidates.append({
# #                         "dataset_id": ds.id,
# #                         "dataset_name": ds.original_filename,
# #                         "table_name": ds.cleaned_table_name,
# #                         "column_name": col_name,
# #                         "score": score,
# #                     })
# #     finally:
# #         engine.dispose()
 
# #     if not candidates:
# #         return None
 
# #     candidates.sort(key=lambda c: c["score"], reverse=True)
# #     best = candidates[0]
 
# #     # # Determine aggregation from query wording
# #     # if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
# #     #     aggregation = "avg"
# #     # elif "how many" in cleaned_text or "count" in cleaned_text:
# #     #     aggregation = "count"
# #     # elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
# #     #     aggregation = "max"
# #     # elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
# #     #     aggregation = "min"
# #     # else:
# #     #     aggregation = "sum"
# #     # Determine aggregation from query wording inside _auto_match_metric
# #     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
# #         aggregation = "avg"
# #     # NEW: explicitly checking for "number" guarantees a count 
# #     elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
# #         aggregation = "count"
# #     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
# #         aggregation = "max"
# #     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
# #         aggregation = "min"
# #     else:
# #         aggregation = "sum"
 
# #     return {
# #         "dataset_id": best["dataset_id"],
# #         "table_name": best["table_name"],
# #         "column_name": best["column_name"],
# #         "aggregation": aggregation,
# #     }
# def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
#     """
#     Scan numeric columns across datasets and score against query tokens.
#     Uses fuzzy matching to improve column resolution.
#     """
#     engine = create_engine(settings.DATABASE_URL)
#     candidates = []
    
#     import difflib

#     try:
#         inspector = inspect(engine)
#         for ds in datasets:
#             try:
#                 columns_info = inspector.get_columns(ds.cleaned_table_name)
#             except Exception:
#                 continue

#             for col in columns_info:
#                 col_name = col["name"]
#                 type_str = str(col["type"]).upper()
#                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
#                     continue
#                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
#                     continue

#                 col_words = col_name.lower().replace("_", " ").split()
#                 score = 0
                
#                 # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
#                 for w in col_words:
#                     for qt in tokens: 
#                         fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
#                         if fuzz > 0.8:
#                             score += 2 * fuzz
                
#                 # Semantic Aliases
#                 for term in tokens:
#                     term_lower = term.lower()
#                     if term_lower in SEMANTIC_ALIASES:
#                         for alias in SEMANTIC_ALIASES[term_lower]:
#                             if alias in col_name.lower():
#                                 score += 3

#                 # FIX: Require score > 0 before boosting!
#                 # This prevents unrelated datasets from winning the auto-metric fallback.
#                 col_lower = col_name.lower()
#                 if score > 0 and any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
#                     score += 1

#                 # Append to candidates only if it matched the user's text
#                 if score > 0:
#                     candidates.append({
#                         "dataset_id": ds.id,
#                         "dataset_name": ds.original_filename,
#                         "table_name": ds.cleaned_table_name,
#                         "column_name": col_name,
#                         "score": score,
#                     })
#     finally:
#         engine.dispose()
 
#     if not candidates:
#         return None
 
#     candidates.sort(key=lambda c: c["score"], reverse=True)
#     best = candidates[0]
 
#     # Determine aggregation from query wording inside _auto_match_metric
#     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
#         aggregation = "avg"
#     elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
#         aggregation = "count"
#     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
#         aggregation = "max"
#     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
#         aggregation = "min"
#     else:
#         aggregation = "sum"
 
#     return {
#         "dataset_id": best["dataset_id"],
#         "table_name": best["table_name"],
#         "column_name": best["column_name"],
#         "aggregation": aggregation,
#     }
 
# def _is_text_column(sa_type) -> bool:
#     if sa_type is None:
#         return False
#     type_str = str(sa_type).upper()
#     return "CHAR" in type_str or "TEXT" in type_str


# def _is_date_column(sa_type) -> bool:
#     if sa_type is None:
#         return False
#     type_str = str(sa_type).upper()
#     return any(t in type_str for t in DATE_TYPE_HINTS)
 
 
# def _get_search_variants(candidate: str) -> list[str]:
#     """
#     Generate de-pluralized / stemmed variants so plural query words match
#     singular DB values: 'females' → ['females', 'female'].
#     """
#     variants = [candidate]
#     c = candidate.lower()
 
#     # Strip trailing 's' (females → female, orders → order)
#     if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
#         stem = candidate[:-1]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)
 
#     # Strip trailing 'es' (branches → branch, classes → class)
#     if c.endswith("es") and len(c) > 4:
#         stem = candidate[:-2]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)
 
#     return variants

# ==============================================================================
# ==============================================================================


# # import re
# # from sqlalchemy.orm import Session
# # from sqlalchemy import create_engine, text as sql_text, inspect
# # from app.models.knowledge_base import BusinessEntity, BusinessMetric
# # from app.models.dataset import Dataset
# # from app.core.config import settings

# # # ---------------------------------------------------------------------------
# # # Constants
# # # ---------------------------------------------------------------------------

# # ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
# # NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
# # DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]

# # SEMANTIC_ALIASES = {
# #     "revenue": ["revenue", "sales", "amount", "total_amount", "total_sales", "price"],
# #     "orders": ["order_id", "orders", "order_count", "transaction_id"],
# #     "customers": ["customer_id", "customer_name", "customer", "client", "user"],
# #     "profit": ["profit", "net_profit", "gross_profit", "margin"],
# #     "quantity": ["quantity", "qty", "count", "volume"],
# #     "stock": ["stock", "inventory", "quantity_available", "quantity_on_hand"],
# # }

# # # Words that are part of query structure / analytical intent — NEVER filter candidates.
# # # Prevents "all" → matching "Allahabad", "revenue" → matching product names, etc.
# # # NOTE: "city", "category", "customer", "product" removed from here since they
# # # are needed as GROUP BY hints. They stay in QUERY_ACTION_CAPS only.
# # QUERY_STRUCTURAL_TERMS: set[str] = {
# #     # Query action verbs
# #     "show", "display", "list", "find", "get", "fetch", "give", "tell",
# #     "what", "which", "how", "where", "when", "who", "why",
# #     # Aggregation & metric words
# #     "revenue", "sales", "profit", "income", "amount", "total", "sum", "count",
# #     "average", "avg", "mean", "maximum", "minimum", "number", "value",
# #     # Ranking
# #     "top", "bottom", "highest", "lowest", "best", "worst", "most", "least",
# #     # Time/trend
# #     "monthly", "yearly", "daily", "weekly", "annual", "quarterly",
# #     "month", "year", "day", "week", "quarter", "trend", "time",
# #     # Analytical structure
# #     "distribution", "comparison", "analysis", "breakdown", "growth",
# #     "above", "below", "greater", "less", "between", "never", "sold",
# #     # Quantifiers
# #     "all", "every", "each", "any", "some", "both", "few", "many",
# #     # Generic column-group hints (safe to exclude from filter search)
# #     "region", "regions", "segment", "segments",
# #     "state", "states", "country", "countries", "territory", "territories",
# #     "stock", "price", "discount", "quantity",
# #     # Generic filler
# #     "please", "need", "want", "give", "with", "their", "data",
# #     "report", "result", "results", "per", "using", "based",
# #     "purchase", "purchases", "compare", "versus", "generate", "create",
# #     "business", "insights", "dashboard", "trend", "sales",
# #     "order", "orders",
# # }

# # # Capitalized words that are query structure — not data values
# # QUERY_ACTION_CAPS: set[str] = {
# #     "Show", "Display", "List", "Find", "Get", "Fetch", "Give", "Tell",
# #     "What", "Which", "How", "Where", "When", "Who", "Why", "Compare",
# #     "Top", "Bottom", "Above", "Below", "Never", "All", "By", "Generate",
# #     "Create", "Build", "Their", "With",
# # }

# # # Irregular plural → singular mapping (for GROUP BY hint normalization)
# # IRREGULAR_PLURALS: dict[str, str] = {
# #     "cities": "city",
# #     "categories": "category",
# #     "countries": "country",
# #     "companies": "company",
# #     "territories": "territory",
# #     "subsidiaries": "subsidiary",
# #     "subcategories": "subcategory",
# #     "states": "state",
# #     "regions": "region",
# #     "segments": "segment",
# #     "quantities": "quantity",
# #     "customers": "customer",
# #     "products": "product",
# #     "orders": "order",
# # }

# # # Date period keywords for GROUP BY date_trunc detection
# # DATE_PERIOD_HINTS: dict[str, str] = {
# #     "month": "month", "monthly": "month",
# #     "year": "year", "yearly": "year", "annual": "year", "annually": "year",
# #     "day": "day", "daily": "day",
# #     "week": "week", "weekly": "week",
# #     "quarter": "quarter", "quarterly": "quarter",
# # }

# # # Column roles for GROUP BY resolution — maps query words to column name hints
# # COLUMN_ROLE_HINTS: dict[str, list[str]] = {
# #     "city": ["city", "ship_city", "billing_city", "location", "town"],
# #     "category": ["category", "product_category", "item_category", "type"],
# #     "product": ["product", "product_name", "item", "sku", "item_name"],
# #     "customer": ["customer", "customer_name", "client", "buyer", "name"],
# #     "region": ["region", "area", "zone"],
# #     "segment": ["segment", "group", "tier"],
# #     "state": ["state", "province"],
# #     "country": ["country", "nation"],
# #     "order": ["order_id", "order", "transaction"],
# # }


# # # ---------------------------------------------------------------------------
# # # Public extraction functions
# # # ---------------------------------------------------------------------------

# # def extract_entities_and_metrics(
# #     db: Session, workspace_id: int, tokens: list[str], cleaned_text: str,
# #     dataset_id_filter: int | None = None,
# # ) -> dict:
# #     """
# #     Match query tokens against registered BusinessMetric/BusinessEntity.
# #     Falls back to auto-detecting a numeric column from the dataset schema.
# #     """
# #     entities = db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()
# #     metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()
# #     datasets = db.query(Dataset).filter(
# #         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
# #     ).all()

# #     if dataset_id_filter:
# #         datasets = [d for d in datasets if d.id == dataset_id_filter]
# #         entities = [e for e in entities if e.dataset_id == dataset_id_filter]
# #         metrics = [m for m in metrics if m.dataset_id == dataset_id_filter]

# #     matched_entities = []
# #     for entity in entities:
# #         name_lower = entity.name.lower()
# #         if name_lower in cleaned_text or any(tok in name_lower for tok in tokens):
# #             matched_entities.append(entity)

# #     matched_metrics = []
# #     for metric in metrics:
# #         key_lower = metric.metric_key.lower()
# #         name_lower = metric.name.lower()
# #         if key_lower in cleaned_text or any(word in cleaned_text for word in name_lower.split()):
# #             matched_metrics.append(metric)

# #     matched_datasets = []
# #     if not matched_entities:
# #         for ds in datasets:
# #             stub = ds.original_filename.rsplit(".", 1)[0].lower()
# #             if stub in cleaned_text or stub.rstrip("s") in tokens:
# #                 matched_datasets.append(ds)

# #     auto_metric = None
# #     if not matched_metrics:
# #         auto_metric = _auto_match_metric(datasets, tokens, cleaned_text)

# #     return {
# #         "entities": [
# #             {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "identifier_column": e.identifier_column}
# #             for e in matched_entities
# #         ],
# #         "metrics": [
# #             {
# #                 "id": m.id, "name": m.name, "metric_key": m.metric_key,
# #                 "dataset_id": m.dataset_id, "column_name": m.column_name,
# #                 "aggregation": m.aggregation,
# #             }
# #             for m in matched_metrics
# #         ],
# #         "fallback_datasets": [
# #             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
# #             for d in matched_datasets
# #         ],
# #         "auto_metric": auto_metric,
# #         "candidate_datasets": [
# #             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
# #             for d in datasets
# #         ],
# #     }


# # def extract_group_by_hint(cleaned_text: str, tokens: list[str]) -> dict | None:
# #     """
# #     Detect GROUP BY intent from patterns like:
# #       'by cities', 'by category', 'per month', 'monthly revenue', 'yearly trend',
# #       'by customer', 'by product', etc.

# #     Returns one of:
# #       {"type": "date_trunc", "period": "month"}    — for date-based grouping
# #       {"type": "column",    "hint":  "city"}        — for column-based grouping
# #       None                                           — no group-by detected
# #     """
# #     # Check for time-based keywords anywhere in the query (monthly, yearly, etc.)
# #     for keyword, period in DATE_PERIOD_HINTS.items():
# #         if keyword in cleaned_text:
# #             return {"type": "date_trunc", "period": period}

# #     # Match explicit "by [WORD]" or "per [WORD]" pattern
# #     # Handles: "by all cities", "by category", "per region", "by customer"
# #     by_match = re.search(r"\b(?:by|per)\s+(?:all\s+|each\s+)?([\w]+)", cleaned_text)
# #     if by_match:
# #         by_word = by_match.group(1).lower()

# #         # Skip action words only — NOT column/dimension group words
# #         skip_words = {"revenue", "sales", "value", "amount", "top", "bottom", "their", "using"}
# #         if by_word not in skip_words:
# #             # Check for date period in the "by X" word
# #             if by_word in DATE_PERIOD_HINTS:
# #                 return {"type": "date_trunc", "period": DATE_PERIOD_HINTS[by_word]}

# #             # Normalize irregular plural to singular for column matching
# #             normalized = IRREGULAR_PLURALS.get(by_word, by_word)
# #             return {"type": "column", "hint": normalized}

# #     # Detect implicit GROUP BY from dimension words in the query without "by"
# #     # e.g. "Show revenue city" or "city revenue" or "category distribution"
# #     DIMENSION_WORDS = {
# #         "city": "city", "category": "category", "product": "product",
# #         "customer": "customer", "region": "region", "segment": "segment",
# #         "state": "state", "country": "country",
# #     }
# #     for word, hint in DIMENSION_WORDS.items():
# #         # Only if there's also a revenue/aggregation context
# #         if word in cleaned_text and any(agg in cleaned_text for agg in
# #                                          ["revenue", "sales", "amount", "total", "distribution",
# #                                           "breakdown", "comparison", "generate"]):
# #             return {"type": "column", "hint": hint}

# #     return None


# # def extract_numeric_threshold_filter(
# #     cleaned_text: str,
# #     table_name: str,
# #     dataset_id: int,
# # ) -> list[dict]:
# #     """
# #     Detect numeric threshold conditions like "stock below 20", "price above 100".
# #     Returns a list of filter dicts for the query spec.
# #     """
# #     # Pattern: <column_hint> <operator> <number>  OR  <operator> <number>
# #     patterns = [
# #         # "stock below 20" / "quantity less than 10"
# #         re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count)\b"
# #                    r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to)\s+"
# #                    r"(\d+(?:\.\d+)?)", re.I),
# #         # Reversed: "below 20 stock"
# #         re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
# #                    r"\s+(?:stock|items|units|products)", re.I),
# #     ]

# #     OPERATOR_MAP = {
# #         "below": "<", "under": "<", "less than": "<",
# #         "above": ">", "over": ">", "greater than": ">", "more than": ">",
# #         "equal to": "=",
# #     }

# #     found = []
# #     for pattern in patterns:
# #         match = pattern.search(cleaned_text)
# #         if match:
# #             groups = match.groups()
# #             col_hint = groups[0].lower() if len(groups) > 1 else "stock"
# #             value = float(groups[-1])
# #             # Determine operator from match text
# #             matched_str = match.group(0).lower()
# #             op = "<"  # default
# #             for op_word, op_sym in OPERATOR_MAP.items():
# #                 if op_word in matched_str:
# #                     op = op_sym
# #                     break
# #             found.append({
# #                 "column_hint": col_hint,
# #                 "op": op,
# #                 "value": value,
# #                 "dataset_id": dataset_id,
# #                 "table_name": table_name,
# #                 "is_numeric": True,
# #             })
# #             break  # Only one threshold per query for now

# #     return found


# # def extract_filter_values(
# #     db: Session, workspace_id: int, tokens: list[str], raw_text: str,
# #     dataset_id_filter: int | None = None,
# # ) -> list[dict]:
# #     """
# #     Detect specific filter values by matching candidates against actual DB values.

# #     CANDIDATE STRATEGY (critical for avoiding filter pollution):
# #     Only use HIGH-CONFIDENCE candidates:
# #       1. Capitalized proper-noun words from the raw text (Ahmedabad, Electronics)
# #          — but NOT generic query-action words (Show, Compare, Top, etc.)
# #       2. Underscore-pattern tokens from raw text (Customer_1273, Product_ABC)
# #       3. Mixed-case bi-grams like "New York" (both words capitalized)
# #       4. Lowercase non-structural words (for values like "female", "electronics")
    
# #     Intentionally EXCLUDED:
# #       - Pure structural/analytical terms (revenue, sales, total, etc.)
# #       - Short tokens (< 3 chars)
# #       - Pure numbers

# #     This prevents queries like "Show revenue by all cities" from generating
# #     spurious WHERE clauses for customer_name, city, and product_name.
# #     """
# #     # 1. Capitalized proper nouns — exclude generic query-action caps
# #     capitalized = [
# #         w for w in re.findall(r"\b[A-Z][a-zA-Z0-9\-]+\b", raw_text)
# #         if w not in QUERY_ACTION_CAPS and len(w) >= 3
# #     ]

# #     # 2. Underscore tokens — IDs and coded identifiers
# #     underscore_tokens = re.findall(r"\b[A-Za-z]\w*_\w+\b", raw_text)

# #     # 3. Capitalized bi-grams (e.g. "New York", "South East")
# #     words = raw_text.split()
# #     cap_bigrams = [
# #         f"{words[i]} {words[i+1]}"
# #         for i in range(len(words) - 1)
# #         if words[i][0].isupper() and words[i+1][0].isupper()
# #         and words[i] not in QUERY_ACTION_CAPS
# #         and words[i+1] not in QUERY_ACTION_CAPS
# #     ]

# #     # 4. Lowercase non-structural words — for filter values like "electronics", "city names"
# #     cleaned_words = [re.sub(r'[^a-zA-Z0-9\-_]', '', w).lower() for w in words]
# #     regular_words = [
# #         w for w in cleaned_words
# #         if len(w) >= 3 and not w.isdigit() and w not in QUERY_STRUCTURAL_TERMS
# #     ]

# #     # Combine and deduplicate, filtering short/numeric strings
# #     candidates = list(set(
# #         c for c in (capitalized + underscore_tokens + cap_bigrams + regular_words + [w.lower() for w in capitalized])
# #         if len(c) >= 3 and not c.isdigit()
# #     ))

# #     if not candidates:
# #         return []

# #     # Always scan ALL workspace datasets to catch cross-table filter values
# #     datasets = db.query(Dataset).filter(
# #         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
# #     ).all()
# #     if dataset_id_filter:
# #         # Prefer the specified dataset but also scan others for cross-table joins
# #         target = [d for d in datasets if d.id == dataset_id_filter]
# #         others = [d for d in datasets if d.id != dataset_id_filter]
# #         datasets = target + others

# #     if not datasets:
# #         return []

# #     engine = create_engine(settings.DATABASE_URL)
# #     seen_keys: set[tuple] = set()
# #     filters_found: list[dict] = []

# #     try:
# #         inspector = inspect(engine)
# #         with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
# #             for ds in datasets:
# #                 try:
# #                     columns_info = inspector.get_columns(ds.cleaned_table_name)
# #                 except Exception:
# #                     continue

# #                 text_cols = [c["name"] for c in columns_info if _is_text_column(c["type"])]
# #                 if not text_cols:
# #                     continue

# #                 for col in text_cols:
# #                     for candidate in candidates:
# #                         # Generate de-pluralized variants so "females" → tries
# #                         # "%females%", then "%female%" to find DB value "Female"
# #                         for variant in _get_search_variants(candidate):
# #                             dedup_key = (ds.id, ds.cleaned_table_name, col, variant.lower())
# #                             if dedup_key in seen_keys:
# #                                 break
# #                             try:
# #                                 row = conn.execute(
# #                                     sql_text(
# #                                         f'SELECT "{col}" FROM "{ds.cleaned_table_name}"'
# #                                         f' WHERE "{col}" ILIKE :val LIMIT 1'
# #                                     ),
# #                                     {"val": f"%{variant}%"},
# #                                 ).fetchone()
# #                             except Exception:
# #                                 continue
# #                             if row:
# #                                 exact_value = row[0]
# #                                 result_key = (ds.id, ds.cleaned_table_name, col, str(exact_value).lower())
# #                                 if result_key not in seen_keys:
# #                                     seen_keys.add(result_key)
# #                                     filters_found.append({
# #                                         "dataset_id": ds.id,
# #                                         "table_name": ds.cleaned_table_name,
# #                                         "column": col,
# #                                         "value": exact_value,   # Exact DB value, correct case
# #                                     })
# #                                 break  # Done with this candidate on this column
# #     finally:
# #         engine.dispose()

# #     return filters_found


# # # ---------------------------------------------------------------------------
# # # Private helpers
# # # ---------------------------------------------------------------------------

# # def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
# #     """
# #     Scan numeric columns across datasets and score against query tokens.
# #     Returns the best-matching column as an auto-detected metric.
# #     """
# #     engine = create_engine(settings.DATABASE_URL)
# #     candidates = []

# #     try:
# #         inspector = inspect(engine)
# #         for ds in datasets:
# #             try:
# #                 columns_info = inspector.get_columns(ds.cleaned_table_name)
# #             except Exception:
# #                 continue

# #             for col in columns_info:
# #                 col_name = col["name"]
# #                 type_str = str(col["type"]).upper()
# #                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
# #                     continue
# #                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
# #                     continue

# #                 col_words = col_name.lower().replace("_", " ").split()
# #                 score = 0
# #                 for w in col_words:
# #                     if w in cleaned_text:
# #                         score += 2
# #                     elif w in tokens:
# #                         score += 1

# #                 for term in tokens:
# #                     term_lower = term.lower()
# #                     if term_lower in SEMANTIC_ALIASES:
# #                         for alias in SEMANTIC_ALIASES[term_lower]:
# #                             if alias in col_name.lower():
# #                                 score += 3

# #                 # Boost revenue/sales/amount columns as default metric
# #                 col_lower = col_name.lower()
# #                 if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
# #                     score += 1

# #                 if score > 0:
# #                     candidates.append({
# #                         "dataset_id": ds.id,
# #                         "dataset_name": ds.original_filename,
# #                         "table_name": ds.cleaned_table_name,
# #                         "column_name": col_name,
# #                         "score": score,
# #                     })
# #     finally:
# #         engine.dispose()

# #     if not candidates:
# #         return None

# #     candidates.sort(key=lambda c: c["score"], reverse=True)
# #     best = candidates[0]

# #     # Determine aggregation from query wording
# #     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
# #         aggregation = "avg"
# #     elif "how many" in cleaned_text or "count" in cleaned_text:
# #         aggregation = "count"
# #     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
# #         aggregation = "max"
# #     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
# #         aggregation = "min"
# #     else:
# #         aggregation = "sum"

# #     return {
# #         "dataset_id": best["dataset_id"],
# #         "table_name": best["table_name"],
# #         "column_name": best["column_name"],
# #         "aggregation": aggregation,
# #     }


# # def _is_text_column(sa_type) -> bool:
# #     type_str = str(sa_type).upper()
# #     return "CHAR" in type_str or "TEXT" in type_str


# # def _is_date_column(sa_type) -> bool:
# #     type_str = str(sa_type).upper()
# #     return any(t in type_str for t in DATE_TYPE_HINTS)


# # def _get_search_variants(candidate: str) -> list[str]:
# #     """
# #     Generate de-pluralized / stemmed variants so plural query words match
# #     singular DB values: 'females' → ['females', 'female'].
# #     """
# #     variants = [candidate]
# #     c = candidate.lower()

# #     # Strip trailing 's' (females → female, orders → order)
# #     if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
# #         stem = candidate[:-1]
# #         if stem.lower() not in [v.lower() for v in variants]:
# #             variants.append(stem)

# #     # Strip trailing 'es' (branches → branch, classes → class)
# #     if c.endswith("es") and len(c) > 4:
# #         stem = candidate[:-2]
# #         if stem.lower() not in [v.lower() for v in variants]:
# #             variants.append(stem)

# #     return variants
# # -------------------------------------------------------------

# import re
# from sqlalchemy.orm import Session
# from sqlalchemy import create_engine, text as sql_text, inspect
# from app.models.knowledge_base import BusinessEntity, BusinessMetric
# from app.models.dataset import Dataset
# from app.core.config import settings
 
# # ---------------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------------
 
# ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
# NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
# DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]
 
# SEMANTIC_ALIASES = {
#     "revenue": ["revenue", "sales", "amount", "total_amount", "total_sales", "price"],
#     "orders": ["order_id", "orders", "order_count", "transaction_id"],
#     "customers": ["customer_id", "customer_name", "customer", "client", "user"],
#     "profit": ["profit", "net_profit", "gross_profit", "margin"],
#     "quantity": ["quantity", "qty", "count", "volume"],
#     "stock": ["stock", "inventory", "quantity_available", "quantity_on_hand"],
# }
 
# # Words that are part of query structure / analytical intent — NEVER filter candidates.
# # Prevents "all" → matching "Allahabad", "revenue" → matching product names, etc.
# # NOTE: "city", "category", "customer", "product" removed from here since they
# # are needed as GROUP BY hints. They stay in QUERY_ACTION_CAPS only.
# QUERY_STRUCTURAL_TERMS: set[str] = {
#     # Query action verbs
#     "show", "display", "list", "find", "get", "fetch", "give", "tell",
#     "what", "which", "how", "where", "when", "who", "why",
#     # Aggregation & metric words
#     "revenue", "sales", "profit", "income", "amount", "total", "sum", "count",
#     "average", "avg", "mean", "maximum", "minimum", "number", "value",
#     # Ranking
#     "top", "bottom", "highest", "lowest", "best", "worst", "most", "least",
#     # Time/trend
#     "monthly", "yearly", "daily", "weekly", "annual", "quarterly",
#     "month", "year", "day", "week", "quarter", "trend", "time",
#     # Analytical structure
#     "distribution", "comparison", "analysis", "breakdown", "growth",
#     "above", "below", "greater", "less", "between", "never", "sold",
#     # Quantifiers
#     "all", "every", "each", "any", "some", "both", "few", "many",
#     # Generic column-group hints (safe to exclude from filter search)
#     "region", "regions", "segment", "segments",
#     "state", "states", "country", "countries", "territory", "territories",
#     "stock", "price", "discount", "quantity",
#     # Generic filler
#     "please", "need", "want", "give", "with", "their", "data",
#     "report", "result", "results", "per", "using", "based",
#     "purchase", "purchases", "compare", "versus", "generate", "create",
#     "business", "insights", "dashboard", "trend", "sales",
#     "order", "orders",
# }
 
# # Capitalized words that are query structure — not data values
# QUERY_ACTION_CAPS: set[str] = {
#     "Show", "Display", "List", "Find", "Get", "Fetch", "Give", "Tell",
#     "What", "Which", "How", "Where", "When", "Who", "Why", "Compare",
#     "Top", "Bottom", "Above", "Below", "Never", "All", "By", "Generate",
#     "Create", "Build", "Their", "With",
# }
 
# # Irregular plural → singular mapping (for GROUP BY hint normalization)
# IRREGULAR_PLURALS: dict[str, str] = {
#     "cities": "city",
#     "categories": "category",
#     "countries": "country",
#     "companies": "company",
#     "territories": "territory",
#     "subsidiaries": "subsidiary",
#     "subcategories": "subcategory",
#     "states": "state",
#     "regions": "region",
#     "segments": "segment",
#     "quantities": "quantity",
#     "customers": "customer",
#     "products": "product",
#     "orders": "order",
# }
 
# # Date period keywords for GROUP BY date_trunc detection
# DATE_PERIOD_HINTS: dict[str, str] = {
#     "month": "month", "monthly": "month",
#     "year": "year", "yearly": "year", "annual": "year", "annually": "year",
#     "day": "day", "daily": "day",
#     "week": "week", "weekly": "week",
#     "quarter": "quarter", "quarterly": "quarter",
# }
 
# # Column roles for GROUP BY resolution — maps query words to column name hints
# COLUMN_ROLE_HINTS: dict[str, list[str]] = {
#     "city": ["city", "ship_city", "billing_city", "location", "town"],
#     "category": ["category", "product_category", "item_category", "type"],
#     "product": ["product", "product_name", "item", "sku", "item_name"],
#     "customer": ["customer", "customer_name", "client", "buyer", "name"],
#     "region": ["region", "area", "zone"],
#     "segment": ["segment", "group", "tier"],
#     "state": ["state", "province"],
#     "country": ["country", "nation"],
#     "order": ["order_id", "order", "transaction"],
# }
 
 
# # ---------------------------------------------------------------------------
# # Public extraction functions
# # ---------------------------------------------------------------------------
 
# def extract_entities_and_metrics(
#     db: Session, workspace_id: int, tokens: list[str], cleaned_text: str,
#     dataset_id_filter: int | None = None,
# ) -> dict:
#     """
#     Match query tokens against registered BusinessMetric/BusinessEntity.
#     Falls back to auto-detecting a numeric column from the dataset schema.
 
#     Also scores EVERY workspace dataset against the query (see
#     score_dataset_candidates) so downstream code can pick the best dataset
#     across the whole workspace instead of whichever metric/entity happened
#     to be matched first.
#     """
#     entities = db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()
#     metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()
 
#     if dataset_id_filter:
#         datasets = [d for d in datasets if d.id == dataset_id_filter]
#         entities = [e for e in entities if e.dataset_id == dataset_id_filter]
#         metrics = [m for m in metrics if m.dataset_id == dataset_id_filter]
 
#     matched_entities = []
#     for entity in entities:
#         name_lower = entity.name.lower()
#         if name_lower in cleaned_text or any(tok in name_lower for tok in tokens):
#             matched_entities.append(entity)
 
#     matched_metrics = []
#     for metric in metrics:
#         key_lower = metric.metric_key.lower()
#         name_lower = metric.name.lower()
        
#         if re.search(rf"\b{re.escape(key_lower)}\b", cleaned_text) or any(
#             re.search(rf"\b{re.escape(word)}\b", cleaned_text) for word in name_lower.split()
#         ):
#             matched_metrics.append(metric)
 
#     matched_datasets = []
#     if not matched_entities:
#         for ds in datasets:
#             stub = ds.original_filename.rsplit(".", 1)[0].lower()
#             if stub in cleaned_text or stub.rstrip("s") in tokens:
#                 matched_datasets.append(ds)
 
#     auto_metric = None
#     if not matched_metrics:
#         auto_metric = _auto_match_metric(datasets, tokens, cleaned_text)
 
#     # ------------------------------------------------------------------
#     # NEW: score every candidate dataset against the query so the caller
#     # can rank them instead of blindly taking metrics[0]/entities[0].
#     # ------------------------------------------------------------------
#     dataset_scores = score_dataset_candidates(
#         datasets=datasets,
#         tokens=tokens,
#         cleaned_text=cleaned_text,
#         matched_entities=matched_entities,
#         matched_metrics=matched_metrics,
#         matched_datasets=matched_datasets,
#     )
 
#     return {
#         "entities": [
#             {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "identifier_column": e.identifier_column}
#             for e in matched_entities
#         ],
#         "metrics": [
#             {
#                 "id": m.id, "name": m.name, "metric_key": m.metric_key,
#                 "dataset_id": m.dataset_id, "column_name": m.column_name,
#                 "aggregation": m.aggregation,
#             }
#             for m in matched_metrics
#         ],
#         "fallback_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in matched_datasets
#         ],
#         "auto_metric": auto_metric,
#         "candidate_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in datasets
#         ],
#         # Ranked list of every workspace dataset with a confidence score and
#         # human-readable reasons. Highest score first. Empty list == no
#         # datasets in workspace at all.
#         "dataset_scores": dataset_scores,
#     }
 
 
# # ---------------------------------------------------------------------------
# # Dataset scoring — replaces "first metric/entity/dataset found wins"
# # ---------------------------------------------------------------------------
 
# # Minimum score (out of the weights below) before we trust a dataset choice
# # without asking the user to confirm. Tune based on observed false-positive rate.
# DATASET_CONFIDENCE_THRESHOLD = 3

# # How much each kind of signal counts toward a dataset's score. Centralized
# # here so tuning doesn't require touching query_mapper.py.
# SCORE_WEIGHTS = {
#     "explicit_metric": 5,     # a registered BusinessMetric on this dataset matched query text
#     "explicit_entity": 5,     # a registered BusinessEntity on this dataset matched query text
#     "filename_match": 4,      # dataset filename/stub literally appears in the query
#     "filter_value_hit": 4,    # a value the user typed was actually found IN this dataset's data
#     "column_name_overlap": 1, # per query token that overlaps a column name in this dataset (capped)
#     "domain_keyword": 2,      # query mentions a domain-specific term suggesting this dataset
# }
# MAX_COLUMN_OVERLAP_SCORE = 3  # cap so a wide table doesn't win purely on column-name volume

# # Domain keyword signals per dataset filename pattern.
# # If the dataset filename contains any of the keys, and the query contains any of the
# # associated terms, boosted by `domain_keyword` weight.
# DOMAIN_KEYWORD_SIGNALS: dict[str, list[str]] = {
#     "insurance": ["insurance", "premium", "claim", "charges", "bmi", "smoker", "insured",
#                   "deductible", "coverage", "policy", "beneficiary"],
#     "order": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
#               "product", "sales", "revenue", "category", "sub-category"],
#     "sales": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
#               "product", "sales", "revenue", "category"],
#     "student": ["student", "score", "grade", "exam", "marks", "pass", "fail", "gpa"],
#     "employee": ["employee", "salary", "department", "hire", "position", "role", "payroll"],
#     "inventory": ["stock", "inventory", "warehouse", "sku", "reorder", "quantity"],
#     "medical": ["patient", "diagnosis", "hospital", "doctor", "treatment", "medication"],
# }
# MAX_DATASET_SCORE = (
#     SCORE_WEIGHTS["explicit_metric"]
#     + SCORE_WEIGHTS["explicit_entity"]
#     + SCORE_WEIGHTS["filename_match"]
#     + SCORE_WEIGHTS["filter_value_hit"]
#     + MAX_COLUMN_OVERLAP_SCORE * SCORE_WEIGHTS["column_name_overlap"]
#     + SCORE_WEIGHTS["domain_keyword"]
# )


# def _attach_dataset_confidence(dataset_scores: list[dict]) -> list[dict]:
#     """Normalize raw dataset match scores into a 0-100 confidence scale."""
#     for entry in dataset_scores:
#         entry["confidence"] = round(
#             min(100.0, (entry["score"] / MAX_DATASET_SCORE) * 100.0), 1
#         ) if MAX_DATASET_SCORE else 0.0
#     return dataset_scores
 
 
# def score_dataset_candidates(
#     datasets: list,
#     tokens: list[str],
#     cleaned_text: str,
#     matched_entities: list | None = None,
#     matched_metrics: list | None = None,
#     matched_datasets: list | None = None,
#     filter_hits: list[dict] | None = None,
# ) -> list[dict]:
#     """
#     Score every workspace dataset against the current query so the caller
#     can pick the best match instead of an arbitrary "first found" dataset.
 
#     Returns a list of dicts sorted by score (descending):
#         {
#             "dataset_id": int,
#             "table_name": str,
#             "name": str,
#             "score": int,
#             "reasons": list[str],   # human-readable, safe to show to the user
#         }
#     """
#     matched_entities = matched_entities or []
#     matched_metrics = matched_metrics or []
#     matched_datasets = matched_datasets or []
#     filter_hits = filter_hits or []
 
#     entity_ds_ids = {e.dataset_id for e in matched_entities}
#     metric_ds_ids = {m.dataset_id for m in matched_metrics}
#     filename_ds_ids = {d.id for d in matched_datasets}
#     filter_hit_ds_ids = {f["dataset_id"] for f in filter_hits if "dataset_id" in f}
 
#     # Open ONE engine/inspector for the whole scoring pass rather than one
#     # per dataset — this runs on every query, so it needs to stay cheap.
#     engine = create_engine(settings.DATABASE_URL)
#     try:
#         inspector = inspect(engine)
 
#         scored: list[dict] = []
#         for ds in datasets:
#             score = 0
#             reasons: list[str] = []
 
#             if ds.id in metric_ds_ids:
#                 score += SCORE_WEIGHTS["explicit_metric"]
#                 reasons.append("a business metric on this dataset matched the query")
 
#             if ds.id in entity_ds_ids:
#                 score += SCORE_WEIGHTS["explicit_entity"]
#                 reasons.append("a business entity on this dataset matched the query")
 
#             if ds.id in filename_ds_ids:
#                 score += SCORE_WEIGHTS["filename_match"]
#                 reasons.append(f"the dataset name '{ds.original_filename}' appears in the query")
 
#             if ds.id in filter_hit_ds_ids:
#                 score += SCORE_WEIGHTS["filter_value_hit"]
#                 reasons.append("a value mentioned in the query was found in this dataset's data")
 
#             # Column-name overlap — cheap signal that works even with zero
#             # registered metrics/entities (many workspaces won't have them set up).
#             try:
#                 col_names = [c["name"] for c in inspector.get_columns(ds.cleaned_table_name)]
#             except Exception:
#                 col_names = []
#             overlap = 0
#             import difflib
#             for col in col_names:
#                 col_words = col.lower().replace("_", " ").split()
#                 is_match = False
#                 for w in col_words:
#                     if w in tokens or w in cleaned_text:
#                         is_match = True
#                         break
#                     # Fuzzy match with tokens
#                     for t in tokens:
#                         if difflib.SequenceMatcher(None, w, t.lower()).ratio() > 0.8:
#                             is_match = True
#                             break
#                     if is_match:
#                         break
#                 if is_match:
#                     overlap += 1
                    
#             if overlap:
#                 col_score = min(overlap, MAX_COLUMN_OVERLAP_SCORE) * SCORE_WEIGHTS["column_name_overlap"]
#                 score += col_score
#                 reasons.append(f"{overlap} column name(s) relate to words in the query")
 
#             # Domain keyword signal: if the query uses domain-specific terms that
#             # match this dataset's domain, boost its score.
#             ds_name_lower = ds.original_filename.lower()
#             for domain_key, domain_terms in DOMAIN_KEYWORD_SIGNALS.items():
#                 if domain_key in ds_name_lower:
#                     matched_domain_terms = [t for t in domain_terms if t in cleaned_text]
#                     if matched_domain_terms:
#                         score += SCORE_WEIGHTS["domain_keyword"]
#                         reasons.append(f"domain terms {matched_domain_terms[:2]} matched dataset '{ds.original_filename}'")
#                     break

#             scored.append({
#                 "dataset_id": ds.id,
#                 "table_name": ds.cleaned_table_name,
#                 "name": ds.original_filename,
#                 "score": score,
#                 "reasons": reasons,
#             })
#     finally:
#         engine.dispose()

#     scored = _attach_dataset_confidence(scored)
#     scored.sort(key=lambda s: s["score"], reverse=True)
#     return scored


# def apply_filter_evidence_to_scores(dataset_scores: list[dict], filters: list[dict]) -> list[dict]:
#     """
#     Re-rank dataset scores once filter values are known.
 
#     Filters are resolved in a later pipeline stage than the initial entity/
#     metric scoring (forward_chaining.py runs preprocess -> intent ->
#     entities/metrics -> group_by -> filters, in that order), so this is
#     called from query_mapper.py right before the primary_table decision to
#     fold in "this literal value was actually found in dataset X's data" —
#     one of the strongest possible signals for which dataset the user means.
#     Returns a NEW sorted list; does not mutate the input.
#     """
#     if not filters:
#         return dataset_scores
 
#     hit_ds_ids: dict[int, int] = {}
#     for f in filters:
#         ds_id = f.get("dataset_id")
#         if ds_id is None:
#             continue
#         hit_ds_ids[ds_id] = hit_ds_ids.get(ds_id, 0) + 1
 
#     if not hit_ds_ids:
#         return dataset_scores
  
#     updated = []
#     for entry in dataset_scores:
#         new_entry = dict(entry)
#         hits = hit_ds_ids.get(entry["dataset_id"], 0)
#         if hits:
#             new_entry["score"] = entry["score"] + hits * SCORE_WEIGHTS["filter_value_hit"]
#             new_entry["reasons"] = entry["reasons"] + [
#                 f"{hits} value(s) from the query were found in this dataset's data"
#             ]
#         updated.append(new_entry)
  
#     updated = _attach_dataset_confidence(updated)
#     updated.sort(key=lambda s: s["score"], reverse=True)
#     return updated
 
 
# def extract_group_by_hint(cleaned_text: str, tokens: list[str]) -> dict | None:
#     """
#     Detect GROUP BY intent from patterns like:
#       'by cities', 'by category', 'per month', 'monthly revenue', 'yearly trend',
#       'by customer', 'by product', etc.
 
#     Returns one of:
#       {"type": "date_trunc", "period": "month"}    — for date-based grouping
#       {"type": "column",    "hints": ["city"]}     — for column-based grouping
#       None                                          — no group-by detected
#     """
#     # Check for time-based keywords anywhere in the query (monthly, yearly, etc.)
#     for keyword, period in DATE_PERIOD_HINTS.items():
#         if keyword in cleaned_text:
#             return {"type": "date_trunc", "period": period}
 
#     # Match ALL explicit "by [WORD]" or "per [WORD]" patterns — not just the first.
#     # This fixes queries like "bottom 3 cities by sales" where re.search() would
#     # find "by sales" first, skip it (sales is a skip word), and return None
#     # without ever seeing "cities". Now we try every match in order.
#     #
#     # skip_words includes metric words (sales, revenue, quantity…) so that
#     # "by quantity sold" or "by revenue" doesn't suppress detection of the actual
#     # dimension (product, city, etc.) elsewhere in the query.
#     skip_words = {
#         "revenue", "sales", "value", "amount", "total", "top", "bottom",
#         "their", "using", "quantity", "qty", "stock", "count", "price",
#         "cost", "rate", "profit", "income",
#     }
#     by_matches = re.findall(r"\b(?:by|per)\s+(?:all\s+|each\s+)?(\w+)", cleaned_text)
#     for by_word in by_matches:
#         by_word = by_word.lower()
#         if by_word in skip_words:
#             continue
#         # Check for date period in the "by X" word
#         if by_word in DATE_PERIOD_HINTS:
#             return {"type": "date_trunc", "period": DATE_PERIOD_HINTS[by_word]}
#         # Normalize irregular plural to singular for column matching
#         normalized = IRREGULAR_PLURALS.get(by_word, by_word)
#         return {"type": "column", "hints": [normalized]}
 
#     # Also check dimension words embedded in the query WITHOUT explicit "by/per".
#     # Handles: "Show revenue city", "city revenue", "category distribution",
#     # AND plural forms like "bottom 3 cities by sales" (where "by sales" was
#     # skipped above but "cities" → "city" can still be found here).
#     DIMENSION_WORDS = {
#         "city": "city", "cities": "city",
#         "category": "category", "categories": "category",
#         "product": "product", "products": "product",
#         "customer": "customer", "customers": "customer",
#         "region": "region", "regions": "region",
#         "segment": "segment", "segments": "segment",
#         "state": "state", "states": "state",
#         "country": "country", "countries": "country",
#     }
#     # Context signals that indicate we're in an aggregation/breakdown query.
#     AGG_CONTEXT = [
#         "revenue", "sales", "amount", "total", "distribution",
#         "breakdown", "comparison", "generate", "top", "bottom",
#         "average", "count", "how many",
#     ]
#     for word, hint in DIMENSION_WORDS.items():
#         # Only if there's also a revenue/aggregation context
#         if word in cleaned_text and any(agg in cleaned_text for agg in
#                                          ["revenue", "sales", "amount", "total", "distribution",
#                                           "breakdown", "comparison", "generate"]):
#             return {"type": "column", "hints": [hint]}
 
#     return None
 
 
# def extract_numeric_threshold_filter(
#     cleaned_text: str,
#     table_name: str,
#     dataset_id: int,
# ) -> list[dict]:
#     """
#     Detect numeric threshold conditions like "stock below 20", "price above 100".
#     Returns a list of filter dicts for the query spec.
#     """
#     # Pattern: <column_hint> <operator> <number>  OR  <operator> <number>
#     # patterns = [
#     #     # "stock below 20" / "quantity less than 10"
#     #     re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count)\b"
#     #                r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to)\s+"
#     #                r"(\d+(?:\.\d+)?)", re.I),
#     #     # Reversed: "below 20 stock"
#     #     re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
#     #                r"\s+(?:stock|items|units|products)", re.I),
#     # ]
#     patterns = [
#         # NEW: Made the operator block (?:...)? optional and added bmi/children fields
#         re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count|bmi|children)\b"
#                    r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to|=|>|<)?\s*"
#                    r"(\d+(?:\.\d+)?)", re.I),
#         re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
#                    r"\s+(?:stock|items|units|products|years|age)", re.I),
#     ]
 
#     OPERATOR_MAP = {
#         "below": "<", "under": "<", "less than": "<",
#         "above": ">", "over": ">", "greater than": ">", "more than": ">",
#         "equal to": "=",
#     }
 
#     # found = []
#     # for pattern in patterns:
#     #     match = pattern.search(cleaned_text)
#     #     if match:
#     #         groups = match.groups()
#     #         col_hint = groups[0].lower() if len(groups) > 1 else "stock"
#     #         value = float(groups[-1])
#     #         # Determine operator from match text
#     #         matched_str = match.group(0).lower()
#     #         op = "<"  # default
#     #         for op_word, op_sym in OPERATOR_MAP.items():
#     #             if op_word in matched_str:
#     #                 op = op_sym
#     #                 break
#     #         found.append({
#     #             "column_hint": col_hint,
#     #             "op": op,
#     #             "value": value,
#     #             "dataset_id": dataset_id,
#     #             "table_name": table_name,
#     #             "is_numeric": True,
#     #         })
#     #         break  # Only one threshold per query for now
 
#     # return found
#     found = []
#     for pattern in patterns:
#         for match in pattern.finditer(cleaned_text):  # NEW: using finditer to capture all
#             groups = match.groups()
#             col_hint = groups[0].lower() if len(groups) > 1 else "stock"
#             value = float(groups[-1])
#             matched_str = match.group(0).lower()
            
#             op = "="  # NEW: Default to equal for implicit ranges like "age 30"
#             for op_word, op_sym in OPERATOR_MAP.items():
#                 if re.search(rf"\b{re.escape(op_word)}\b", matched_str) or op_word in matched_str:
#                     op = op_sym
#                     break
                    
#             found.append({
#                 "column_hint": col_hint,
#                 "op": op,
#                 "value": value,
#                 "dataset_id": dataset_id,
#                 "table_name": table_name,
#                 "is_numeric": True,
#             })
#     return found
 
 
# def extract_filter_values(
#     db: Session, workspace_id: int, tokens: list[str], raw_text: str,
#     dataset_id_filter: int | None = None,
# ) -> list[dict]:
#     """
#     Detect specific filter values by matching candidates against actual DB values.
 
#     CANDIDATE STRATEGY (critical for avoiding filter pollution):
#     Only use HIGH-CONFIDENCE candidates:
#       1. Capitalized proper-noun words from the raw text (Ahmedabad, Electronics)
#          — but NOT generic query-action words (Show, Compare, Top, etc.)
#       2. Underscore-pattern tokens from raw text (Customer_1273, Product_ABC)
#       3. Mixed-case bi-grams like "New York" (both words capitalized)
#       4. Lowercase non-structural words (for values like "female", "electronics")
    
#     Intentionally EXCLUDED:
#       - Pure structural/analytical terms (revenue, sales, total, etc.)
#       - Short tokens (< 3 chars)
#       - Pure numbers
 
#     This prevents queries like "Show revenue by all cities" from generating
#     spurious WHERE clauses for customer_name, city, and product_name.
#     """
#     # 1. Capitalized proper nouns — exclude generic query-action caps
#     capitalized = [
#         w for w in re.findall(r"\b[A-Z][a-zA-Z0-9\-]+\b", raw_text)
#         if w not in QUERY_ACTION_CAPS and len(w) >= 3
#     ]
 
#     # 2. Underscore tokens — IDs and coded identifiers
#     underscore_tokens = re.findall(r"\b[A-Za-z]\w*_\w+\b", raw_text)
 
#     # 3. Capitalized bi-grams (e.g. "New York", "South East")
#     words = raw_text.split()
#     cap_bigrams = [
#         f"{words[i]} {words[i+1]}"
#         for i in range(len(words) - 1)
#         if words[i][0].isupper() and words[i+1][0].isupper()
#         and words[i] not in QUERY_ACTION_CAPS
#         and words[i+1] not in QUERY_ACTION_CAPS
#     ]
 
#     # 4. Lowercase non-structural words — for filter values like "electronics", "city names"
#     cleaned_words = [re.sub(r'[^a-zA-Z0-9\-_]', '', w).lower() for w in words]
#     regular_words = [
#         w for w in cleaned_words
#         if len(w) >= 3 and not w.isdigit() and w not in QUERY_STRUCTURAL_TERMS
#     ]
 
#     # Combine and deduplicate, filtering short/numeric strings
#     candidates = list(set(
#         c for c in (capitalized + underscore_tokens + cap_bigrams + regular_words + [w.lower() for w in capitalized])
#         if len(c) >= 3 and not c.isdigit()
#     ))
 
#     if not candidates:
#         return []
 
#     # Always scan ALL workspace datasets to catch cross-table filter values
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()
#     if dataset_id_filter:
#         # Prefer the specified dataset but also scan others for cross-table joins
#         target = [d for d in datasets if d.id == dataset_id_filter]
#         others = [d for d in datasets if d.id != dataset_id_filter]
#         datasets = target + others
 
#     if not datasets:
#         return []
 
#     import difflib
#     seen_keys: set[tuple] = set()
#     filters_found: list[dict] = []
    
#     for ds in datasets:
#         profile = ds.profile_json or {}
#         nlp_index = profile.get("nlp_index", {})
#         # FIX: indexer stores as "value_dictionary" (lowercase underscore), not "Value Dictionary"
#         value_dict = nlp_index.get("value_dictionary") or nlp_index.get("Value Dictionary") or {}
        
#         for candidate in candidates:
#             c_lower = candidate.lower()
#             best_match = None
#             best_score = 0
#             best_cols = []
            
#             # Fuzzy match candidate against value dictionary keys
#             for val_key, cols in value_dict.items():
#                 if not isinstance(val_key, str):
#                     continue
#                 val_lower = val_key.lower()
#                 # Try rapidfuzz first for speed and accuracy; fall back to difflib
#                 try:
#                     from rapidfuzz import fuzz as rfuzz
#                     score = rfuzz.ratio(c_lower, val_lower) / 100.0
#                     score = max(score, rfuzz.partial_ratio(c_lower, val_lower) / 100.0)
#                 except ImportError:
#                     score = difflib.SequenceMatcher(None, c_lower, val_lower).ratio()
#                 # Boost substrings (exact word match within value)
#                 if val_lower.startswith(c_lower) or val_lower.endswith(c_lower) or c_lower in val_lower or val_lower in c_lower:
#                     score = max(score, 0.88)
#                 if score > best_score:
#                     best_score = score
#                     best_match = val_key
#                     best_cols = cols if isinstance(cols, list) else [cols]
            
#             # # Lower threshold to 0.72 to catch fuzzy/typo inputs while avoiding false positives
#             # if best_score > 0.72 and best_match:
#             #     for col in best_cols:
#             #         result_key = (ds.id, ds.cleaned_table_name, col, best_match)
#             #         if result_key not in seen_keys:
#             #             seen_keys.add(result_key)
#             #             filters_found.append({
#             #                 "dataset_id": ds.id,
#             #                 "table_name": ds.cleaned_table_name,
#             #                 "column": col,
#             #                 "value": best_match,
#             #                 "match_score": round(best_score, 3),
#             #             })
#         # Lower threshold to 0.72 to catch fuzzy/typo inputs while avoiding false positives
#         if best_score > 0.72 and best_match:
#             for col in best_cols:
#                 result_key = (ds.id, ds.cleaned_table_name, col, best_match)
#                 if result_key not in seen_keys:
#                     seen_keys.add(result_key)
#                     filters_found.append({
#                         "dataset_id": ds.id,
#                         "table_name": ds.cleaned_table_name,
#                         "column": col,
#                         "value": best_match,
#                         "match_score": round(best_score, 3),
#                     })
#         else:
#             # Index had no answer for this candidate on this dataset —
#             # fall back to live DB values instead of giving up.
#             engine = create_engine(settings.DATABASE_URL)
#             try:
#                 for m in _live_categorical_fallback(engine, ds.cleaned_table_name, candidate):
#                     result_key = (ds.id, ds.cleaned_table_name, m["column"], m["value"])
#                     if result_key not in seen_keys:
#                         seen_keys.add(result_key)
#                         filters_found.append({
#                             "dataset_id": ds.id,
#                             "table_name": ds.cleaned_table_name,
#                             "column": m["column"],
#                             "value": m["value"],
#                             "match_score": m["match_score"],
#                         })
#             finally:
#                 engine.dispose()

    
        
                        
#     return filters_found
# # ------------------------------------------------------------------------------
# def _live_categorical_fallback(engine, table_name: str, candidate: str, threshold: float = 0.72) -> list[dict]:
#     from sqlalchemy import inspect as sa_inspect, text as sql_text
#     from rapidfuzz import fuzz as rfuzz

#     matches = []
#     try:
#         inspector = sa_inspect(engine)
#         columns_info = inspector.get_columns(table_name)
#     except Exception:
#         return matches

#     with engine.connect() as conn:
#         for col in columns_info:
#             type_str = str(col["type"]).upper()
#             if not any(t in type_str for t in ("CHAR", "TEXT", "VARCHAR")):
#                 continue
#             col_name = col["name"]

#             # ---- NEW: Boolean flag inference (fixes "smoker" issue) ----
#             if candidate.lower() == col_name.lower():
#                 try:
#                     bool_rows = conn.execute(
#                         sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 50')
#                     ).fetchall()
#                     bool_vals = {str(r[0]).lower() for r in bool_rows if r[0] is not None}
                    
#                     if 'yes' in bool_vals:
#                         matches.append({"column": col_name, "value": "yes", "match_score": 1.0})
#                         continue
#                     elif 'true' in bool_vals:
#                         matches.append({"column": col_name, "value": "true", "match_score": 1.0})
#                         continue
#                 except Exception:
#                     pass
#             # ------------------------------------------------------------

#             try:
#                 distinct_count = conn.execute(
#                     sql_text(f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"')
#                 ).scalar()
#                 if not distinct_count or distinct_count > 200:
#                     continue

#                 rows = conn.execute(
#                     sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 200')
#                 ).fetchall()
#             except Exception:
#                 continue

#             for (val,) in rows:
#                 if val is None:
#                     continue
#                 val_str = str(val)
#                 score = rfuzz.ratio(candidate.lower(), val_str.lower()) / 100.0
#                 score = max(score, rfuzz.partial_ratio(candidate.lower(), val_str.lower()) / 100.0)
#                 if val_str.lower() in candidate.lower() or candidate.lower() in val_str.lower():
#                     score = max(score, 0.88)
#                 if score > threshold:
#                     matches.append({"column": col_name, "value": val_str, "match_score": round(score, 3)})
#     return matches
 
 
# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------
 
# # def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
# #     """
# #     Scan numeric columns across datasets and score against query tokens.
# #     Uses fuzzy matching to improve column resolution.
# #     """
# #     engine = create_engine(settings.DATABASE_URL)
# #     candidates = []
    
# #     import difflib

# #     try:
# #         inspector = inspect(engine)
# #         for ds in datasets:
# #             try:
# #                 columns_info = inspector.get_columns(ds.cleaned_table_name)
# #             except Exception:
# #                 continue

# #             for col in columns_info:
# #                 col_name = col["name"]
# #                 type_str = str(col["type"]).upper()
# #                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
# #                     continue
# #                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
# #                     continue

# #                 col_words = col_name.lower().replace("_", " ").split()
# #                 score = 0
                
# #                 # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
# #                 for w in col_words:
# #                     for qt in tokens: 
# #                         fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
# #                         if fuzz > 0.8:
# #                             score += 2 * fuzz
                
# #                 # Semantic Aliases
# #                 for term in tokens:
# #                     term_lower = term.lower()
# #                     if term_lower in SEMANTIC_ALIASES:
# #                         for alias in SEMANTIC_ALIASES[term_lower]:
# #                             if alias in col_name.lower():
# #                                 score += 3

# #                 # Boost revenue/sales/amount columns as default metric
# #                 col_lower = col_name.lower()
# #                 if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
# #                     score += 1

# #                 if score > 0:
# #                     candidates.append({
# #                         "dataset_id": ds.id,
# #                         "dataset_name": ds.original_filename,
# #                         "table_name": ds.cleaned_table_name,
# #                         "column_name": col_name,
# #                         "score": score,
# #                     })
# #     finally:
# #         engine.dispose()
 
# #     if not candidates:
# #         return None
 
# #     candidates.sort(key=lambda c: c["score"], reverse=True)
# #     best = candidates[0]
 
# #     # # Determine aggregation from query wording
# #     # if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
# #     #     aggregation = "avg"
# #     # elif "how many" in cleaned_text or "count" in cleaned_text:
# #     #     aggregation = "count"
# #     # elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
# #     #     aggregation = "max"
# #     # elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
# #     #     aggregation = "min"
# #     # else:
# #     #     aggregation = "sum"
# #     # Determine aggregation from query wording inside _auto_match_metric
# #     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
# #         aggregation = "avg"
# #     # NEW: explicitly checking for "number" guarantees a count 
# #     elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
# #         aggregation = "count"
# #     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
# #         aggregation = "max"
# #     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
# #         aggregation = "min"
# #     else:
# #         aggregation = "sum"
 
# #     return {
# #         "dataset_id": best["dataset_id"],
# #         "table_name": best["table_name"],
# #         "column_name": best["column_name"],
# #         "aggregation": aggregation,
# #     }
# def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
#     """
#     Scan numeric columns across datasets and score against query tokens.
#     Uses fuzzy matching to improve column resolution.
#     """
#     engine = create_engine(settings.DATABASE_URL)
#     candidates = []
    
#     import difflib

#     try:
#         inspector = inspect(engine)
#         for ds in datasets:
#             try:
#                 columns_info = inspector.get_columns(ds.cleaned_table_name)
#             except Exception:
#                 continue

#             for col in columns_info:
#                 col_name = col["name"]
#                 type_str = str(col["type"]).upper()
#                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
#                     continue
#                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
#                     continue

#                 col_words = col_name.lower().replace("_", " ").split()
#                 score = 0
                
#                 # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
#                 for w in col_words:
#                     for qt in tokens: 
#                         fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
#                         if fuzz > 0.8:
#                             score += 2 * fuzz
                
#                 # Semantic Aliases
#                 for term in tokens:
#                     term_lower = term.lower()
#                     if term_lower in SEMANTIC_ALIASES:
#                         for alias in SEMANTIC_ALIASES[term_lower]:
#                             if alias in col_name.lower():
#                                 score += 3

#                 # FIX: Require score > 0 before boosting!
#                 # This prevents unrelated datasets from winning the auto-metric fallback.
#                 col_lower = col_name.lower()
#                 if score > 0 and any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
#                     score += 1

#                 # Append to candidates only if it matched the user's text
#                 if score > 0:
#                     candidates.append({
#                         "dataset_id": ds.id,
#                         "dataset_name": ds.original_filename,
#                         "table_name": ds.cleaned_table_name,
#                         "column_name": col_name,
#                         "score": score,
#                     })
#     finally:
#         engine.dispose()
 
#     if not candidates:
#         return None
 
#     candidates.sort(key=lambda c: c["score"], reverse=True)
#     best = candidates[0]
 
#     # Determine aggregation from query wording inside _auto_match_metric
#     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
#         aggregation = "avg"
#     elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
#         aggregation = "count"
#     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
#         aggregation = "max"
#     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
#         aggregation = "min"
#     else:
#         aggregation = "sum"
 
#     return {
#         "dataset_id": best["dataset_id"],
#         "table_name": best["table_name"],
#         "column_name": best["column_name"],
#         "aggregation": aggregation,
#     }
 
# def _is_text_column(sa_type) -> bool:
#     if sa_type is None:
#         return False
#     type_str = str(sa_type).upper()
#     return "CHAR" in type_str or "TEXT" in type_str


# def _is_date_column(sa_type) -> bool:
#     if sa_type is None:
#         return False
#     type_str = str(sa_type).upper()
#     return any(t in type_str for t in DATE_TYPE_HINTS)
 
 
# def _get_search_variants(candidate: str) -> list[str]:
#     """
#     Generate de-pluralized / stemmed variants so plural query words match
#     singular DB values: 'females' → ['females', 'female'].
#     """
#     variants = [candidate]
#     c = candidate.lower()
 
#     # Strip trailing 's' (females → female, orders → order)
#     if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
#         stem = candidate[:-1]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)
 
#     # Strip trailing 'es' (branches → branch, classes → class)
#     if c.endswith("es") and len(c) > 4:
#         stem = candidate[:-2]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)
 
#     return variants





# import re
# from sqlalchemy.orm import Session
# from sqlalchemy import create_engine, text as sql_text, inspect
# from app.models.knowledge_base import BusinessEntity, BusinessMetric
# from app.models.dataset import Dataset
# from app.core.config import settings

# # ---------------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------------

# ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
# NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
# DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]

# SEMANTIC_ALIASES = {
#     "revenue": ["revenue", "sales", "amount", "total_amount", "total_sales", "price"],
#     "orders": ["order_id", "orders", "order_count", "transaction_id"],
#     "customers": ["customer_id", "customer_name", "customer", "client", "user"],
#     "profit": ["profit", "net_profit", "gross_profit", "margin"],
#     "quantity": ["quantity", "qty", "count", "volume"],
#     "stock": ["stock", "inventory", "quantity_available", "quantity_on_hand"],
# }

# # Words that are part of query structure / analytical intent — NEVER filter candidates.
# # Prevents "all" → matching "Allahabad", "revenue" → matching product names, etc.
# # NOTE: "city", "category", "customer", "product" removed from here since they
# # are needed as GROUP BY hints. They stay in QUERY_ACTION_CAPS only.
# QUERY_STRUCTURAL_TERMS: set[str] = {
#     # Query action verbs
#     "show", "display", "list", "find", "get", "fetch", "give", "tell",
#     "what", "which", "how", "where", "when", "who", "why",
#     # Aggregation & metric words
#     "revenue", "sales", "profit", "income", "amount", "total", "sum", "count",
#     "average", "avg", "mean", "maximum", "minimum", "number", "value",
#     # Ranking
#     "top", "bottom", "highest", "lowest", "best", "worst", "most", "least",
#     # Time/trend
#     "monthly", "yearly", "daily", "weekly", "annual", "quarterly",
#     "month", "year", "day", "week", "quarter", "trend", "time",
#     # Analytical structure
#     "distribution", "comparison", "analysis", "breakdown", "growth",
#     "above", "below", "greater", "less", "between", "never", "sold",
#     # Quantifiers
#     "all", "every", "each", "any", "some", "both", "few", "many",
#     # Generic column-group hints (safe to exclude from filter search)
#     "region", "regions", "segment", "segments",
#     "state", "states", "country", "countries", "territory", "territories",
#     "stock", "price", "discount", "quantity",
#     # Generic filler
#     "please", "need", "want", "give", "with", "their", "data",
#     "report", "result", "results", "per", "using", "based",
#     "purchase", "purchases", "compare", "versus", "generate", "create",
#     "business", "insights", "dashboard", "trend", "sales",
#     "order", "orders",
# }

# # Capitalized words that are query structure — not data values
# QUERY_ACTION_CAPS: set[str] = {
#     "Show", "Display", "List", "Find", "Get", "Fetch", "Give", "Tell",
#     "What", "Which", "How", "Where", "When", "Who", "Why", "Compare",
#     "Top", "Bottom", "Above", "Below", "Never", "All", "By", "Generate",
#     "Create", "Build", "Their", "With",
# }

# # Irregular plural → singular mapping (for GROUP BY hint normalization)
# IRREGULAR_PLURALS: dict[str, str] = {
#     "cities": "city",
#     "categories": "category",
#     "countries": "country",
#     "companies": "company",
#     "territories": "territory",
#     "subsidiaries": "subsidiary",
#     "subcategories": "subcategory",
#     "states": "state",
#     "regions": "region",
#     "segments": "segment",
#     "quantities": "quantity",
#     "customers": "customer",
#     "products": "product",
#     "orders": "order",
# }

# # Date period keywords for GROUP BY date_trunc detection
# DATE_PERIOD_HINTS: dict[str, str] = {
#     "month": "month", "monthly": "month",
#     "year": "year", "yearly": "year", "annual": "year", "annually": "year",
#     "day": "day", "daily": "day",
#     "week": "week", "weekly": "week",
#     "quarter": "quarter", "quarterly": "quarter",
# }

# # Column roles for GROUP BY resolution — maps query words to column name hints
# COLUMN_ROLE_HINTS: dict[str, list[str]] = {
#     "city": ["city", "ship_city", "billing_city", "location", "town"],
#     "category": ["category", "product_category", "item_category", "type"],
#     "product": ["product", "product_name", "item", "sku", "item_name"],
#     "customer": ["customer", "customer_name", "client", "buyer", "name"],
#     "region": ["region", "area", "zone"],
#     "segment": ["segment", "group", "tier"],
#     "state": ["state", "province"],
#     "country": ["country", "nation"],
#     "order": ["order_id", "order", "transaction"],
# }


# # ---------------------------------------------------------------------------
# # Public extraction functions
# # ---------------------------------------------------------------------------

# def extract_entities_and_metrics(
#     db: Session, workspace_id: int, tokens: list[str], cleaned_text: str,
#     dataset_id_filter: int | None = None,
# ) -> dict:
#     """
#     Match query tokens against registered BusinessMetric/BusinessEntity.
#     Falls back to auto-detecting a numeric column from the dataset schema.
#     """
#     entities = db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()
#     metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()

#     if dataset_id_filter:
#         datasets = [d for d in datasets if d.id == dataset_id_filter]
#         entities = [e for e in entities if e.dataset_id == dataset_id_filter]
#         metrics = [m for m in metrics if m.dataset_id == dataset_id_filter]

#     matched_entities = []
#     for entity in entities:
#         name_lower = entity.name.lower()
#         if name_lower in cleaned_text or any(tok in name_lower for tok in tokens):
#             matched_entities.append(entity)

#     matched_metrics = []
#     for metric in metrics:
#         key_lower = metric.metric_key.lower()
#         name_lower = metric.name.lower()
#         if key_lower in cleaned_text or any(word in cleaned_text for word in name_lower.split()):
#             matched_metrics.append(metric)

#     matched_datasets = []
#     if not matched_entities:
#         for ds in datasets:
#             stub = ds.original_filename.rsplit(".", 1)[0].lower()
#             if stub in cleaned_text or stub.rstrip("s") in tokens:
#                 matched_datasets.append(ds)

#     auto_metric = None
#     if not matched_metrics:
#         auto_metric = _auto_match_metric(datasets, tokens, cleaned_text)

#     return {
#         "entities": [
#             {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "identifier_column": e.identifier_column}
#             for e in matched_entities
#         ],
#         "metrics": [
#             {
#                 "id": m.id, "name": m.name, "metric_key": m.metric_key,
#                 "dataset_id": m.dataset_id, "column_name": m.column_name,
#                 "aggregation": m.aggregation,
#             }
#             for m in matched_metrics
#         ],
#         "fallback_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in matched_datasets
#         ],
#         "auto_metric": auto_metric,
#         "candidate_datasets": [
#             {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
#             for d in datasets
#         ],
#     }


# def extract_group_by_hint(cleaned_text: str, tokens: list[str]) -> dict | None:
#     """
#     Detect GROUP BY intent from patterns like:
#       'by cities', 'by category', 'per month', 'monthly revenue', 'yearly trend',
#       'by customer', 'by product', etc.

#     Returns one of:
#       {"type": "date_trunc", "period": "month"}    — for date-based grouping
#       {"type": "column",    "hint":  "city"}        — for column-based grouping
#       None                                           — no group-by detected
#     """
#     # Check for time-based keywords anywhere in the query (monthly, yearly, etc.)
#     for keyword, period in DATE_PERIOD_HINTS.items():
#         if keyword in cleaned_text:
#             return {"type": "date_trunc", "period": period}

#     # Match explicit "by [WORD]" or "per [WORD]" pattern
#     # Handles: "by all cities", "by category", "per region", "by customer"
#     by_match = re.search(r"\b(?:by|per)\s+(?:all\s+|each\s+)?([\w]+)", cleaned_text)
#     if by_match:
#         by_word = by_match.group(1).lower()

#         # Skip action words only — NOT column/dimension group words
#         skip_words = {"revenue", "sales", "value", "amount", "top", "bottom", "their", "using"}
#         if by_word not in skip_words:
#             # Check for date period in the "by X" word
#             if by_word in DATE_PERIOD_HINTS:
#                 return {"type": "date_trunc", "period": DATE_PERIOD_HINTS[by_word]}

#             # Normalize irregular plural to singular for column matching
#             normalized = IRREGULAR_PLURALS.get(by_word, by_word)
#             return {"type": "column", "hint": normalized}

#     # Detect implicit GROUP BY from dimension words in the query without "by"
#     # e.g. "Show revenue city" or "city revenue" or "category distribution"
#     DIMENSION_WORDS = {
#         "city": "city", "category": "category", "product": "product",
#         "customer": "customer", "region": "region", "segment": "segment",
#         "state": "state", "country": "country",
#     }
#     for word, hint in DIMENSION_WORDS.items():
#         # Only if there's also a revenue/aggregation context
#         if word in cleaned_text and any(agg in cleaned_text for agg in
#                                          ["revenue", "sales", "amount", "total", "distribution",
#                                           "breakdown", "comparison", "generate"]):
#             return {"type": "column", "hint": hint}

#     return None


# def extract_numeric_threshold_filter(
#     cleaned_text: str,
#     table_name: str,
#     dataset_id: int,
# ) -> list[dict]:
#     """
#     Detect numeric threshold conditions like "stock below 20", "price above 100".
#     Returns a list of filter dicts for the query spec.
#     """
#     # Pattern: <column_hint> <operator> <number>  OR  <operator> <number>
#     patterns = [
#         # "stock below 20" / "quantity less than 10"
#         re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count)\b"
#                    r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to)\s+"
#                    r"(\d+(?:\.\d+)?)", re.I),
#         # Reversed: "below 20 stock"
#         re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
#                    r"\s+(?:stock|items|units|products)", re.I),
#     ]

#     OPERATOR_MAP = {
#         "below": "<", "under": "<", "less than": "<",
#         "above": ">", "over": ">", "greater than": ">", "more than": ">",
#         "equal to": "=",
#     }

#     found = []
#     for pattern in patterns:
#         match = pattern.search(cleaned_text)
#         if match:
#             groups = match.groups()
#             col_hint = groups[0].lower() if len(groups) > 1 else "stock"
#             value = float(groups[-1])
#             # Determine operator from match text
#             matched_str = match.group(0).lower()
#             op = "<"  # default
#             for op_word, op_sym in OPERATOR_MAP.items():
#                 if op_word in matched_str:
#                     op = op_sym
#                     break
#             found.append({
#                 "column_hint": col_hint,
#                 "op": op,
#                 "value": value,
#                 "dataset_id": dataset_id,
#                 "table_name": table_name,
#                 "is_numeric": True,
#             })
#             break  # Only one threshold per query for now

#     return found


# def extract_filter_values(
#     db: Session, workspace_id: int, tokens: list[str], raw_text: str,
#     dataset_id_filter: int | None = None,
# ) -> list[dict]:
#     """
#     Detect specific filter values by matching candidates against actual DB values.

#     CANDIDATE STRATEGY (critical for avoiding filter pollution):
#     Only use HIGH-CONFIDENCE candidates:
#       1. Capitalized proper-noun words from the raw text (Ahmedabad, Electronics)
#          — but NOT generic query-action words (Show, Compare, Top, etc.)
#       2. Underscore-pattern tokens from raw text (Customer_1273, Product_ABC)
#       3. Mixed-case bi-grams like "New York" (both words capitalized)
#       4. Lowercase non-structural words (for values like "female", "electronics")
    
#     Intentionally EXCLUDED:
#       - Pure structural/analytical terms (revenue, sales, total, etc.)
#       - Short tokens (< 3 chars)
#       - Pure numbers

#     This prevents queries like "Show revenue by all cities" from generating
#     spurious WHERE clauses for customer_name, city, and product_name.
#     """
#     # 1. Capitalized proper nouns — exclude generic query-action caps
#     capitalized = [
#         w for w in re.findall(r"\b[A-Z][a-zA-Z0-9\-]+\b", raw_text)
#         if w not in QUERY_ACTION_CAPS and len(w) >= 3
#     ]

#     # 2. Underscore tokens — IDs and coded identifiers
#     underscore_tokens = re.findall(r"\b[A-Za-z]\w*_\w+\b", raw_text)

#     # 3. Capitalized bi-grams (e.g. "New York", "South East")
#     words = raw_text.split()
#     cap_bigrams = [
#         f"{words[i]} {words[i+1]}"
#         for i in range(len(words) - 1)
#         if words[i][0].isupper() and words[i+1][0].isupper()
#         and words[i] not in QUERY_ACTION_CAPS
#         and words[i+1] not in QUERY_ACTION_CAPS
#     ]

#     # 4. Lowercase non-structural words — for filter values like "electronics", "city names"
#     cleaned_words = [re.sub(r'[^a-zA-Z0-9\-_]', '', w).lower() for w in words]
#     regular_words = [
#         w for w in cleaned_words
#         if len(w) >= 3 and not w.isdigit() and w not in QUERY_STRUCTURAL_TERMS
#     ]

#     # Combine and deduplicate, filtering short/numeric strings
#     candidates = list(set(
#         c for c in (capitalized + underscore_tokens + cap_bigrams + regular_words + [w.lower() for w in capitalized])
#         if len(c) >= 3 and not c.isdigit()
#     ))

#     if not candidates:
#         return []

#     # Always scan ALL workspace datasets to catch cross-table filter values
#     datasets = db.query(Dataset).filter(
#         Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
#     ).all()
#     if dataset_id_filter:
#         # Prefer the specified dataset but also scan others for cross-table joins
#         target = [d for d in datasets if d.id == dataset_id_filter]
#         others = [d for d in datasets if d.id != dataset_id_filter]
#         datasets = target + others

#     if not datasets:
#         return []

#     engine = create_engine(settings.DATABASE_URL)
#     seen_keys: set[tuple] = set()
#     filters_found: list[dict] = []

#     try:
#         inspector = inspect(engine)
#         with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
#             for ds in datasets:
#                 try:
#                     columns_info = inspector.get_columns(ds.cleaned_table_name)
#                 except Exception:
#                     continue

#                 text_cols = [c["name"] for c in columns_info if _is_text_column(c["type"])]
#                 if not text_cols:
#                     continue

#                 for col in text_cols:
#                     for candidate in candidates:
#                         # Generate de-pluralized variants so "females" → tries
#                         # "%females%", then "%female%" to find DB value "Female"
#                         for variant in _get_search_variants(candidate):
#                             dedup_key = (ds.id, ds.cleaned_table_name, col, variant.lower())
#                             if dedup_key in seen_keys:
#                                 break
#                             try:
#                                 row = conn.execute(
#                                     sql_text(
#                                         f'SELECT "{col}" FROM "{ds.cleaned_table_name}"'
#                                         f' WHERE "{col}" ILIKE :val LIMIT 1'
#                                     ),
#                                     {"val": f"%{variant}%"},
#                                 ).fetchone()
#                             except Exception:
#                                 continue
#                             if row:
#                                 exact_value = row[0]
#                                 result_key = (ds.id, ds.cleaned_table_name, col, str(exact_value).lower())
#                                 if result_key not in seen_keys:
#                                     seen_keys.add(result_key)
#                                     filters_found.append({
#                                         "dataset_id": ds.id,
#                                         "table_name": ds.cleaned_table_name,
#                                         "column": col,
#                                         "value": exact_value,   # Exact DB value, correct case
#                                     })
#                                 break  # Done with this candidate on this column
#     finally:
#         engine.dispose()

#     return filters_found


# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------

# def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
#     """
#     Scan numeric columns across datasets and score against query tokens.
#     Returns the best-matching column as an auto-detected metric.
#     """
#     engine = create_engine(settings.DATABASE_URL)
#     candidates = []

#     try:
#         inspector = inspect(engine)
#         for ds in datasets:
#             try:
#                 columns_info = inspector.get_columns(ds.cleaned_table_name)
#             except Exception:
#                 continue

#             for col in columns_info:
#                 col_name = col["name"]
#                 type_str = str(col["type"]).upper()
#                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
#                     continue
#                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
#                     continue

#                 col_words = col_name.lower().replace("_", " ").split()
#                 score = 0
#                 for w in col_words:
#                     if w in cleaned_text:
#                         score += 2
#                     elif w in tokens:
#                         score += 1

#                 for term in tokens:
#                     term_lower = term.lower()
#                     if term_lower in SEMANTIC_ALIASES:
#                         for alias in SEMANTIC_ALIASES[term_lower]:
#                             if alias in col_name.lower():
#                                 score += 3

#                 # Boost revenue/sales/amount columns as default metric
#                 col_lower = col_name.lower()
#                 if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
#                     score += 1

#                 if score > 0:
#                     candidates.append({
#                         "dataset_id": ds.id,
#                         "dataset_name": ds.original_filename,
#                         "table_name": ds.cleaned_table_name,
#                         "column_name": col_name,
#                         "score": score,
#                     })
#     finally:
#         engine.dispose()

#     if not candidates:
#         return None

#     candidates.sort(key=lambda c: c["score"], reverse=True)
#     best = candidates[0]

#     # Determine aggregation from query wording
#     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
#         aggregation = "avg"
#     elif "how many" in cleaned_text or "count" in cleaned_text:
#         aggregation = "count"
#     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
#         aggregation = "max"
#     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
#         aggregation = "min"
#     else:
#         aggregation = "sum"

#     return {
#         "dataset_id": best["dataset_id"],
#         "table_name": best["table_name"],
#         "column_name": best["column_name"],
#         "aggregation": aggregation,
#     }


# def _is_text_column(sa_type) -> bool:
#     type_str = str(sa_type).upper()
#     return "CHAR" in type_str or "TEXT" in type_str


# def _is_date_column(sa_type) -> bool:
#     type_str = str(sa_type).upper()
#     return any(t in type_str for t in DATE_TYPE_HINTS)


# def _get_search_variants(candidate: str) -> list[str]:
#     """
#     Generate de-pluralized / stemmed variants so plural query words match
#     singular DB values: 'females' → ['females', 'female'].
#     """
#     variants = [candidate]
#     c = candidate.lower()

#     # Strip trailing 's' (females → female, orders → order)
#     if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
#         stem = candidate[:-1]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)

#     # Strip trailing 'es' (branches → branch, classes → class)
#     if c.endswith("es") and len(c) > 4:
#         stem = candidate[:-2]
#         if stem.lower() not in [v.lower() for v in variants]:
#             variants.append(stem)

#     return variants
# -------------------------------------------------------------

import re
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text as sql_text, inspect
from app.models.knowledge_base import BusinessEntity, BusinessMetric
from app.models.dataset import Dataset
from app.core.config import settings
 
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
 
ID_LIKE_HINTS = ["id", "code", "zip", "postal", "index"]
NUMERIC_TYPE_HINTS = ["INT", "FLOAT", "NUMERIC", "DOUBLE", "REAL", "DECIMAL"]
DATE_TYPE_HINTS = ["DATE", "TIMESTAMP", "TIME"]
 
SEMANTIC_ALIASES = {
    "revenue": ["revenue", "sales", "amount", "total_amount", "total_sales", "price"],
    "orders": ["order_id", "orders", "order_count", "transaction_id"],
    "customers": ["customer_id", "customer_name", "customer", "client", "user"],
    "profit": ["profit", "net_profit", "gross_profit", "margin"],
    "quantity": ["quantity", "qty", "count", "volume"],
    "stock": ["stock", "inventory", "quantity_available", "quantity_on_hand"],
}
 
# Words that are part of query structure / analytical intent — NEVER filter candidates.
# Prevents "all" → matching "Allahabad", "revenue" → matching product names, etc.
# NOTE: "city", "category", "customer", "product" removed from here since they
# are needed as GROUP BY hints. They stay in QUERY_ACTION_CAPS only.
QUERY_STRUCTURAL_TERMS: set[str] = {
    # Query action verbs
    "show", "display", "list", "find", "get", "fetch", "give", "tell",
    "what", "which", "how", "where", "when", "who", "why",
    # Aggregation & metric words
    "revenue", "sales", "profit", "income", "amount", "total", "sum", "count",
    "average", "avg", "mean", "maximum", "minimum", "number", "value",
    # Ranking
    "top", "bottom", "highest", "lowest", "best", "worst", "most", "least",
    # Time/trend
    "monthly", "yearly", "daily", "weekly", "annual", "quarterly",
    "month", "year", "day", "week", "quarter", "trend", "time",
    # Analytical structure
    "distribution", "comparison", "analysis", "breakdown", "growth",
    "above", "below", "greater", "less", "between", "never", "sold",
    # Quantifiers
    "all", "every", "each", "any", "some", "both", "few", "many",
    # Generic column-group hints (safe to exclude from filter search)
    "region", "regions", "segment", "segments",
    "state", "states", "country", "countries", "territory", "territories",
    "stock", "price", "discount", "quantity",
    # Generic filler
    "please", "need", "want", "give", "with", "their", "data",
    "report", "result", "results", "per", "using", "based",
    "purchase", "purchases", "compare", "versus", "generate", "create",
    "business", "insights", "dashboard", "trend", "sales",
    "order", "orders",
}
 
# Capitalized words that are query structure — not data values
QUERY_ACTION_CAPS: set[str] = {
    "Show", "Display", "List", "Find", "Get", "Fetch", "Give", "Tell",
    "What", "Which", "How", "Where", "When", "Who", "Why", "Compare",
    "Top", "Bottom", "Above", "Below", "Never", "All", "By", "Generate",
    "Create", "Build", "Their", "With",
}
 
# Irregular plural → singular mapping (for GROUP BY hint normalization)
IRREGULAR_PLURALS: dict[str, str] = {
    "cities": "city",
    "categories": "category",
    "countries": "country",
    "companies": "company",
    "territories": "territory",
    "subsidiaries": "subsidiary",
    "subcategories": "subcategory",
    "states": "state",
    "regions": "region",
    "segments": "segment",
    "quantities": "quantity",
    "customers": "customer",
    "products": "product",
    "orders": "order",
}
 
# Date period keywords for GROUP BY date_trunc detection
DATE_PERIOD_HINTS: dict[str, str] = {
    "month": "month", "monthly": "month",
    "year": "year", "yearly": "year", "annual": "year", "annually": "year",
    "day": "day", "daily": "day",
    "week": "week", "weekly": "week",
    "quarter": "quarter", "quarterly": "quarter",
}
 
# Column roles for GROUP BY resolution — maps query words to column name hints
COLUMN_ROLE_HINTS: dict[str, list[str]] = {
    "city": ["city", "ship_city", "billing_city", "location", "town"],
    "category": ["category", "product_category", "item_category", "type"],
    "product": ["product", "product_name", "item", "sku", "item_name"],
    "customer": ["customer", "customer_name", "client", "buyer", "name"],
    "region": ["region", "area", "zone"],
    "segment": ["segment", "group", "tier"],
    "state": ["state", "province"],
    "country": ["country", "nation"],
    "order": ["order_id", "order", "transaction"],
}
 
 
# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------
 
def extract_entities_and_metrics(
    db: Session, workspace_id: int, tokens: list[str], cleaned_text: str,
    dataset_id_filter: int | None = None,
) -> dict:
    """
    Match query tokens against registered BusinessMetric/BusinessEntity.
    Falls back to auto-detecting a numeric column from the dataset schema.
 
    Also scores EVERY workspace dataset against the query (see
    score_dataset_candidates) so downstream code can pick the best dataset
    across the whole workspace instead of whichever metric/entity happened
    to be matched first.
    """
    entities = db.query(BusinessEntity).filter(BusinessEntity.workspace_id == workspace_id).all()
    metrics = db.query(BusinessMetric).filter(BusinessMetric.workspace_id == workspace_id).all()
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
    ).all()
 
    if dataset_id_filter:
        datasets = [d for d in datasets if d.id == dataset_id_filter]
        entities = [e for e in entities if e.dataset_id == dataset_id_filter]
        metrics = [m for m in metrics if m.dataset_id == dataset_id_filter]
 
    matched_entities = []
    for entity in entities:
        name_lower = entity.name.lower()
        if name_lower in cleaned_text or any(tok in name_lower for tok in tokens):
            matched_entities.append(entity)
 
    matched_metrics = []
    for metric in metrics:
        key_lower = metric.metric_key.lower()
        name_lower = metric.name.lower()
        
        if re.search(rf"\b{re.escape(key_lower)}\b", cleaned_text) or any(
            re.search(rf"\b{re.escape(word)}\b", cleaned_text) for word in name_lower.split()
        ):
            matched_metrics.append(metric)
 
    matched_datasets = []
    if not matched_entities:
        for ds in datasets:
            stub = ds.original_filename.rsplit(".", 1)[0].lower()
            if stub in cleaned_text or stub.rstrip("s") in tokens:
                matched_datasets.append(ds)
 
    auto_metric = None
    if not matched_metrics:
        auto_metric = _auto_match_metric(datasets, tokens, cleaned_text)
 
    # ------------------------------------------------------------------
    # NEW: score every candidate dataset against the query so the caller
    # can rank them instead of blindly taking metrics[0]/entities[0].
    # ------------------------------------------------------------------
    dataset_scores = score_dataset_candidates(
        datasets=datasets,
        tokens=tokens,
        cleaned_text=cleaned_text,
        matched_entities=matched_entities,
        matched_metrics=matched_metrics,
        matched_datasets=matched_datasets,
    )
 
    return {
        "entities": [
            {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "identifier_column": e.identifier_column}
            for e in matched_entities
        ],
        "metrics": [
            {
                "id": m.id, "name": m.name, "metric_key": m.metric_key,
                "dataset_id": m.dataset_id, "column_name": m.column_name,
                "aggregation": m.aggregation,
            }
            for m in matched_metrics
        ],
        "fallback_datasets": [
            {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
            for d in matched_datasets
        ],
        "auto_metric": auto_metric,
        "candidate_datasets": [
            {"id": d.id, "name": d.original_filename, "table_name": d.cleaned_table_name}
            for d in datasets
        ],
        # Ranked list of every workspace dataset with a confidence score and
        # human-readable reasons. Highest score first. Empty list == no
        # datasets in workspace at all.
        "dataset_scores": dataset_scores,
    }
 
 
# ---------------------------------------------------------------------------
# Dataset scoring — replaces "first metric/entity/dataset found wins"
# ---------------------------------------------------------------------------
 
# Minimum score (out of the weights below) before we trust a dataset choice
# without asking the user to confirm. Tune based on observed false-positive rate.
DATASET_CONFIDENCE_THRESHOLD = 3

# How much each kind of signal counts toward a dataset's score. Centralized
# here so tuning doesn't require touching query_mapper.py.
SCORE_WEIGHTS = {
    "explicit_metric": 5,     # a registered BusinessMetric on this dataset matched query text
    "explicit_entity": 5,     # a registered BusinessEntity on this dataset matched query text
    "filename_match": 4,      # dataset filename/stub literally appears in the query
    "filter_value_hit": 4,    # a value the user typed was actually found IN this dataset's data
    "column_name_overlap": 1, # per query token that overlaps a column name in this dataset (capped)
    "domain_keyword": 2,      # query mentions a domain-specific term suggesting this dataset
}
MAX_COLUMN_OVERLAP_SCORE = 3  # cap so a wide table doesn't win purely on column-name volume

# Domain keyword signals per dataset filename pattern.
# If the dataset filename contains any of the keys, and the query contains any of the
# associated terms, boosted by `domain_keyword` weight.
DOMAIN_KEYWORD_SIGNALS: dict[str, list[str]] = {
    "insurance": ["insurance", "premium", "claim", "charges", "bmi", "smoker", "insured",
                  "deductible", "coverage", "policy", "beneficiary"],
    "order": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
              "product", "sales", "revenue", "category", "sub-category"],
    "sales": ["order", "ship", "shipping", "profit", "discount", "quantity", "customer",
              "product", "sales", "revenue", "category"],
    "student": ["student", "score", "grade", "exam", "marks", "pass", "fail", "gpa"],
    "employee": ["employee", "salary", "department", "hire", "position", "role", "payroll"],
    "inventory": ["stock", "inventory", "warehouse", "sku", "reorder", "quantity"],
    "medical": ["patient", "diagnosis", "hospital", "doctor", "treatment", "medication"],
}
MAX_DATASET_SCORE = (
    SCORE_WEIGHTS["explicit_metric"]
    + SCORE_WEIGHTS["explicit_entity"]
    + SCORE_WEIGHTS["filename_match"]
    + SCORE_WEIGHTS["filter_value_hit"]
    + MAX_COLUMN_OVERLAP_SCORE * SCORE_WEIGHTS["column_name_overlap"]
    + SCORE_WEIGHTS["domain_keyword"]
)


def _attach_dataset_confidence(dataset_scores: list[dict]) -> list[dict]:
    """Normalize raw dataset match scores into a 0-100 confidence scale."""
    for entry in dataset_scores:
        entry["confidence"] = round(
            min(100.0, (entry["score"] / MAX_DATASET_SCORE) * 100.0), 1
        ) if MAX_DATASET_SCORE else 0.0
    return dataset_scores
 
 
def score_dataset_candidates(
    datasets: list,
    tokens: list[str],
    cleaned_text: str,
    matched_entities: list | None = None,
    matched_metrics: list | None = None,
    matched_datasets: list | None = None,
    filter_hits: list[dict] | None = None,
) -> list[dict]:
    """
    Score every workspace dataset against the current query so the caller
    can pick the best match instead of an arbitrary "first found" dataset.
 
    Returns a list of dicts sorted by score (descending):
        {
            "dataset_id": int,
            "table_name": str,
            "name": str,
            "score": int,
            "reasons": list[str],   # human-readable, safe to show to the user
        }
    """
    matched_entities = matched_entities or []
    matched_metrics = matched_metrics or []
    matched_datasets = matched_datasets or []
    filter_hits = filter_hits or []
 
    entity_ds_ids = {e.dataset_id for e in matched_entities}
    metric_ds_ids = {m.dataset_id for m in matched_metrics}
    filename_ds_ids = {d.id for d in matched_datasets}
    filter_hit_ds_ids = {f["dataset_id"] for f in filter_hits if "dataset_id" in f}
 
    # Open ONE engine/inspector for the whole scoring pass rather than one
    # per dataset — this runs on every query, so it needs to stay cheap.
    engine = create_engine(settings.DATABASE_URL)
    try:
        inspector = inspect(engine)
 
        scored: list[dict] = []
        for ds in datasets:
            score = 0
            reasons: list[str] = []
 
            if ds.id in metric_ds_ids:
                score += SCORE_WEIGHTS["explicit_metric"]
                reasons.append("a business metric on this dataset matched the query")
 
            if ds.id in entity_ds_ids:
                score += SCORE_WEIGHTS["explicit_entity"]
                reasons.append("a business entity on this dataset matched the query")
 
            if ds.id in filename_ds_ids:
                score += SCORE_WEIGHTS["filename_match"]
                reasons.append(f"the dataset name '{ds.original_filename}' appears in the query")
 
            if ds.id in filter_hit_ds_ids:
                score += SCORE_WEIGHTS["filter_value_hit"]
                reasons.append("a value mentioned in the query was found in this dataset's data")
 
            # Column-name overlap — cheap signal that works even with zero
            # registered metrics/entities (many workspaces won't have them set up).
            try:
                col_names = [c["name"] for c in inspector.get_columns(ds.cleaned_table_name)]
            except Exception:
                col_names = []
            overlap = 0
            import difflib
            for col in col_names:
                col_words = col.lower().replace("_", " ").split()
                is_match = False
                for w in col_words:
                    if w in tokens or w in cleaned_text:
                        is_match = True
                        break
                    # Fuzzy match with tokens
                    for t in tokens:
                        if difflib.SequenceMatcher(None, w, t.lower()).ratio() > 0.8:
                            is_match = True
                            break
                    if is_match:
                        break
                if is_match:
                    overlap += 1
                    
            if overlap:
                col_score = min(overlap, MAX_COLUMN_OVERLAP_SCORE) * SCORE_WEIGHTS["column_name_overlap"]
                score += col_score
                reasons.append(f"{overlap} column name(s) relate to words in the query")
 
            # Domain keyword signal: if the query uses domain-specific terms that
            # match this dataset's domain, boost its score.
            ds_name_lower = ds.original_filename.lower()
            for domain_key, domain_terms in DOMAIN_KEYWORD_SIGNALS.items():
                if domain_key in ds_name_lower:
                    matched_domain_terms = [t for t in domain_terms if t in cleaned_text]
                    if matched_domain_terms:
                        score += SCORE_WEIGHTS["domain_keyword"]
                        reasons.append(f"domain terms {matched_domain_terms[:2]} matched dataset '{ds.original_filename}'")
                    break

            scored.append({
                "dataset_id": ds.id,
                "table_name": ds.cleaned_table_name,
                "name": ds.original_filename,
                "score": score,
                "reasons": reasons,
            })
    finally:
        engine.dispose()

    scored = _attach_dataset_confidence(scored)
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored


def apply_filter_evidence_to_scores(dataset_scores: list[dict], filters: list[dict]) -> list[dict]:
    """
    Re-rank dataset scores once filter values are known.
 
    Filters are resolved in a later pipeline stage than the initial entity/
    metric scoring (forward_chaining.py runs preprocess -> intent ->
    entities/metrics -> group_by -> filters, in that order), so this is
    called from query_mapper.py right before the primary_table decision to
    fold in "this literal value was actually found in dataset X's data" —
    one of the strongest possible signals for which dataset the user means.
    Returns a NEW sorted list; does not mutate the input.
    """
    if not filters:
        return dataset_scores
 
    hit_ds_ids: dict[int, int] = {}
    for f in filters:
        ds_id = f.get("dataset_id")
        if ds_id is None:
            continue
        hit_ds_ids[ds_id] = hit_ds_ids.get(ds_id, 0) + 1
 
    if not hit_ds_ids:
        return dataset_scores
  
    updated = []
    for entry in dataset_scores:
        new_entry = dict(entry)
        hits = hit_ds_ids.get(entry["dataset_id"], 0)
        if hits:
            new_entry["score"] = entry["score"] + hits * SCORE_WEIGHTS["filter_value_hit"]
            new_entry["reasons"] = entry["reasons"] + [
                f"{hits} value(s) from the query were found in this dataset's data"
            ]
        updated.append(new_entry)
  
    updated = _attach_dataset_confidence(updated)
    updated.sort(key=lambda s: s["score"], reverse=True)
    return updated
 
 
def extract_group_by_hint(cleaned_text: str, tokens: list[str]) -> dict | None:
    """
    Detect GROUP BY intent from patterns like:
      'by cities', 'by category', 'per month', 'monthly revenue', 'yearly trend',
      'by customer', 'by product', etc.
 
    Returns one of:
      {"type": "date_trunc", "period": "month"}    — for date-based grouping
      {"type": "column",    "hints": ["city"]}     — for column-based grouping
      None                                          — no group-by detected
    """
    # Check for time-based keywords anywhere in the query (monthly, yearly, etc.)
    for keyword, period in DATE_PERIOD_HINTS.items():
        if keyword in cleaned_text:
            return {"type": "date_trunc", "period": period}
 
    # Match ALL explicit "by [WORD]" or "per [WORD]" patterns — not just the first.
    # This fixes queries like "bottom 3 cities by sales" where re.search() would
    # find "by sales" first, skip it (sales is a skip word), and return None
    # without ever seeing "cities". Now we try every match in order.
    #
    # skip_words includes metric words (sales, revenue, quantity…) so that
    # "by quantity sold" or "by revenue" doesn't suppress detection of the actual
    # dimension (product, city, etc.) elsewhere in the query.
    skip_words = {
        "revenue", "sales", "value", "amount", "total", "top", "bottom",
        "their", "using", "quantity", "qty", "stock", "count", "price",
        "cost", "rate", "profit", "income",
    }
    by_matches = re.findall(r"\b(?:by|per)\s+(?:all\s+|each\s+)?(\w+)", cleaned_text)
    for by_word in by_matches:
        by_word = by_word.lower()
        if by_word in skip_words:
            continue
        # Check for date period in the "by X" word
        if by_word in DATE_PERIOD_HINTS:
            return {"type": "date_trunc", "period": DATE_PERIOD_HINTS[by_word]}
        # Normalize irregular plural to singular for column matching
        normalized = IRREGULAR_PLURALS.get(by_word, by_word)
        return {"type": "column", "hints": [normalized]}
 
    # Also check dimension words embedded in the query WITHOUT explicit "by/per".
    # Handles: "Show revenue city", "city revenue", "category distribution",
    # AND plural forms like "bottom 3 cities by sales" (where "by sales" was
    # skipped above but "cities" → "city" can still be found here).
    DIMENSION_WORDS = {
        "city": "city", "cities": "city",
        "category": "category", "categories": "category",
        "product": "product", "products": "product",
        "customer": "customer", "customers": "customer",
        "region": "region", "regions": "region",
        "segment": "segment", "segments": "segment",
        "state": "state", "states": "state",
        "country": "country", "countries": "country",
    }
    # Context signals that indicate we're in an aggregation/breakdown query.
    AGG_CONTEXT = [
        "revenue", "sales", "amount", "total", "distribution",
        "breakdown", "comparison", "generate", "top", "bottom",
        "average", "count", "how many",
    ]
    for word, hint in DIMENSION_WORDS.items():
        # Only if there's also a revenue/aggregation context
        if word in cleaned_text and any(agg in cleaned_text for agg in
                                         ["revenue", "sales", "amount", "total", "distribution",
                                          "breakdown", "comparison", "generate"]):
            return {"type": "column", "hints": [hint]}
 
    return None
 
 
def extract_numeric_threshold_filter(
    cleaned_text: str,
    table_name: str,
    dataset_id: int,
) -> list[dict]:
    """
    Detect numeric threshold conditions like "stock below 20", "price above 100".
    Returns a list of filter dicts for the query spec.
    """
    # Pattern: <column_hint> <operator> <number>  OR  <operator> <number>
    # patterns = [
    #     # "stock below 20" / "quantity less than 10"
    #     re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count)\b"
    #                r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to)\s+"
    #                r"(\d+(?:\.\d+)?)", re.I),
    #     # Reversed: "below 20 stock"
    #     re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
    #                r"\s+(?:stock|items|units|products)", re.I),
    # ]
    patterns = [
        # NEW: Made the operator block (?:...)? optional and added bmi/children fields
        re.compile(r"\b(stock|quantity|qty|price|revenue|amount|sales|inventory|age|count|bmi|children)\b"
                   r"\s*(?:is\s+)?(?:below|under|less than|greater than|above|over|more than|equal to|=|>|<)?\s*"
                   r"(\d+(?:\.\d+)?)", re.I),
        re.compile(r"\b(?:below|under|less than|greater than|above|over|more than)\s+(\d+(?:\.\d+)?)"
                   r"\s+(?:stock|items|units|products|years|age)", re.I),
    ]
 
    OPERATOR_MAP = {
        "below": "<", "under": "<", "less than": "<",
        "above": ">", "over": ">", "greater than": ">", "more than": ">",
        "equal to": "=",
    }
 
    # found = []
    # for pattern in patterns:
    #     match = pattern.search(cleaned_text)
    #     if match:
    #         groups = match.groups()
    #         col_hint = groups[0].lower() if len(groups) > 1 else "stock"
    #         value = float(groups[-1])
    #         # Determine operator from match text
    #         matched_str = match.group(0).lower()
    #         op = "<"  # default
    #         for op_word, op_sym in OPERATOR_MAP.items():
    #             if op_word in matched_str:
    #                 op = op_sym
    #                 break
    #         found.append({
    #             "column_hint": col_hint,
    #             "op": op,
    #             "value": value,
    #             "dataset_id": dataset_id,
    #             "table_name": table_name,
    #             "is_numeric": True,
    #         })
    #         break  # Only one threshold per query for now
 
    # return found
    found = []
    for pattern in patterns:
        for match in pattern.finditer(cleaned_text):  # NEW: using finditer to capture all
            groups = match.groups()
            col_hint = groups[0].lower() if len(groups) > 1 else "stock"
            value = float(groups[-1])
            matched_str = match.group(0).lower()
            
            op = "="  # NEW: Default to equal for implicit ranges like "age 30"
            for op_word, op_sym in OPERATOR_MAP.items():
                if re.search(rf"\b{re.escape(op_word)}\b", matched_str) or op_word in matched_str:
                    op = op_sym
                    break
                    
            found.append({
                "column_hint": col_hint,
                "op": op,
                "value": value,
                "dataset_id": dataset_id,
                "table_name": table_name,
                "is_numeric": True,
            })
    return found
 
 
def extract_filter_values(
    db: Session, workspace_id: int, tokens: list[str], raw_text: str,
    dataset_id_filter: int | None = None,
) -> list[dict]:
    """
    Detect specific filter values by matching candidates against actual DB values.
 
    CANDIDATE STRATEGY (critical for avoiding filter pollution):
    Only use HIGH-CONFIDENCE candidates:
      1. Capitalized proper-noun words from the raw text (Ahmedabad, Electronics)
         — but NOT generic query-action words (Show, Compare, Top, etc.)
      2. Underscore-pattern tokens from raw text (Customer_1273, Product_ABC)
      3. Mixed-case bi-grams like "New York" (both words capitalized)
      4. Lowercase non-structural words (for values like "female", "electronics")
    
    Intentionally EXCLUDED:
      - Pure structural/analytical terms (revenue, sales, total, etc.)
      - Short tokens (< 3 chars)
      - Pure numbers
 
    This prevents queries like "Show revenue by all cities" from generating
    spurious WHERE clauses for customer_name, city, and product_name.
    """
    # Common English function words. These were previously NOT excluded from
    # candidate generation at all (QUERY_STRUCTURAL_TERMS only covers BI/query
    # vocabulary like "total"/"revenue", not ordinary conjunctions/prepositions).
    # A short word like "and" easily clears the 0.72 fuzzy threshold against
    # unrelated proper nouns that happen to share letters/suffixes (e.g. "and"
    # vs "ahmedabad" AND "hyderabad" both scoring high via rapidfuzz's
    # partial_ratio, since it looks for the best-aligned substring rather than
    # judging overall word similarity) — silently adding a third, unrequested
    # city to what should have been a clean two-way comparison.
    GENERIC_STOPWORDS = {
        "and", "or", "the", "of", "in", "on", "at", "to", "a", "an", "is",
        "are", "was", "were", "for", "from", "as", "this", "that", "these",
        "those", "it", "its", "be", "been", "being", "vs", "not", "but",
    }

    # 1. Capitalized proper nouns — exclude generic query-action caps.
    # ALSO exclude QUERY_STRUCTURAL_TERMS/stopwords case-insensitively: a
    # word like "Total" or "Average" starting a sentence is capitalized for
    # grammatical reasons only, not because it's a proper noun, but this
    # list previously only checked QUERY_ACTION_CAPS (a much smaller,
    # capitalized-only list) — so it slipped through as a filter-value
    # candidate even though its lowercase form is deliberately excluded
    # a few lines below.
    capitalized = [
        w for w in re.findall(r"\b[A-Z][a-zA-Z0-9\-]+\b", raw_text)
        if w not in QUERY_ACTION_CAPS
        and w.lower() not in QUERY_STRUCTURAL_TERMS
        and w.lower() not in GENERIC_STOPWORDS
        and len(w) >= 3
    ]
 
    # 2. Underscore tokens — IDs and coded identifiers
    underscore_tokens = re.findall(r"\b[A-Za-z]\w*_\w+\b", raw_text)
 
    # 3. Capitalized bi-grams (e.g. "New York", "South East")
    words = raw_text.split()
    cap_bigrams = [
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i][0].isupper() and words[i+1][0].isupper()
        and words[i] not in QUERY_ACTION_CAPS
        and words[i+1] not in QUERY_ACTION_CAPS
    ]
 
    # 4. Lowercase non-structural words — for filter values like "electronics", "city names"
    cleaned_words = [re.sub(r'[^a-zA-Z0-9\-_]', '', w).lower() for w in words]
    regular_words = [
        w for w in cleaned_words
        if len(w) >= 3 and not w.isdigit()
        and w not in QUERY_STRUCTURAL_TERMS
        and w not in GENERIC_STOPWORDS
    ]
 
    # Combine and deduplicate, filtering short/numeric strings
    candidates = list(set(
        c for c in (capitalized + underscore_tokens + cap_bigrams + regular_words + [w.lower() for w in capitalized])
        if len(c) >= 3 and not c.isdigit()
    ))
 
    if not candidates:
        return []
 
    # Always scan ALL workspace datasets to catch cross-table filter values
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id, Dataset.is_processed == 1
    ).all()
    if dataset_id_filter:
        # Prefer the specified dataset but also scan others for cross-table joins
        target = [d for d in datasets if d.id == dataset_id_filter]
        others = [d for d in datasets if d.id != dataset_id_filter]
        datasets = target + others
 
    if not datasets:
        return []
 
    import difflib
    seen_keys: set[tuple] = set()
    filters_found: list[dict] = []
    
    for ds in datasets:
        profile = ds.profile_json or {}
        nlp_index = profile.get("nlp_index", {})
        # FIX: indexer stores as "value_dictionary" (lowercase underscore), not "Value Dictionary"
        value_dict = nlp_index.get("value_dictionary") or nlp_index.get("Value Dictionary") or {}
        
        for candidate in candidates:
            c_lower = candidate.lower()
            best_match = None
            best_score = 0
            best_cols = []
            
            # Fuzzy match candidate against value dictionary keys
            for val_key, cols in value_dict.items():
                if not isinstance(val_key, str):
                    continue
                val_lower = val_key.lower()
                # Try rapidfuzz first for speed and accuracy; fall back to difflib
                try:
                    from rapidfuzz import fuzz as rfuzz
                    score = rfuzz.ratio(c_lower, val_lower) / 100.0
                    score = max(score, rfuzz.partial_ratio(c_lower, val_lower) / 100.0)
                except ImportError:
                    score = difflib.SequenceMatcher(None, c_lower, val_lower).ratio()
                # Boost substrings (exact word match within value)
                if val_lower.startswith(c_lower) or val_lower.endswith(c_lower) or c_lower in val_lower or val_lower in c_lower:
                    score = max(score, 0.88)
                if score > best_score:
                    best_score = score
                    best_match = val_key
                    best_cols = cols if isinstance(cols, list) else [cols]
            
            # Lower threshold to 0.72 to catch fuzzy/typo inputs while avoiding false positives
            # NOTE: this must stay INSIDE the `for candidate in candidates:` loop above —
            # it used to be de-indented one level (into the `for ds in datasets:` loop),
            # which meant only the LAST candidate processed for a dataset was ever matched
            # or appended. That silently dropped every earlier filter value in a query
            # (e.g. "Compare Ahmedabad and Surat" would only ever keep "Surat"), and could
            # also leak a stale best_match/best_cols from one candidate onto another.
            if best_score > 0.72 and best_match:
                for col in best_cols:
                    result_key = (ds.id, ds.cleaned_table_name, col, best_match)
                    if result_key not in seen_keys:
                        seen_keys.add(result_key)
                        filters_found.append({
                            "dataset_id": ds.id,
                            "table_name": ds.cleaned_table_name,
                            "column": col,
                            "value": best_match,
                            "match_score": round(best_score, 3),
                        })
            else:
                # Index had no answer for this candidate on this dataset —
                # fall back to live DB values instead of giving up.
                engine = create_engine(settings.DATABASE_URL)
                try:
                    for m in _live_categorical_fallback(engine, ds.cleaned_table_name, candidate):
                        result_key = (ds.id, ds.cleaned_table_name, m["column"], m["value"])
                        if result_key not in seen_keys:
                            seen_keys.add(result_key)
                            filters_found.append({
                                "dataset_id": ds.id,
                                "table_name": ds.cleaned_table_name,
                                "column": m["column"],
                                "value": m["value"],
                                "match_score": m["match_score"],
                            })
                finally:
                    engine.dispose()

    
        
                        
    return filters_found
# ------------------------------------------------------------------------------
def _live_categorical_fallback(engine, table_name: str, candidate: str, threshold: float = 0.72) -> list[dict]:
    from sqlalchemy import inspect as sa_inspect, text as sql_text
    from rapidfuzz import fuzz as rfuzz

    matches = []
    try:
        inspector = sa_inspect(engine)
        columns_info = inspector.get_columns(table_name)
    except Exception:
        return matches

    with engine.connect() as conn:
        for col in columns_info:
            type_str = str(col["type"]).upper()
            if not any(t in type_str for t in ("CHAR", "TEXT", "VARCHAR")):
                continue
            col_name = col["name"]

            # ---- NEW: Boolean flag inference (fixes "smoker" issue) ----
            if candidate.lower() == col_name.lower():
                try:
                    bool_rows = conn.execute(
                        sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 50')
                    ).fetchall()
                    bool_vals = {str(r[0]).lower() for r in bool_rows if r[0] is not None}
                    
                    if 'yes' in bool_vals:
                        matches.append({"column": col_name, "value": "yes", "match_score": 1.0})
                        continue
                    elif 'true' in bool_vals:
                        matches.append({"column": col_name, "value": "true", "match_score": 1.0})
                        continue
                except Exception:
                    pass
            # ------------------------------------------------------------

            try:
                distinct_count = conn.execute(
                    sql_text(f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"')
                ).scalar()
                if not distinct_count or distinct_count > 200:
                    continue

                rows = conn.execute(
                    sql_text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" LIMIT 200')
                ).fetchall()
            except Exception:
                continue

            for (val,) in rows:
                if val is None:
                    continue
                val_str = str(val)
                score = rfuzz.ratio(candidate.lower(), val_str.lower()) / 100.0
                score = max(score, rfuzz.partial_ratio(candidate.lower(), val_str.lower()) / 100.0)
                if val_str.lower() in candidate.lower() or candidate.lower() in val_str.lower():
                    score = max(score, 0.88)
                if score > threshold:
                    matches.append({"column": col_name, "value": val_str, "match_score": round(score, 3)})
    return matches
 
 
# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
 
# def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
#     """
#     Scan numeric columns across datasets and score against query tokens.
#     Uses fuzzy matching to improve column resolution.
#     """
#     engine = create_engine(settings.DATABASE_URL)
#     candidates = []
    
#     import difflib

#     try:
#         inspector = inspect(engine)
#         for ds in datasets:
#             try:
#                 columns_info = inspector.get_columns(ds.cleaned_table_name)
#             except Exception:
#                 continue

#             for col in columns_info:
#                 col_name = col["name"]
#                 type_str = str(col["type"]).upper()
#                 if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
#                     continue
#                 if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
#                     continue

#                 col_words = col_name.lower().replace("_", " ").split()
#                 score = 0
                
#                 # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
#                 for w in col_words:
#                     for qt in tokens: 
#                         fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
#                         if fuzz > 0.8:
#                             score += 2 * fuzz
                
#                 # Semantic Aliases
#                 for term in tokens:
#                     term_lower = term.lower()
#                     if term_lower in SEMANTIC_ALIASES:
#                         for alias in SEMANTIC_ALIASES[term_lower]:
#                             if alias in col_name.lower():
#                                 score += 3

#                 # Boost revenue/sales/amount columns as default metric
#                 col_lower = col_name.lower()
#                 if any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
#                     score += 1

#                 if score > 0:
#                     candidates.append({
#                         "dataset_id": ds.id,
#                         "dataset_name": ds.original_filename,
#                         "table_name": ds.cleaned_table_name,
#                         "column_name": col_name,
#                         "score": score,
#                     })
#     finally:
#         engine.dispose()
 
#     if not candidates:
#         return None
 
#     candidates.sort(key=lambda c: c["score"], reverse=True)
#     best = candidates[0]
 
#     # # Determine aggregation from query wording
#     # if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
#     #     aggregation = "avg"
#     # elif "how many" in cleaned_text or "count" in cleaned_text:
#     #     aggregation = "count"
#     # elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
#     #     aggregation = "max"
#     # elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
#     #     aggregation = "min"
#     # else:
#     #     aggregation = "sum"
#     # Determine aggregation from query wording inside _auto_match_metric
#     if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
#         aggregation = "avg"
#     # NEW: explicitly checking for "number" guarantees a count 
#     elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
#         aggregation = "count"
#     elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
#         aggregation = "max"
#     elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
#         aggregation = "min"
#     else:
#         aggregation = "sum"
 
#     return {
#         "dataset_id": best["dataset_id"],
#         "table_name": best["table_name"],
#         "column_name": best["column_name"],
#         "aggregation": aggregation,
#     }
def _auto_match_metric(datasets: list, tokens: list[str], cleaned_text: str) -> dict | None:
    """
    Scan numeric columns across datasets and score against query tokens.
    Uses fuzzy matching to improve column resolution.
    """
    engine = create_engine(settings.DATABASE_URL)
    candidates = []
    
    import difflib

    try:
        inspector = inspect(engine)
        for ds in datasets:
            try:
                columns_info = inspector.get_columns(ds.cleaned_table_name)
            except Exception:
                continue

            for col in columns_info:
                col_name = col["name"]
                type_str = str(col["type"]).upper()
                if not any(t in type_str for t in NUMERIC_TYPE_HINTS):
                    continue
                if any(hint in col_name.lower() for hint in ID_LIKE_HINTS):
                    continue

                col_words = col_name.lower().replace("_", " ").split()
                score = 0
                
                # Check for tokens with fuzzy match (Simulating RapidFuzz/Levenshtein)
                for w in col_words:
                    for qt in tokens: 
                        fuzz = difflib.SequenceMatcher(None, w, qt.lower()).ratio()
                        if fuzz > 0.8:
                            score += 2 * fuzz
                
                # Semantic Aliases
                for term in tokens:
                    term_lower = term.lower()
                    if term_lower in SEMANTIC_ALIASES:
                        for alias in SEMANTIC_ALIASES[term_lower]:
                            if alias in col_name.lower():
                                score += 3

                # FIX: Require score > 0 before boosting!
                # This prevents unrelated datasets from winning the auto-metric fallback.
                col_lower = col_name.lower()
                if score > 0 and any(hint in col_lower for hint in ["revenue", "amount", "sales", "price", "total"]):
                    score += 1

                # Append to candidates only if it matched the user's text
                if score > 0:
                    candidates.append({
                        "dataset_id": ds.id,
                        "dataset_name": ds.original_filename,
                        "table_name": ds.cleaned_table_name,
                        "column_name": col_name,
                        "score": score,
                    })
    finally:
        engine.dispose()
 
    if not candidates:
        return None
 
    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0]
 
    # Determine aggregation from query wording inside _auto_match_metric
    if "average" in cleaned_text or "avg" in cleaned_text or "mean" in cleaned_text:
        aggregation = "avg"
    elif "how many" in cleaned_text or "count" in cleaned_text or "number" in cleaned_text: 
        aggregation = "count"
    elif "highest" in cleaned_text or "max" in cleaned_text or "maximum" in cleaned_text:
        aggregation = "max"
    elif "lowest" in cleaned_text or "min" in cleaned_text or "minimum" in cleaned_text:
        aggregation = "min"
    else:
        aggregation = "sum"
 
    return {
        "dataset_id": best["dataset_id"],
        "table_name": best["table_name"],
        "column_name": best["column_name"],
        "aggregation": aggregation,
    }
 
def _is_text_column(sa_type) -> bool:
    if sa_type is None:
        return False
    type_str = str(sa_type).upper()
    return "CHAR" in type_str or "TEXT" in type_str


def _is_date_column(sa_type) -> bool:
    if sa_type is None:
        return False
    type_str = str(sa_type).upper()
    return any(t in type_str for t in DATE_TYPE_HINTS)
 
 
def _get_search_variants(candidate: str) -> list[str]:
    """
    Generate de-pluralized / stemmed variants so plural query words match
    singular DB values: 'females' → ['females', 'female'].
    """
    variants = [candidate]
    c = candidate.lower()
 
    # Strip trailing 's' (females → female, orders → order)
    if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        stem = candidate[:-1]
        if stem.lower() not in [v.lower() for v in variants]:
            variants.append(stem)
 
    # Strip trailing 'es' (branches → branch, classes → class)
    if c.endswith("es") and len(c) > 4:
        stem = candidate[:-2]
        if stem.lower() not in [v.lower() for v in variants]:
            variants.append(stem)
 
    return variants