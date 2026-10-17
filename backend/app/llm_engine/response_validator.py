"""
LLM Engine — Response Validator
=================================
Pydantic models that validate the structured JSON output from the LLM.

The LLM is instructed to output a specific JSON schema, but LLMs can be
unpredictable.  This validator:
    1. Ensures all required fields are present
    2. Normalizes field values (e.g., uppercase aggregation functions)
    3. Provides sensible defaults for missing optional fields
    4. Rejects responses that are clearly malformed
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class MetricSpec(BaseModel):
    """A metric to aggregate."""
    column: str
    aggregation: str = "SUM"

    @field_validator("aggregation")
    @classmethod
    def normalize_aggregation(cls, v: str) -> str:
        v = v.upper().strip()
        valid = {"SUM", "AVG", "COUNT", "MIN", "MAX", "COUNT_DISTINCT", "MEDIAN", "STDDEV", "VARIANCE"}
        return v if v in valid else "SUM"


class FilterSpec(BaseModel):
    """A filter condition."""
    column: str
    operator: str = "eq"
    value: str | int | float | list | None = None

    @field_validator("operator")
    @classmethod
    def normalize_operator(cls, v: str) -> str:
        v = v.lower().strip()
        valid = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "between", "like"}
        return v if v in valid else "eq"


class TimeRangeSpec(BaseModel):
    """A time range filter."""
    column: str
    start: Optional[str] = None
    end: Optional[str] = None
    granularity: Optional[str] = None

    @field_validator("granularity")
    @classmethod
    def normalize_granularity(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.lower().strip()
        valid = {"day", "week", "month", "quarter", "year"}
        return v if v in valid else None


class SortSpec(BaseModel):
    """Sort specification."""
    column: Optional[str] = None
    direction: Optional[str] = None

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return "DESC" if v.upper().startswith("D") else "ASC"


class LLMQuerySpec(BaseModel):
    """
    The complete structured query specification output by the LLM.

    This is the contract between the LLM and the deterministic query engine.
    """
    intent: str = "list"
    metrics: list[MetricSpec] = Field(default_factory=list)
    filters: list[FilterSpec] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    time_range: Optional[TimeRangeSpec] = None
    sort: Optional[SortSpec] = None
    limit: Optional[int] = None
    subquery_type: Optional[str] = None
    tables: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    reasoning: Optional[str] = None

    @field_validator("intent")
    @classmethod
    def normalize_intent(cls, v: str) -> str:
        v = v.lower().strip()
        valid = {
            "aggregate", "top_n", "bottom_n", "trend", "distribution",
            "compare", "filter", "list", "generate_dashboard", "generate_insights",
            "correlation", "ranking", "calculation", "pivot", "window", "query",
        }
        return v if v in valid else "list"

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


def validate_llm_response(raw_response: dict | None) -> LLMQuerySpec | None:
    """
    Validate and normalize a raw LLM JSON response into a typed LLMQuerySpec.

    Returns None if the response is malformed beyond repair.
    """
    if not raw_response or not isinstance(raw_response, dict):
        logger.warning("LLM response is empty or not a dict")
        return None

    try:
        spec = LLMQuerySpec(**raw_response)
        logger.debug(f"LLM response validated: intent={spec.intent}, confidence={spec.confidence}")
        return spec
    except Exception as e:
        logger.warning(f"LLM response validation failed: {e}")

        # Try to salvage partial responses
        try:
            cleaned = {
                "intent": raw_response.get("intent", "list"),
                "confidence": float(raw_response.get("confidence", 0.3)),
                "reasoning": raw_response.get("reasoning"),
            }

            # Try to parse metrics
            if "metrics" in raw_response and isinstance(raw_response["metrics"], list):
                cleaned["metrics"] = raw_response["metrics"]

            # Try to parse filters
            if "filters" in raw_response and isinstance(raw_response["filters"], list):
                cleaned["filters"] = raw_response["filters"]

            if "group_by" in raw_response:
                gb = raw_response["group_by"]
                cleaned["group_by"] = gb if isinstance(gb, list) else [gb] if isinstance(gb, str) else []

            if "tables" in raw_response:
                tb = raw_response["tables"]
                cleaned["tables"] = tb if isinstance(tb, list) else [tb] if isinstance(tb, str) else []

            if "limit" in raw_response and raw_response["limit"] is not None:
                cleaned["limit"] = int(raw_response["limit"])

            spec = LLMQuerySpec(**cleaned)
            logger.info(f"Salvaged partial LLM response: intent={spec.intent}")
            return spec
        except Exception as e2:
            logger.error(f"Could not salvage LLM response: {e2}")
            return None
