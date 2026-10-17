"""
RAG Engine — Context Assembler
================================
Formats retrieved RAG chunks into a structured prompt section for the LLM.

Takes the raw chunk list from ``rag_retriever.retrieve_context()`` and
produces a well-organized text block that goes into the LLM's system prompt
under the ``DATABASE CONTEXT`` section.
"""

import logging

logger = logging.getLogger(__name__)


def assemble_context(chunks: list[dict], max_tokens_estimate: int = 2000) -> str:
    """
    Assemble retrieved RAG chunks into a formatted context string.

    Organizes chunks by type for readability:
        1. Table schemas (overview)
        2. Column details (specifics)
        3. Business rules and metrics
        4. Relationships
        5. Past query patterns

    Parameters
    ----------
    chunks : list[dict]
        Retrieved chunks from rag_retriever.
    max_tokens_estimate : int
        Rough character budget (1 token ≈ 4 chars). Chunks are included
        in order of relevance until the budget is exhausted.

    Returns
    -------
    str
        Formatted context string ready for LLM prompt injection.
    """
    if not chunks:
        return "No database context available. Ask the user to upload and process data first."

    # Group chunks by type, maintaining relevance order within each group.
    type_order = ["table_schema", "column_detail", "business_metric", "business_rule",
                  "relationship", "query_history"]
    grouped: dict[str, list[dict]] = {t: [] for t in type_order}
    for chunk in chunks:
        ctype = chunk.get("type", "unknown")
        if ctype in grouped:
            grouped[ctype].append(chunk)
        else:
            grouped.setdefault("other", []).append(chunk)

    # Build formatted output, respecting token budget.
    sections = []
    char_count = 0
    char_limit = max_tokens_estimate * 4  # rough token→char conversion

    # Section headers for each type.
    _headers = {
        "table_schema": "## Tables",
        "column_detail": "## Column Details",
        "business_metric": "## Business Metrics",
        "business_rule": "## Business Rules",
        "relationship": "## Table Relationships",
        "query_history": "## Similar Past Queries",
    }

    for ctype in type_order:
        type_chunks = grouped.get(ctype, [])
        if not type_chunks:
            continue

        header = _headers.get(ctype, f"## {ctype.title()}")
        section_lines = [header]

        for chunk in type_chunks:
            text = chunk.get("text", "")
            upcoming = len(text) + 10  # +10 for formatting overhead
            if char_count + upcoming > char_limit:
                break
            section_lines.append(f"- {text}")
            char_count += upcoming

        if len(section_lines) > 1:  # header + at least one chunk
            sections.append("\n".join(section_lines))

        if char_count >= char_limit:
            break

    return "\n\n".join(sections)
