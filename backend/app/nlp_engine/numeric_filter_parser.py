import re
from rapidfuzz import fuzz

COMPARISON_PATTERNS = [
    (r"between\s+([\d,\.]+)\s+and\s+([\d,\.]+)", "between"),
    (r"(?:more than|greater than|above|over|exceeding|higher than)\s+([\d,\.]+)", ">"),
    (r"(?:less than|below|under|lower than)\s+([\d,\.]+)", "<"),
    (r"(?:at least|minimum of|no less than)\s+([\d,\.]+)", ">="),
    (r"(?:at most|maximum of|no more than)\s+([\d,\.]+)", "<="),
    (r"(?:exactly|equal to)\s+([\d,\.]+)", "="),
    (r"(?<![\d\w\.\-])(\d+(?:\.\d+)?)(?![\d\w\.\-])", "="), # fallback naked number
]


def _to_number(s: str):
    s = s.replace(",", "")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _resolve_numeric_column(text: str, position: int, numeric_columns: list[str], synonyms: dict) -> str | None:
    """Look at the words right before the number to guess which column it refers to."""
    window = text[max(0, position - 40):position]
    best_col, best_score = None, 0
    for col in numeric_columns:
        col_clean = col.lower().replace("_", " ")
        score = fuzz.partial_ratio(col_clean, window)
        for syn in synonyms.get(col, []):
            score = max(score, fuzz.partial_ratio(syn, window))
        if score > best_score:
            best_score, best_col = score, col
    return best_col if best_score > 55 else None


def _needs_cast(column: str, numeric_info: dict | None) -> bool:
    if not numeric_info:
        return False
    column_info = numeric_info.get(column)
    if isinstance(column_info, dict):
        return bool(column_info.get("soft", False))
    return bool(column_info)


def extract_numeric_filters(
    cleaned_text: str,
    numeric_columns: list[str],
    synonyms: dict,
    primary_numeric_hint: str | None = None,
    numeric_info: dict | None = None,
) -> list[dict]:
    """
    Detect comparison expressions ('more than 10000', 'between 100 and 200')
    and resolve which numeric column they apply to using nearby word context,
    falling back to the already-resolved metric column if nothing nearby matches.
    """
    results = []
    for pattern, op in COMPARISON_PATTERNS:
        for match in re.finditer(pattern, cleaned_text):
            if op == "between":
                low, high = match.groups()
                value = (_to_number(low), _to_number(high))
            else:
                value = _to_number(match.group(1))
            if value is None or (isinstance(value, tuple) and None in value):
                continue

            column = _resolve_numeric_column(cleaned_text, match.start(), numeric_columns, synonyms) or primary_numeric_hint
            if column:
                results.append({"column": column, "op": op, "value": value,
                                "needs_cast": numeric_info.get(column, {}).get("soft", False) if numeric_info else False,})
    return results