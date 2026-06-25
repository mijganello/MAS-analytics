"""
Hallucination Index (HI) metric — simplified.

HI measures the fraction of numeric claims in the response that are NOT
traceable to the expected ground-truth answers.  Only the fixture's
*expected_numbers* are considered «correct»; any other numeric claim
(aggregate, intermediate value, raw cell value, etc.) counts as a
hallucination for the purpose of this metric.

  HI = hallucinated_count / (total_response_numbers + 1)   → [0, 1), lower is better

Rationale
---------
On large datasets (1 000+ rows) the old source-grounded approach produced
verified sets that were too large (every raw cell value + every aggregate),
making HI trivially low and not useful for comparing MAS vs Naive.

By restricting the «allowed» set to the fixture's declared answers we get
a meaningful signal: the response should stick to answering the query,
not flood the user with irrelevant numbers.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Union


# ── text → numbers ────────────────────────────────────────────────────────────

def _strip_list_markers(text: str) -> str:
    """Remove numbered-list prefixes ('1.', '2)') so they are not counted as data."""
    text = re.sub(r"(?m)^\s*\d+[\.)]\s+", " ", text)
    text = re.sub(r"(?<=\s)\d+[\.)]\s+(?=\d)", " ", text)
    return text


def _extract_numbers(text: str) -> list[float]:
    """Extract positive numeric values from text, skipping ISO-date fragments."""
    text = _strip_list_markers(text)
    # Drop YYYY-MM-DD so "2024-06-10" does not yield 2024, 06, 10 as separate claims
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    # Thousand separators (space between digit groups)
    text = re.sub(r"(\d) (\d{3})(?!\d)", r"\1\2", text)
    # K/M/B/тыс/млн/млрд suffixes → raw integer strings
    def _expand_suffix(m: re.Match) -> str:
        num_s  = m.group(1).replace(',', '.')
        suffix = m.group(2).lower()
        mult   = {
            'k': 1_000, 'к': 1_000, 'тыс': 1_000,
            'м': 1_000_000, 'm': 1_000_000, 'млн': 1_000_000,
            'b': 1_000_000_000, 'млрд': 1_000_000_000,
        }.get(suffix, 1)
        try:
            v = float(num_s) * mult
            return str(int(v) if v == int(v) else v)
        except ValueError:
            return m.group(0)
    text = re.sub(
        r'(\d+(?:[.,]\d+)?)\s*(млрд|млн|тыс|[KkМмBb])\b',
        _expand_suffix, text, flags=re.IGNORECASE,
    )
    result = []
    for r in re.findall(r'\d+(?:[.,]\d+)?', text):
        try:
            v = float(r.replace(',', '.'))
            if not math.isnan(v) and not math.isinf(v) and v > 0:
                result.append(v)
        except ValueError:
            pass
    return result


# ── verified set (expected answers only) ──────────────────────────────────────

def _build_verified_from_expected(
    ground_truth_numbers: list[dict] | None,
) -> set[float]:
    """Build verified set ONLY from declared expected answers.

    Adds each value rounded to several precisions so that the tolerance
    check is robust even when the LLM reports "83.33" vs expected "83.3333".
    """
    verified: set[float] = set()
    if not ground_truth_numbers:
        return verified
    for item in ground_truth_numbers:
        try:
            v = float(item["value"])
            if math.isnan(v) or math.isinf(v) or v <= 0:
                continue
            verified.add(round(v, 4))
            verified.add(round(v, 2))
            verified.add(round(v, 1))
            verified.add(round(v))
        except (KeyError, TypeError, ValueError):
            pass
    return verified


# ── matching ──────────────────────────────────────────────────────────────────

def _in_expected(value: float, verified: set[float], tolerance: float = 0.02) -> bool:
    """Return True when *value* is within relative tolerance of any verified number."""
    for sv in verified:
        if sv == 0:
            continue
        if abs(value - sv) / max(abs(sv), 1e-9) <= tolerance:
            return True
    return False


# ── public API ────────────────────────────────────────────────────────────────

def hallucination_index(
    response_text: str,
    source_file: Union[Path, None] = None,
    source_numbers: Union[set[float], None] = None,
    ground_truth_numbers: Union[list[dict], None] = None,
    tolerance: float = 0.02,
    min_value: float = 2.0,
    strict_expected_only: bool = False,
) -> dict:
    """
    Compute Hallucination Index (HI).

    HI = fraction of numeric claims (≥ min_value) in *response_text* that
    do NOT match any expected ground-truth answer within *tolerance*.

    Parameters
    ----------
    response_text : str
        The full text of the LLM response.
    source_file : Path | None
        **Ignored** — kept for backward compatibility only.
    source_numbers : set[float] | None
        **Ignored** — kept for backward compatibility only.
    ground_truth_numbers : list[dict] | None
        List of {"value": <float>, ...} from the fixture's expected_numbers.
    tolerance : float
        Relative tolerance for matching (default 2 %).
    min_value : float
        Numbers below this threshold are ignored (default 2.0).
    strict_expected_only : bool
        **Ignored** — always True in the new implementation.

    Returns
    -------
    dict with keys:
        hi                     — float in [0, 1), lower is better
        hallucinated_count     — int
        verified_count         — int
        total_response_numbers — int
        hallucinated_samples   — list[float] (up to 10)
    """
    verified = _build_verified_from_expected(ground_truth_numbers)

    resp_numbers = [v for v in _extract_numbers(response_text) if v >= min_value]

    hallucinated: list[float] = []
    verified_list: list[float] = []

    for v in resp_numbers:
        if _in_expected(v, verified, tolerance):
            verified_list.append(v)
        else:
            hallucinated.append(v)

    total = len(resp_numbers)
    hi    = round(len(hallucinated) / (total + 1), 4)

    return {
        "hi":                     hi,
        "hallucinated_count":     len(hallucinated),
        "verified_count":         len(verified_list),
        "total_response_numbers": total,
        "hallucinated_samples":   hallucinated[:10],
    }

