"""
Factual Recall (FR) and Numerical Accuracy (NA) metrics.

Deterministic: no LLM evaluation. Uses regex number extraction + tolerance comparison.
"""
import re
import math
from typing import Any


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text (handles Russian number formatting)."""
    # Normalize: remove spaces between digits (Russian style: 1 000 000)
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    # Find all numbers (int or float, with optional comma decimal)
    raw = re.findall(r'\d+(?:[.,]\d+)?', text)
    result = []
    for r in raw:
        try:
            val = float(r.replace(',', '.'))
            if not math.isnan(val) and not math.isinf(val):
                result.append(val)
        except ValueError:
            pass
    return result


def _matches(found: float, expected: float, tolerance: float) -> bool:
    """Check if 'found' is within relative tolerance of 'expected'."""
    if expected == 0:
        return abs(found) <= tolerance
    return abs(found - expected) / max(abs(expected), 1e-9) <= tolerance


def factual_recall(response_text: str, expected_numbers: list[dict[str, Any]],
                   tolerance: float = 0.05) -> dict[str, Any]:
    """
    Compute Factual Recall.

    Args:
        response_text: The full response text to search in.
        expected_numbers: List of dicts with keys:
            - value: expected numeric value
            - tolerance: optional override for this specific value
            - key: label for logging
        tolerance: Default tolerance (relative, 0.05 = 5%).

    Returns:
        dict with fr (float), details (list), found_count, total_count
    """
    found_numbers = _extract_numbers(response_text)
    details = []
    found_count = 0

    for exp in expected_numbers:
        ev  = float(exp["value"])
        tol = float(exp.get("tolerance", tolerance))
        key = exp.get("key", str(ev))

        matched = any(_matches(f, ev, tol) for f in found_numbers)
        if matched:
            found_count += 1
        details.append({
            "key":     key,
            "expected": ev,
            "found":    matched,
            "tolerance": tol,
        })

    total = len(expected_numbers)
    fr    = round(found_count / total, 4) if total > 0 else 0.0

    return {
        "fr":          fr,
        "found_count": found_count,
        "total_count": total,
        "details":     details,
    }


def numerical_accuracy(response_text: str, expected_numbers: list[dict[str, Any]],
                        strict_tolerance: float = 0.01) -> dict[str, Any]:
    """
    Compute Numerical Accuracy (NA) — stricter than FR (1% tolerance by default).

    Only counts facts that are correct within strict_tolerance.
    """
    result = factual_recall(response_text, expected_numbers, tolerance=strict_tolerance)
    result["na"]  = result.pop("fr")
    return result
