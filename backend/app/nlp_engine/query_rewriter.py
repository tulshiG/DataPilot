import re

# Canonical rewrite rules — applied BEFORE tokenization so everything downstream
# (intent detection, entity extraction) sees clearer, more parseable phrasing.
REWRITE_RULES = [
    (r"\bwho bought\b", "customers who purchased"),
    (r"\bwho purchased\b", "customers who purchased"),
    (r"\bbest city\b", "city with highest revenue"),
    (r"\bbest region\b", "region with highest revenue"),
    (r"\bbest product\b", "product with highest revenue"),
    (r"\bbig customers?\b", "customers with highest spending"),
    (r"\bbiggest customers?\b", "customers with highest spending"),
    (r"\bsmall customers?\b", "customers with lowest spending"),
    (r"\bno\.\s*of\b", "number of"),
    (r"\bavg\.\s", "average "),
]


def rewrite_query(cleaned_text: str) -> str:
    """Module 15 — canonicalize common informal phrasings into a form the
    rest of the pipeline parses more reliably."""
    rewritten = cleaned_text
    for pattern, replacement in REWRITE_RULES:
        rewritten = re.sub(pattern, replacement, rewritten)
    return rewritten