"""
Query Completeness (QC) metric.

Checks whether required topics from the ground truth appear in the response.
Uses substring matching with basic Russian stemming (prefix matching).
Deterministic — no LLM.
"""


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation."""
    import re
    return re.sub(r'[^\w\s]', ' ', text.lower())


def _topic_present(text_lower: str, topic: str) -> bool:
    """
    Check if a topic keyword is present in text.
    topic may be a prefix (stemmed root) — we check if any word starts with it.
    """
    topic_lower = topic.lower().strip()
    # Direct substring match
    if topic_lower in text_lower:
        return True
    # Word-boundary prefix match (handles Russian word forms)
    words = text_lower.split()
    return any(w.startswith(topic_lower) for w in words)


def query_completeness(response_text: str, required_topics: list[str]) -> dict:
    """
    Compute Query Completeness.

    Args:
        response_text: Full text of the response.
        required_topics: List of topic keywords/prefixes that should appear.

    Returns:
        dict with qc (float [0,1]), found_topics, missing_topics, details.
    """
    norm_text  = _normalize(response_text)
    details    = []
    found_count = 0
    found_list  = []
    missing_list= []

    for topic in required_topics:
        present = _topic_present(norm_text, topic)
        details.append({"topic": topic, "found": present})
        if present:
            found_count += 1
            found_list.append(topic)
        else:
            missing_list.append(topic)

    total = len(required_topics)
    qc    = round(found_count / total, 4) if total > 0 else 0.0

    return {
        "qc":             qc,
        "found_count":    found_count,
        "total_topics":   total,
        "found_topics":   found_list,
        "missing_topics": missing_list,
        "details":        details,
    }
