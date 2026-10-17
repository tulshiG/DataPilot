import logging
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from app.nlp_engine.preprocessing import clean_query_text
from app.nlp_engine.tokenizer import tokenize, remove_stop_words
from app.nlp_engine.intent_detector import detect_intent
from app.nlp_engine.entity_extractor import (
    extract_entities_and_metrics,
    extract_group_by_hint,
    extract_filter_values
)
from app.nlp_engine.query_mapper import map_to_query_spec
from app.nlp_engine.sql_generator import generate_sql
from app.knowledge_engine.rule_engine import match_business_rule, apply_rule_to_spec
from app.nlp_engine.dataset_resolver import resolve_dataset
from app.nlp_engine.query_planner import build_query_plan
from app.nlp_engine.confidence_engine import compute_plan_confidence, decide_action
from app.nlp_engine.numeric_filter_parser import extract_numeric_filters
from app.nlp_engine.time_parser import extract_time_filter
from app.models.dataset import Dataset as DatasetModel
from app.nlp_engine.business_intent_mapper import match_business_intent
from app.nlp_engine.result_validator import validate_query_plan
from app.nlp_engine.query_rewriter import rewrite_query
logger = logging.getLogger(__name__)

class NLPQueryPipeline:
    """
    End-to-end NLP Query Parsing and Routing Pipeline.
    Implements the full 20-step lifecycle for complex analytic queries.
    """
    def __init__(self, db: Session, workspace_id: int, dataset_id: int | None = None):
        self.db = db
        self.workspace_id = workspace_id
        self.dataset_id = dataset_id
        
    def execute(self, raw_query: str) -> dict:
        trace = {}
        
        # 1. User Query
        trace["user_query"] = raw_query
        
        # 2. Query Normalization
        cleaned_text = self._normalize_query(raw_query)
        trace["normalized"] = cleaned_text
