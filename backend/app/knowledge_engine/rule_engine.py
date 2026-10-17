from sqlalchemy.orm import Session
from app.models.knowledge_base import BusinessRule

def match_business_rule(db: Session, workspace_id: int, cleaned_text: str) -> BusinessRule | None:
    """
    Check the cleaned query text against registered BusinessRule trigger phrases.
    Simple substring/overlap match — good enough for a finite, curated rule set.
    """
    rules = db.query(BusinessRule).filter(BusinessRule.workspace_id == workspace_id).all()

    best_match = None
    best_score = 0

    for rule in rules:
        trigger = rule.trigger_phrase.lower()
        if trigger in cleaned_text:
            score = len(trigger)  # longer, more specific matches win
            if score > best_score:
                best_score = score
                best_match = rule

    return best_match


def apply_rule_to_spec(rule: BusinessRule, spec: dict) -> dict:
    """Overlay a matched rule's stored logic onto the query spec (rule takes precedence)."""
    if not rule or not rule.rule_logic:
        return spec

    logic = rule.rule_logic
    if "sort_by" in logic:
        spec["order_by"] = logic["sort_by"]
    if "order" in logic:
        spec["order_direction"] = logic["order"]
    if "limit" in logic:
        spec["limit"] = logic["limit"]
    if "aggregation" in logic:
        spec["aggregation"] = logic["aggregation"]

    return spec