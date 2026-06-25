"""
Aggregate metric computation — deterministic, no composite scores.

Metrics per run
---------------
answers_correct / answers_total — per-question ground-truth checks
HI  — Hallucination Index (numbers not traceable to source data)
NPI — Numeric Precision Index (informational)
latency_s, token_count — performance only
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from metrics.answer_checks import verify_answers
from metrics.data_quality import numeric_precision_index
from metrics.hallucination import hallucination_index


def compute_all_metrics(
    response_text:   str,
    ground_truth:    dict,
    latency_seconds: float,
    token_count:     int,
    blocks:          list[dict] | None = None,
    source_file:     Path | None = None,
    is_mas:          bool = True,
) -> dict[str, Any]:
    expected_numbers = ground_truth.get("expected_numbers") if ground_truth else None

    answers = verify_answers(response_text, expected_numbers)

    # HI: source-grounded — number is OK if derivable from the data file (±2%)
    hi_result = hallucination_index(
        response_text,
        source_file=source_file,
        ground_truth_numbers=expected_numbers,
        strict_expected_only=False,
    )

    npi_result = numeric_precision_index(response_text)

    return {
        "dataset_id":      ground_truth.get("dataset_id", "unknown"),
        "mode":            "mas" if is_mas else "naive",
        "latency_s":       round(latency_seconds, 2),
        "token_count":     token_count,
        "answers_correct": answers["answers_correct"],
        "answers_total":   answers["answers_total"],
        "hi":              hi_result["hi"],
        "npi":             npi_result["npi"],
        "answer_checks":   answers["checks"],
        "npi_details": {
            "precise_count":   npi_result["precise_count"],
            "candidate_count": npi_result["candidate_count"],
            "rounded_samples": npi_result["rounded_samples"],
        },
        "hi_samples": hi_result["hallucinated_samples"],
    }


def compare_results(mas_metrics: dict, naive_metrics: dict) -> dict[str, Any]:
    """Side-by-side comparison for one dataset — no composite ratios except latency/tokens."""

    def delta(a, b):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return round(a - b, 4)
        return None

    return {
        "dataset_id":          mas_metrics["dataset_id"],
        "mas_answers_correct": mas_metrics["answers_correct"],
        "naive_answers_correct": naive_metrics["answers_correct"],
        "answers_total":       mas_metrics["answers_total"],
        "mas_hi":              mas_metrics["hi"],
        "naive_hi":            naive_metrics["hi"],
        "mas_npi":             mas_metrics["npi"],
        "naive_npi":           naive_metrics["npi"],
        "mas_latency_s":       mas_metrics["latency_s"],
        "naive_latency_s":     naive_metrics["latency_s"],
        "mas_tokens":          mas_metrics["token_count"],
        "naive_tokens":        naive_metrics["token_count"],
        "answers_delta":       delta(mas_metrics["answers_correct"], naive_metrics["answers_correct"]),
        "hi_delta":            delta(naive_metrics["hi"], mas_metrics["hi"]),  # positive = MAS lower HI
        "latency_ratio":       round(mas_metrics["latency_s"] / naive_metrics["latency_s"], 4)
                               if naive_metrics["latency_s"] else float("inf"),
        "token_ratio":         round(mas_metrics["token_count"] / naive_metrics["token_count"], 4)
                               if naive_metrics["token_count"] else float("inf"),
    }
