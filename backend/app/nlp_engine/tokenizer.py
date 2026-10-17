STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "if", "then", "than", "so", "that", "this", "these", "those",
    "me", "my", "i", "we", "us", "our", "you", "your",
    "please", "can", "could", "would", "tell", "get", "find",
    "what", "which", "do", "does", "did",
}

COMPOUND_PHRASES = [
    "how many", "how much", "total amount", "number of", "total of",
    "amount of", "over time", "greater than", "less than", "equal to", "show me"
]

def tokenize(text: str) -> list[str]:
    """Split cleaned text into word tokens, preserving key compound phrases."""
    text_work = text
    # Temporarily replace compound phrases with a single token (e.g., 'how_many')
    for phrase in COMPOUND_PHRASES:
        if phrase in text_work:
            text_work = text_work.replace(phrase, phrase.replace(" ", "_"))
    
    tokens = text_work.split()
    # Restore the compound phrases if we want them as single entities, or we can just leave them 
    # as single tokens (e.g., how_many) which is often easier for matching. We'll restore spaces 
    # so they match the INTENT_PATTERNS which have spaces.
    return [t.replace("_", " ") for t in tokens]

def remove_stop_words(tokens: list[str]) -> list[str]:
    """Filter out common stop words, keeping meaningful business terms."""
    return [t for t in tokens if t not in STOP_WORDS]

def preprocess_query(text: str) -> dict:
    from app.nlp_engine.preprocessing import clean_query_text
    cleaned = clean_query_text(text)
    all_tokens = tokenize(cleaned)
    meaningful_tokens = remove_stop_words(all_tokens)
    return {
        "original": text,
        "cleaned": cleaned,
        "all_tokens": all_tokens,
        "tokens": meaningful_tokens,
    }