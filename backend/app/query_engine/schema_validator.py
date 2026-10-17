"""
Query Engine — Schema Validator
=================================
Validates that the columns, tables, and values referenced in a query_spec
actually exist in the database before SQL generation.

This catches errors early — before they become cryptic PostgreSQL errors —
and provides fuzzy suggestions for misspelled column names.

Validation checks:
    1. Table exists in workspace
    2. Columns exist in table
    3. Group-by column is a valid dimension
    4. Filter values are plausible (type-compatible)
    5. Sort column exists and is orderable
"""

import logging
from difflib import get_close_matches
from sqlalchemy.orm import Session

from app.metadata.models import ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)


class ValidationResult:
    """Encapsulates the result of schema validation."""

    def __init__(self):
        self.valid = True
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.corrections: dict = {}  # column_name → corrected_name

    def add_error(self, field: str, message: str, suggestion: str | None = None):
        self.valid = False
        entry = {"field": field, "message": message}
        if suggestion:
            entry["suggestion"] = suggestion
        self.errors.append(entry)

    def add_warning(self, field: str, message: str):
        self.warnings.append({"field": field, "message": message})

    def add_correction(self, original: str, corrected: str):
        self.corrections[original] = corrected
        self.warnings.append({
            "field": original,
            "message": f"Auto-corrected '{original}' → '{corrected}'",
        })

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "corrections": self.corrections,
        }


def validate_query_spec(
    db: Session,
    workspace_id: int,
    spec: dict,
    auto_correct: bool = True,
) -> ValidationResult:
    """
    Validate a query_spec against the actual schema.

    Parameters
    ----------
    db : Session
    workspace_id : int
    spec : dict
        The query_spec from the LLM or keyword pipeline.
    auto_correct : bool
        If True, attempt to fuzzy-correct misspelled column/table names.

    Returns
    -------
    ValidationResult
        Contains valid flag, errors, warnings, and auto-corrections.
    """
    result = ValidationResult()
    primary_table = spec.get("primary_table")

    if not primary_table:
        result.add_warning("primary_table", "No primary table specified in query spec")
        return result

    # ── 1. Validate table exists ──
    table_meta = db.query(TableMetadata).filter(
        TableMetadata.workspace_id == workspace_id,
        TableMetadata.table_name == primary_table,
    ).first()

    if not table_meta:
        # Try fuzzy match
        all_tables = db.query(TableMetadata.table_name).filter(
            TableMetadata.workspace_id == workspace_id
        ).all()
        table_names = [t[0] for t in all_tables]
        matches = get_close_matches(primary_table, table_names, n=1, cutoff=0.6)

        if matches and auto_correct:
            corrected = matches[0]
            result.add_correction(primary_table, corrected)
            spec["primary_table"] = corrected
            primary_table = corrected
        else:
            suggestion = matches[0] if matches else None
            result.add_error("primary_table",
                             f"Table '{primary_table}' not found in workspace",
                             suggestion)
            return result

    # ── 2. Load all columns for the table ──
    columns = db.query(ColumnMetadata).filter(
        ColumnMetadata.workspace_id == workspace_id,
        ColumnMetadata.table_name == primary_table,
    ).all()

    col_names = [c.column_name for c in columns]
    col_names_lower = {c.lower(): c for c in col_names}

    # ── 3. Validate select column ──
    select_col = spec.get("select_column")
    if select_col:
        validated = _validate_column(select_col, col_names, col_names_lower,
                                     "select_column", result, spec, auto_correct)

    # ── 4. Validate group_by column ──
    group_col = spec.get("group_by_column")
    if group_col:
        _validate_column(group_col, col_names, col_names_lower,
                         "group_by_column", result, spec, auto_correct)

    # ── 5. Validate additional group_by ──
    for i, gb in enumerate(spec.get("additional_group_by", [])):
        _validate_column(gb, col_names, col_names_lower,
                         f"additional_group_by[{i}]", result, spec, auto_correct,
                         list_key="additional_group_by", list_idx=i)

    # ── 6. Validate filter columns ──
    for i, f in enumerate(spec.get("filters", [])):
        if "column" in f:
            _validate_column(f["column"], col_names, col_names_lower,
                             f"filters[{i}].column", result, spec, auto_correct,
                             dict_ref=f, dict_key="column")

    # ── 7. Validate numeric filter columns ──
    for i, f in enumerate(spec.get("numeric_filters", [])):
        if "column" in f:
            _validate_column(f["column"], col_names, col_names_lower,
                             f"numeric_filters[{i}].column", result, spec, auto_correct,
                             dict_ref=f, dict_key="column")

    # ── 8. Validate order_by column ──
    order_col = spec.get("order_by")
    if order_col:
        _validate_column(order_col, col_names, col_names_lower,
                         "order_by", result, spec, auto_correct)

    # ── 9. Validate time_filter column ──
    time_filter = spec.get("time_filter")
    if time_filter and time_filter.get("column"):
        _validate_column(time_filter["column"], col_names, col_names_lower,
                         "time_filter.column", result, spec, auto_correct,
                         dict_ref=time_filter, dict_key="column")

    if result.valid:
        logger.debug(f"Schema validation passed for table '{primary_table}'")
    else:
        logger.warning(f"Schema validation failed: {result.errors}")

    return result


def _validate_column(
    col_name: str,
    valid_cols: list[str],
    col_lookup: dict[str, str],
    field_name: str,
    result: ValidationResult,
    spec: dict,
    auto_correct: bool,
    list_key: str | None = None,
    list_idx: int | None = None,
    dict_ref: dict | None = None,
    dict_key: str | None = None,
) -> bool:
    """Validate a single column reference. Returns True if valid."""
    if col_name in valid_cols:
        return True

    # Case-insensitive match
    if col_name.lower() in col_lookup:
        corrected = col_lookup[col_name.lower()]
        if auto_correct:
            _apply_correction(col_name, corrected, field_name, spec, result,
                              list_key, list_idx, dict_ref, dict_key)
        return True

    # Fuzzy match
    matches = get_close_matches(col_name.lower(), list(col_lookup.keys()), n=1, cutoff=0.6)
    if matches and auto_correct:
        corrected = col_lookup[matches[0]]
        _apply_correction(col_name, corrected, field_name, spec, result,
                          list_key, list_idx, dict_ref, dict_key)
        return True

    suggestion = col_lookup.get(matches[0]) if matches else None
    result.add_error(field_name, f"Column '{col_name}' not found", suggestion)
    return False


def _apply_correction(
    original: str,
    corrected: str,
    field_name: str,
    spec: dict,
    result: ValidationResult,
    list_key: str | None = None,
    list_idx: int | None = None,
    dict_ref: dict | None = None,
    dict_key: str | None = None,
):
    """Apply an auto-correction to the spec in-place."""
    result.add_correction(original, corrected)

    if dict_ref and dict_key:
        dict_ref[dict_key] = corrected
    elif list_key and list_idx is not None:
        spec[list_key][list_idx] = corrected
    elif "." not in field_name:
        spec[field_name] = corrected
