from sqlalchemy.orm import Session
from app.nlp_engine.pipeline import NLPQueryPipeline

def resolve_query_chain(
    db: Session, workspace_id: int, raw_query: str, dataset_id: int | None = None
) -> dict:
    """
    Forward-chain through the full NLP pipeline using the newly implemented step-by-step trace architecture.
    """
    pipeline = NLPQueryPipeline(db, workspace_id, dataset_id)
    pipeline_result = pipeline.execute(raw_query)
    
    # Format the result back into what the original callers inside query_service expect
    return {
        "preprocessed": pipeline_result["pipeline_trace"].get("normalized"),
        "intent": pipeline_result["intent"],
        "extraction": pipeline_result["pipeline_trace"].get("entities_and_metrics", {}),
        "matched_rule": pipeline_result["matched_rule"],
        "query_spec": pipeline_result["query_spec"],
        
        # We also pass up the full 21-step pipeline trace for debugging or advanced visualization
        "pipeline_trace": pipeline_result["pipeline_trace"],
        
        # Expose the SQL generation early-resolved data if needed
        "generated_sql": pipeline_result["generated_sql"],
        "sql_params": pipeline_result["sql_params"],
    }