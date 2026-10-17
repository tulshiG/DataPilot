import re

def clean_query_text(text: str) -> str:
    """Lowercase, strip extra whitespace, remove punctuation except useful symbols."""
    text = text.lower().strip()
    # Keep %, $, @, ., - since they are meaningful in BI queries/emails/dates/ids
    text = re.sub(r"[^\w\s%$@.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text