# 2b. Query Rewrite Engine (Module 15) — canonicalize informal phrasings
        rewritten_text = rewrite_query(cleaned_text)
        trace["rewritten"] = rewritten_text

        # 3. Spell Correction (Hook for future extension like symspell)
        corrected_text = self._spell_correct(rewritten_text)
        trace["spell_corrected"] = corrected_text
        
        # 4. Tokenization
        all_tokens = tokenize(corrected_text)
        meaningful_tokens = remove_stop_words(all_tokens)
        trace["tokens"] = meaningful_tokens
        # Dataset Identification (ranked, confidence-scored — never "which dataset?")
        dataset_ranking = resolve_dataset(self.db, self.workspace_id, meaningful_tokens, corrected_text, self.dataset_id)
        trace["dataset_ranking"] = dataset_ranking
        # 5. POS + Dependency Parsing (Hook for NLP libraries like spaCy)
        pos_deps = self._pos_and_dependency_parse(meaningful_tokens)
        trace["pos_deps"] = pos_deps
        
        # 6. Semantic Meaning Extraction (Hook for business aliases mapping)
        semantics = self._semantic_meaning_extraction(meaningful_tokens)
        trace["semantics"] = semantics
        
        # 7. Intent Classification
        intent_res = detect_intent(corrected_text, meaningful_tokens)
        trace["intent"] = intent_res
        
        # 8-11. Dataset, Table, Column, Metric & Aggregation Detection
        extraction = extract_entities_and_metrics(
            self.db, self.workspace_id, meaningful_tokens, corrected_text, self.dataset_id
        )
        extraction["_query_tokens"] = meaningful_tokens
        extraction["_query_cleaned"] = corrected_text
        trace["entities_and_metrics"] = extraction
        business_intent = match_business_intent(corrected_text)
        trace["business_intent"] = business_intent
        
        # Bypass deep extraction for special intents (e.g. Dashboard generating)
        is_special = intent_res.get("is_special", False)
        
        # 12. Time Expression Detection (Group By Hints)
        group_by = None if is_special else extract_group_by_hint(corrected_text, meaningful_tokens)
        extraction["group_by_hint"] = group_by
        trace["group_by_hint"] = group_by

        # 13. Filter Detection
        filters = [] if is_special else extract_filter_values(
            self.db, self.workspace_id, meaningful_tokens, raw_query, self.dataset_id
        )
        trace["filters"] = filters
        
        # 14. Join Relationship Detection & 15. Subquery & 16. Ranking/Sorting
        # Mapped out concurrently during map_to_query_spec
        spec = map_to_query_spec(
            self.db, self.workspace_id, intent_res, extraction, filters,
            dataset_ranking=dataset_ranking,
            business_intent=business_intent,
        )
        # 12b/13b: Numeric Range & Time Expression Filters — deterministic, rule-based, no LLM
        if spec.get("primary_table"):
            ds_row = self.db.query(DatasetModel).filter(DatasetModel.cleaned_table_name == spec["primary_table"]).first()
            nlp_index = (ds_row.profile_json or {}).get("nlp_index", {}) if ds_row else {}
            numeric_cols = nlp_index.get("numeric_columns", [])
            date_cols = nlp_index.get("date_columns", [])
            synonyms = nlp_index.get("synonyms", {})

            numeric_filters = extract_numeric_filters(corrected_text, numeric_cols, synonyms, primary_numeric_hint=spec.get("select_column"))
            time_filter = extract_time_filter(corrected_text, date_cols)

            if numeric_filters:
                if "numeric_filters" not in spec:
                    spec["numeric_filters"] = []
                spec["numeric_filters"].extend(numeric_filters)
            if time_filter:
                spec["time_filter"] = time_filter

        trace["numeric_filters"] = spec.get("numeric_filters")
        trace["time_filter"] = spec.get("time_filter")
        trace["join_relationship_detection"] = {
                "joins": spec.get("joins", []),
                "hops": spec.get("join_path_hops", 0),
            }
        # (Business overlay applied atop the spec)
        matched_rule = None
        if not is_special:
            matched_rule = match_business_rule(self.db, self.workspace_id, corrected_text)
            if matched_rule:
                spec = apply_rule_to_spec(matched_rule, spec)
        trace["matched_rule"] = matched_rule.trigger_phrase if matched_rule else None

        # Module 12: validate every real-world assumption the (now fully-built) plan
        # makes before we ever try to run SQL against it.
        validation_errors = [] if is_special else validate_query_plan(self.db, spec)
        trace["validation_errors"] = validation_errors
                
        # 17. Visualization Detection
        visual_intent = self._detect_visualization(intent_res, spec)
        trace["visualization_intent"] = visual_intent
        
        # 18. SQL Execution Planner
        # Override the old rule-based ranking with the precise dataset_scores that verified filter values with DB lookups
        accurate_ranking = extraction.get("dataset_scores") or dataset_ranking
        trace["dataset_ranking"] = accurate_ranking
        query_plan = build_query_plan(spec, intent_res, extraction, accurate_ranking)
        trace["query_spec"] = spec
        trace["query_plan"] = query_plan
        #Confidence Engine — score the plan before committing to SQL generation
        confidence = compute_plan_confidence(query_plan, intent_res)
        action = decide_action(confidence)
        trace["confidence"] = confidence
        trace["action"] = action        
        # 19. SQL Generator & 20. Result Validator (Hook)
        sql, params, error = None, {}, None
        # if not is_special:
        #     try:
        #          sql, params = generate_sql(spec)
        #          is_valid = self._validate_sql(sql)
        #          if not is_valid:
        #              error = "SQL Validation failed (internal constraint)"
        #     except Exception as e:
        #          error = str(e)
        if not is_special and action == "execute" and not validation_errors:
            try:
                sql, params = generate_sql(spec)
                is_valid = self._validate_sql(sql)
                if not is_valid:
                    error = "SQL Validation failed (internal constraint)"
            except Exception as e:
                error = str(e)
        elif validation_errors:
            action = "try_alternate"  # force retry against next-ranked dataset, per Module 12: "don't immediately throw an error"
            error = "validation_failed:" + "; ".join(validation_errors)
        elif not is_special:
            error = f"confidence_too_low:{action}"                     
        trace["generated_sql"] = sql
        trace["sql_params"] = params
        trace["sql_error"] = error
        
        # 21. Visualization (will be resolved by query service handling the layout/rendering info)
        
        return {
            "pipeline_trace": trace,
            "query_spec": spec,
            "query_plan": query_plan,
            "confidence": confidence,
            "action": action,
            "intent": intent_res,
            "matched_rule": trace["matched_rule"],
            "generated_sql": sql,
            "sql_params": params,
            "error": error
        }
        
    def _normalize_query(self, query: str) -> str:
        return clean_query_text(query)
        
    def _spell_correct(self, query: str) -> str:
        # Placeholder: Map common known misspellings in datasets if detected, or defer to raw query
        # Future: inject spell correction libraries here matching DB aliases.
        return query
        
    def _pos_and_dependency_parse(self, tokens: list[str]) -> dict:
        # Placeholder: Use nltk/spacy output for structural disambiguation
        return {"tags": {token: "NOUN" for token in tokens}, "deps": {}}
        
    def _semantic_meaning_extraction(self, tokens: list[str]) -> list[str]:
        # Placeholder: Identify specific context (e.g. mapping "sales" to "revenue") before intent 
        return tokens
        
    # def _detect_visualization(self, intent_res: dict, spec: dict) -> str:
    #     # Evaluate desired chart type from query specs and aggregation depth
    #     intent = intent_res.get("intent")
    #     if intent == "generate_dashboard": return "dashboard"
    #     if spec.get("is_trend") or spec.get("period"): return "line_chart"
    #     if intent == "top_n": return "bar_chart"
    #     return "table"
    def _detect_visualization(self, intent_res: dict, spec: dict) -> str:
        labels = intent_res.get("labels", {})
        intent = intent_res.get("intent")

        if intent == "generate_dashboard":
            return "dashboard"

        if labels.get("is_trend") or spec.get("time_filter") or spec.get("period"):
            return "line_chart"

        if intent in ("top_n", "bottom_n") or spec.get("group_by_hint"):
            return "bar_chart"

        return "table"
    def _detect_visualization(self, intent_res: dict, spec: dict) -> str:
        labels = intent_res.get("labels", {})

        if intent_res.get("intent") == "generate_dashboard":
            return "dashboard"

        if labels.get("is_trend") or spec.get("time_filter"):
            return "line_chart"  # Trend -> Line

        if spec.get("group_by_column") and spec.get("aggregation"):
            if intent_res.get("intent") in ("top_n", "bottom_n"):
                return "bar_chart"  # Comparison -> Bar
            return "pie_chart"  # Distribution -> Pie

        if spec.get("numeric_filters") and len([f for f in spec.get("filters", [])]) == 0 and not spec.get("group_by_column"):
            return "histogram"  # Frequency of a numeric range -> Histogram

        metric_count = 1 if spec.get("select_column") else 0
        if metric_count >= 2 or (spec.get("select_column") and spec.get("subquery_column")):
            return "scatter_plot"  # Correlation -> Scatter

        return "table"
        
    def _validate_sql(self, sql: str) -> bool:
        # Placeholder: Ensure no dropping tables, destructive ops, or cross-tenant injections exist
        sql_lower = sql.lower()
        if any(bad in sql_lower for bad in ["drop ", "delete ", "insert ", "update ", "truncate ", ";"]):
             return False
        return True