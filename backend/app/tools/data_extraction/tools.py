from __future__ import annotations
from typing import Any
from app.tools.registry import tool


@tool(departments=["data_extraction"])
def get_document_structure(doc_structure_json: dict) -> dict[str, Any]:
    """Return document structure: sections, tables count, metadata."""
    return doc_structure_json or {}


@tool(departments=["data_extraction"])
def find_numeric_context(content: str, search_term: str) -> list[dict[str, Any]]:
    """Find all numbers near a given search term in content."""
    import re
    results = []
    term_lower = search_term.lower()
    pattern = re.compile(
        r'([^\n]{0,80}?' + re.escape(term_lower) + r'[^\n]{0,80}?'
        r'(\b\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d+)?\b)'
        r'[^\n]{0,40})',
        re.IGNORECASE
    )
    for match in pattern.finditer(content):
        context_str = match.group(1)
        num_str = match.group(2).replace(" ", "").replace(",", ".")
        try:
            value = float(num_str)
            results.append({"context": context_str.strip(), "value": value, "raw": num_str})
        except ValueError:
            pass
    return results[:20]


@tool(departments=["data_extraction"])
def verify_number_in_content(
    claimed_value: float,
    context_hint: str,
    fingerprint_json: dict,
) -> dict[str, Any]:
    """Verify a claimed number against the document fingerprint."""
    from app.document_pipeline.fingerprint import NumericFingerprint
    if not fingerprint_json:
        return {"status": "NOT_FOUND", "claimed_value": claimed_value}
    fp = NumericFingerprint.from_dict(fingerprint_json)
    result = fp.verify(claimed_value, context_hint)
    return {
        "status": result.status,
        "claimed_value": result.claimed_value,
        "actual_value": result.actual_value,
        "confidence": result.confidence,
        "source": result.matched_entry.source_location if result.matched_entry else None,
    }


@tool(departments=["data_extraction"])
def extract_table_from_chunks(chunks: list[dict], table_hint: str) -> dict[str, Any]:
    """Find the most relevant table chunk by hint and return its structured data."""
    from rapidfuzz import process, fuzz
    table_chunks = [c for c in chunks if c.get("chunk_type") == "table"]
    if not table_chunks:
        return {"found": False, "headers": [], "rows": []}

    contents = [c["content"] for c in table_chunks]
    match = process.extractOne(table_hint, contents, scorer=fuzz.partial_ratio)
    if not match or match[1] < 30:
        best = table_chunks[0]
    else:
        idx = contents.index(match[0])
        best = table_chunks[idx]

    # Parse content: first line = headers, rest = rows
    lines = best["content"].strip().split("\n")
    if not lines:
        return {"found": False, "headers": [], "rows": []}

    headers = [h.strip() for h in lines[0].split("|")]
    rows = [[c.strip() for c in line.split("|")] for line in lines[1:] if "|" in line]

    return {
        "found": True,
        "headers": headers,
        "rows": rows,
        "source": best.get("metadata", {}),
    }
