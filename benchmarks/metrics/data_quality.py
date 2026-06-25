"""
Data-quality metrics for the MAS benchmark.

Two new deterministic metrics that are fair for both MAS and Naive,
require no ground-truth file, and reflect actual output quality:

NPI — Numeric Precision Index
    Fraction of numeric claims that are *exact* (non-rounded) values.
    MAS uses NumericFingerprint to extract exact source values;
    a naive LLM approximates (14 000 instead of 14 066, "8%" instead of 8.4%).
    Range: [0, 1], higher is better.

RSS — Response Structure Score
    How well-organised and multi-dimensional the response is.
    For MAS:   derived from block-type diversity (tables, KPI cards, charts …).
    For Naive: detected from text structure markers (markdown tables, bold
               key-value labels, numbered lists, explicit section headers).
    Range: [0, 1], higher is better.
"""
from __future__ import annotations

import math
import re
from typing import Any


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values ≥ 2 from text (Russian and standard formats).

    Handles:
    - Space / non-breaking-space thousand separators: "1 000 000" → 1000000
    - Comma-as-thousands (unambiguous groups): "15,200,000" → 15200000
      (only when multiple comma-separated 3-digit groups, i.e. classic US thousands)
    - Single comma-separated 3-digit group: "15,200" → 15200 only when
      the pattern is unambiguous (not "3,14" which is European decimal)
    - Decimal comma for single-decimal values: "3,14" → 3.14
    - K / М / M / тыс / млн suffixes: "15.2К" → 15200, "1.5М" → 1500000
    """
    # 1. Non-breaking and hair spaces → regular space for uniform treatment
    text = text.replace('\xa0', ' ').replace('\u202f', ' ')

    # 1b. Drop ISO dates — "2024-06-10" must not yield 2024, 06, 10 as separate numbers
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', text)

    # 1c. Drop numbered-list markers ("1.", "2)") — not data claims
    text = re.sub(r'(?m)^\s*\d+[\.)]\s+', ' ', text)
    text = re.sub(r'(?<=\s)\d+[\.)]\s+(?=\d)', ' ', text)

    # 2. Space-separated thousands: "1 200 345" → "1200345"
    #    Require exactly 3 digits after each space to avoid joining "5 кг" etc.
    text = re.sub(r'(\d) (\d{3})(?!\d)', r'\1\2', text)
    text = re.sub(r'(\d) (\d{3})(?!\d)', r'\1\2', text)   # second pass for 9-digit+ numbers

    # 3. Expand K / M / B / тыс / млн / млрд suffixes before comma stripping
    def _expand_suffix(m: re.Match) -> str:
        num_s  = m.group(1).replace(',', '.')
        suffix = m.group(2).lower()
        mult   = {
            'k': 1_000, 'к': 1_000,
            'тыс': 1_000,
            'м': 1_000_000, 'm': 1_000_000,
            'млн': 1_000_000,
            'b': 1_000_000_000, 'млрд': 1_000_000_000,
        }.get(suffix, 1)
        try:
            v = float(num_s) * mult
            return str(int(v) if v == int(v) else v)
        except ValueError:
            return m.group(0)

    text = re.sub(
        r'(\d+(?:[.,]\d+)?)\s*(млрд|млн|тыс|[KкМмBb])\b',
        _expand_suffix, text, flags=re.IGNORECASE,
    )

    # 4. Comma thousand separators: "15,200,000" or "15,200"
    #    Multi-group (unambiguous): 1+ leading digit + ,DDD + ,DDD … → strip commas
    text = re.sub(r'(\d{1,3})(,\d{3}){2,}', lambda m: m.group(0).replace(',', ''), text)
    #    Single group: X,YYY where YYY is 3 digits and NOT followed by a digit → thousands
    #    But "3,14" (2 digits after comma) is a decimal → don't touch
    text = re.sub(r'(\d{1,3}),(\d{3})(?!\d)', r'\1\2', text)

    # 5. Now extract: integers or decimal-point floats only
    #    (commas that remain are treated as decimal separator: "3,14" → "3.14")
    raw = re.findall(r'\d+(?:[.,]\d+)?', text)
    nums: list[float] = []
    for r in raw:
        try:
            v = float(r.replace(',', '.'))
            if not (math.isnan(v) or math.isinf(v)) and v >= 2:
                nums.append(v)
        except ValueError:
            pass
    return nums


def _is_precise(n: float) -> bool:
    """
    Return True when n looks like an *exact* extracted value, not an
    approximation.

    Only numbers ≥ 100 are evaluated — smaller values (ordinals, ranks,
    small percentages like "top-5", "3 months", "80%") cannot demonstrate
    rounding behaviour in a meaningful way and would inflate NPI for prose
    responses.  This function should be called only after the caller filters
    to n ≥ 100 (and excludes years).

    Rules for integers (n ≥ 100):
        - 100 ≤ n < 1 000    → precise iff n % 10  ≠ 0
        - 1 000 ≤ n < 10 000  → precise iff n % 100 ≠ 0  (4811 yes, 4800 no)
        - 10 000 ≤ n < 100 000 → precise iff n % 1 000 ≠ 0
        - ≥ 100 000            → precise iff n % 10 000 ≠ 0

    Any number with a non-zero decimal part is always precise (8.4, 3.17).
    """
    if n != int(n):        # non-zero decimal → always precise
        return True
    i = int(n)
    mag = 10 ** max(0, int(math.log10(i)) - 1)
    return (i % mag) != 0


# ── NPI ──────────────────────────────────────────────────────────────────────

def numeric_precision_index(response_text: str) -> dict[str, Any]:
    """
    Numeric Precision Index (NPI).

    Measures whether the numeric claims in the response are *exact* values
    extracted from source data or rounded / approximate figures typical of
    LLM prose summaries ("about 14 000" vs "14 066").

    Only numbers ≥ 100 are considered, excluding calendar years (2000–2030).
    Numbers below 100 (ordinals, ranks, small percentages like "top-5",
    "3 months", "80%") cannot show rounding behaviour and would inflate NPI
    equally for both methods, masking the real difference.

    Algorithm:
        1. Extract all numbers from the response text.
        2. Keep only those ≥ 100 and outside the year range [2000, 2030].
        3. Apply _is_precise() to each candidate.
        4. NPI = precise_count / candidate_count  (0.0 if none found)

    Returns:
        npi            float [0, 1]
        precise_count  int
        candidate_count int   (numbers ≥ 100, non-year)
        total_raw      int    (all extracted numbers before filtering)
        rounded_samples list[float]
    """
    all_nums   = _extract_numbers(response_text)
    candidates = [
        n for n in all_nums
        if n >= 100.0 and not (2000.0 <= n <= 2030.0)
    ]

    precise = [n for n in candidates if _is_precise(n)]
    rounded = [n for n in candidates if not _is_precise(n)]

    total = len(candidates)
    npi   = round(len(precise) / total, 4) if total > 0 else 0.0

    return {
        "npi":             npi,
        "precise_count":   len(precise),
        "candidate_count": total,
        "total_raw":       len(all_nums),
        "rounded_samples": rounded[:10],
    }


# ── RSS ──────────────────────────────────────────────────────────────────────

# Block types that carry structured, machine-readable data
_DATA_BLOCK_TYPES = frozenset({
    "table", "kpi_card", "chart", "forecast", "risk_matrix", "comparison",
})
# Block types that add analytical or narrative depth
_ANALYTICAL_BLOCK_TYPES = frozenset({
    "insight", "text", "executive_summary",
})
_ALL_VALUED_TYPES = _DATA_BLOCK_TYPES | _ANALYTICAL_BLOCK_TYPES


def response_structure_score(
    response_text: str,
    blocks: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Response Structure Score (RSS).

    Measures the structural richness and analytical organisation of the output.

    • For MAS (blocks provided):
        RSS = 0.6 × data_coverage + 0.4 × analytical_depth
        data_coverage     = min(1, distinct_data_block_types   / 4)
        analytical_depth  = min(1, distinct_valued_block_types / 5)
        (Ceiling at 1; a report with ≥4 data types + ≥5 total types scores 1.0)

    • For Naive (plain text, no blocks):
        Four structure markers are checked in the text:
          1. Has explicit markdown/ASCII table  (lines with " | ")
          2. Has bold key-value labels          (**Key**: value)
          3. Has numbered or bullet list        (1. … / - … / • …)
          4. Has explicit section headers       (## or **Header**)
        RSS = min(1, (sum of present markers) / 4)

    Returns:
        rss            float [0, 1]
        details        dict   — breakdown of what was detected
        is_mas         bool
    """
    # ── MAS path ─────────────────────────────────────────────────────────
    if blocks:
        block_types = [b.get("block_type", "unknown") for b in blocks]
        distinct_data       = len(set(block_types) & _DATA_BLOCK_TYPES)
        distinct_all_valued = len(set(block_types) & _ALL_VALUED_TYPES)

        data_coverage    = min(1.0, distinct_data       / 4)
        analytical_depth = min(1.0, distinct_all_valued / 5)

        rss = round(0.6 * data_coverage + 0.4 * analytical_depth, 4)

        return {
            "rss":             rss,
            "is_mas":          True,
            "data_coverage":   round(data_coverage, 4),
            "analytical_depth":round(analytical_depth, 4),
            "distinct_data_types":    distinct_data,
            "distinct_valued_types":  distinct_all_valued,
            "block_type_counts": {bt: block_types.count(bt) for bt in set(block_types)},
        }

    # ── Naive path ───────────────────────────────────────────────────────
    text = response_text

    has_table   = bool(re.search(r'\|.+\|', text))                      # " | "
    has_bold_kv = bool(re.search(r'\*\*[^*]{2,40}\*\*\s*[:\-]', text)) # **Key**:
    has_list    = bool(re.search(                                        # 1. / - / •
        r'(?m)^[\s]*(?:\d+\.|[-•*])\s+\S', text
    ))
    has_headers = bool(re.search(                                        # ## or **Header**
        r'(?m)^#{2,4}\s+\S|^\*{2}[А-ЯA-Z][^*]{3,50}\*{2}\s*$', text
    ))

    markers    = [has_table, has_bold_kv, has_list, has_headers]
    rss        = round(sum(markers) / 4, 4)

    return {
        "rss":         rss,
        "is_mas":      False,
        "has_table":   has_table,
        "has_bold_kv": has_bold_kv,
        "has_list":    has_list,
        "has_headers": has_headers,
    }
