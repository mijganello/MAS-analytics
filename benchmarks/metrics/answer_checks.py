"""
Deterministic per-question answer verification.

For each entry in ground_truth["expected_numbers"] checks whether the
response contains a numeric value within the declared tolerance.
No aggregate score — only explicit pass/fail per question.
"""
from __future__ import annotations

from typing import Any

from metrics.data_quality import _extract_numbers


def verify_answers(
    response_text: str,
    expected_numbers: list[dict] | None,
) -> dict[str, Any]:
    """
    Returns:
        answers_correct  int
        answers_total    int
        checks           list[{key, question, expected, tolerance, matched}]
    """
    if not expected_numbers:
        return {"answers_correct": 0, "answers_total": 0, "checks": []}

    response_nums = _extract_numbers(response_text)
    checks: list[dict] = []
    correct = 0

    for item in expected_numbers:
        key       = item.get("key", "unknown")
        expected  = float(item["value"])
        tolerance = float(item.get("tolerance", 0.01))
        question  = item.get("question", "")

        if expected == 0:
            matched = any(abs(n) <= 1e-6 for n in response_nums)
        else:
            matched = any(
                abs(n - expected) / abs(expected) <= tolerance
                for n in response_nums
            )

        if matched:
            correct += 1

        checks.append({
            "key":       key,
            "question":  question,
            "expected":  expected,
            "tolerance": tolerance,
            "matched":   matched,
        })

    return {
        "answers_correct": correct,
        "answers_total":   len(expected_numbers),
        "checks":          checks,
    }
