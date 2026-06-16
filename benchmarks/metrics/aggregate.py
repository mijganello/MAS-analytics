"""
Aggregate metric computation and scoring.

Retained metrics
----------------
HI  — Hallucination Index     (lower is better)
NPI — Numeric Precision Index (higher is better)  ← NEW
RSS — Response Structure Score (higher is better) ← NEW

Removed metrics (biased or inapplicable for structured block output)
-----------------------------------------------------------------------
FR  — Factual Recall       (regex keyword search unfair to block output)
NA  — Numerical Accuracy   (same issue as FR)
QC  — Query Completeness   (Russian keyword search misses block titles)
BD  — Block Diversity      (MAS-only, no fair Naive equivalent)
SDR — Structured Data Rate (MAS-only)

Score formula (identical for MAS and Naive)
-------------------------------------------
  Score = 0.35 × NPI + 0.35 × RSS + 0.30 × (1 − min(HI, 1))

  All three sub-scores are in [0, 1]; the composite Score is in [0, 1].
  NPI and RSS together represent output *quality* (precision + structure);
  (1 − HI) represents output *trustworthiness* (no invented numbers).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from metrics.hallucination  import hallucination_index, _sample_source_numbers
from metrics.performance    import performance_metrics
from metrics.data_quality   import numeric_precision_index, response_structure_score


def compute_all_metrics(
    response_text:   str,
    ground_truth:    dict,
    latency_seconds: float,
    token_count:     int,
    blocks:          list[dict] | None = None,
    source_file:     Path | None = None,
    is_mas:          bool = True,
) -> dict[str, Any]:
    """
    Compute all metrics for a single benchmark run.

    Args:
        response_text:   Full concatenated response text (from blocks or raw LLM output).
        ground_truth:    Ground-truth dict from *_ground_truth.json.
        latency_seconds: Wall-clock time from first request to final result.
        token_count:     Total tokens used (input + output).
        blocks:          Report blocks list (MAS only; None for Naive).
        source_file:     Path to the original data file (for HI).
        is_mas:          True when evaluating the MAS pipeline.

    Returns:
        Flat dict with all individual metrics and the aggregate score.
    """
    # 1. Hallucination Index
    source_nums = _sample_source_numbers(source_file) if source_file else None
    hi_result   = hallucination_index(response_text, source_file,
                                      source_numbers=source_nums)

    # 2. Numeric Precision Index
    npi_result = numeric_precision_index(response_text)

    # 3. Response Structure Score
    rss_result = response_structure_score(
        response_text,
        blocks=blocks if is_mas else None,
    )

    # 4. Performance metrics
    perf = performance_metrics(latency_seconds, token_count, blocks, is_mas)

    hi  = hi_result["hi"]
    npi = npi_result["npi"]
    rss = rss_result["rss"]

    # Composite score — same formula for both MAS and Naive
    score = round(
        0.35 * npi +
        0.35 * rss +
        0.30 * (1.0 - min(hi, 1.0)),
        4,
    )

    # Efficiency: quality score per log10(tokens) — penalises token waste
    efficiency = round(score / math.log10(max(token_count, 10)), 4)

    return {
        # identity
        "dataset_id":  ground_truth.get("dataset_id", "unknown"),
        "mode":        "mas" if is_mas else "naive",
        # performance
        "latency_s":   perf["latency_s"],
        "token_count": token_count,
        "cost_usd":    perf["cost_usd"],
        # quality metrics
        "npi":         npi,
        "rss":         rss,
        "hi":          hi,
        # composite
        "score":       score,
        "efficiency":  efficiency,
        # detail breakdowns (not in main table; available for debugging)
        "npi_details": {
            "precise_count":   npi_result["precise_count"],
            "candidate_count": npi_result["candidate_count"],
            "total_raw":       npi_result["total_raw"],
            "rounded_samples": npi_result["rounded_samples"],
        },
        "rss_details": rss_result,
        "hi_samples":  hi_result["hallucinated_samples"],
    }


def compare_results(mas_metrics: dict, naive_metrics: dict) -> dict[str, Any]:
    """
    Compute improvement ratios between MAS and Naive for the same dataset.

    All ratios: >1 means MAS is better (except latency/tokens/cost where
    higher means MAS is *more expensive* — so interpret accordingly).
    """
    def ratio(a, b):
        if not isinstance(b, (int, float)) or b == 0:
            return float("inf")
        return round(a / b, 4)

    return {
        "dataset_id":         mas_metrics["dataset_id"],
        # quality improvements (>1 = MAS better)
        "improvement_factor": ratio(mas_metrics["score"],      naive_metrics["score"]),
        "npi_improvement":    ratio(mas_metrics["npi"],        naive_metrics["npi"]),
        "rss_improvement":    ratio(mas_metrics["rss"],        naive_metrics["rss"]),
        "hi_reduction":       ratio(naive_metrics["hi"],       mas_metrics["hi"]),
        # cost of quality (>1 = MAS more expensive)
        "latency_ratio":      ratio(mas_metrics["latency_s"],  naive_metrics["latency_s"]),
        "token_overhead":     ratio(mas_metrics["token_count"],naive_metrics["token_count"]),
        "cost_ratio":         ratio(mas_metrics["cost_usd"],   naive_metrics["cost_usd"]),
        "efficiency_ratio":   ratio(mas_metrics["efficiency"], naive_metrics["efficiency"]),
        # raw scores for the summary table
        "mas_score":          mas_metrics["score"],
        "naive_score":        naive_metrics["score"],
        "mas_npi":            mas_metrics["npi"],
        "naive_npi":          naive_metrics["npi"],
        "mas_rss":            mas_metrics["rss"],
        "naive_rss":          naive_metrics["rss"],
    }
