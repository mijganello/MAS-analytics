"""
Hallucination Index (HI) metric.

Approximates the fraction of numeric claims in the response that do not
correspond to any value in a sample from the source file.

Deterministic: compares extracted numbers against source file values.
"""
import re
import math
import csv
import json
from pathlib import Path
from typing import Union


def _extract_numbers(text: str) -> list[float]:
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    raw  = re.findall(r'\d+(?:[.,]\d+)?', text)
    result = []
    for r in raw:
        try:
            v = float(r.replace(',', '.'))
            if not math.isnan(v) and not math.isinf(v) and v > 0:
                result.append(v)
        except ValueError:
            pass
    return result


def _sample_source_numbers(file_path: Path, max_values: int = 5000) -> set[float]:
    """Extract a sample of numeric values from the source file."""
    suffix = file_path.suffix.lower()
    numbers: set[float] = set()

    try:
        if suffix == ".csv":
            with open(file_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for i, row in enumerate(reader):
                    if len(numbers) >= max_values:
                        break
                    for cell in row:
                        try:
                            v = float(cell.replace(',', '.').strip())
                            if not math.isnan(v) and not math.isinf(v) and v > 0:
                                numbers.add(round(v, 2))
                        except ValueError:
                            pass
                    # Sample every Nth row for large files
                    if i > 0 and i % 10 != 0:
                        continue

        elif suffix == ".json":
            content = file_path.read_text(encoding="utf-8")
            raw = re.findall(r'\d+(?:\.\d+)?', content)
            for r in raw[:max_values]:
                try:
                    v = float(r)
                    if not math.isnan(v) and v > 0:
                        numbers.add(round(v, 2))
                except ValueError:
                    pass

        elif suffix == ".txt":
            content = file_path.read_text(encoding="utf-8")
            raw = re.findall(r'\d+(?:\.\d+)?', content)
            for r in raw[:max_values]:
                try:
                    v = float(r)
                    if not math.isnan(v) and v > 0:
                        numbers.add(round(v, 2))
                except ValueError:
                    pass
    except Exception:
        pass

    return numbers


def _in_source(value: float, source_numbers: set[float], tolerance: float = 0.02) -> bool:
    """Check if value is close to any number in source."""
    for sv in source_numbers:
        if sv == 0:
            continue
        if abs(value - sv) / max(abs(sv), 1e-9) <= tolerance:
            return True
    return False


def hallucination_index(
    response_text: str,
    source_file: Union[Path, None],
    source_numbers: Union[set[float], None] = None,
    tolerance: float = 0.02,
    min_value: float = 2.0,  # ignore trivial numbers like 1, 2, 3
) -> dict:
    """
    Compute Hallucination Index.

    Args:
        response_text: Full response text.
        source_file: Path to the source data file (used to extract reference numbers).
        source_numbers: Pre-computed set of source numbers (optional, avoids re-reading).
        tolerance: Relative tolerance for matching.
        min_value: Only consider numbers >= min_value (ignore ordinals like 1, 2, 3...).

    Returns:
        dict with hi (float [0,1]), hallucinated_count, total_response_numbers, details.
    """
    if source_numbers is None and source_file is not None:
        source_numbers = _sample_source_numbers(source_file)
    source_numbers = source_numbers or set()

    # Add common "safe" numbers that don't require source verification
    # (percentages, round numbers that appear in any context)
    safe_ranges = [(0, 100)]  # percentages

    resp_numbers = _extract_numbers(response_text)
    # Filter: only consider numbers above min_value
    resp_numbers = [v for v in resp_numbers if v >= min_value]

    hallucinated = []
    verified     = []

    for v in resp_numbers:
        in_src = _in_source(v, source_numbers, tolerance)
        # Also check if it could be a computed aggregate (rounded)
        rounded_variants = {
            round(v), round(v, 1), round(v, 2),
            round(v / 100, 4) * 100,   # percentage
            round(v * 1000),            # thousands
            round(v / 1000, 2),         # /1000
        }
        in_src_variant = any(_in_source(rv, source_numbers, tolerance * 2)
                              for rv in rounded_variants)

        if in_src or in_src_variant:
            verified.append(v)
        else:
            hallucinated.append(v)

    total = len(resp_numbers)
    hi    = round(len(hallucinated) / (total + 1), 4)  # +1 to avoid div/0

    return {
        "hi":                   hi,
        "hallucinated_count":   len(hallucinated),
        "verified_count":       len(verified),
        "total_response_numbers": total,
        "hallucinated_samples": hallucinated[:10],  # first 10 for inspection
    }
