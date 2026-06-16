"""
Performance metrics: latency, token count, cost, block statistics (MAS-only).
"""
import math
from typing import Any


# DeepSeek pricing (USD per 1M tokens, as of 2025)
DEEPSEEK_PRICE_IN_PER_M  = 0.27   # deepseek-chat input
DEEPSEEK_PRICE_OUT_PER_M = 1.10   # deepseek-chat output
DEEPSEEK_REASONER_IN     = 0.55   # deepseek-reasoner input
DEEPSEEK_REASONER_OUT    = 2.19   # deepseek-reasoner output


def performance_metrics(
    latency_seconds: float,
    token_count: int,
    blocks: list[dict] | None = None,
    is_mas: bool = True,
) -> dict[str, Any]:
    """
    Compute performance and structural metrics.

    Args:
        latency_seconds: Wall-clock time from request to completion.
        token_count: Total tokens used (in + out combined estimate).
        blocks: List of report blocks (MAS only). None for naive baseline.
        is_mas: True if this is MAS pipeline result.

    Returns:
        dict with all performance metrics.
    """
    # Cost estimate: assume 60% in tokens, 40% out (mix of chat + reasoner)
    tokens_in  = int(token_count * 0.60)
    tokens_out = int(token_count * 0.40)
    cost_usd   = round(
        (tokens_in  / 1_000_000 * DEEPSEEK_PRICE_IN_PER_M) +
        (tokens_out / 1_000_000 * DEEPSEEK_PRICE_OUT_PER_M),
        6
    )

    result: dict[str, Any] = {
        "latency_s":    round(latency_seconds, 2),
        "token_count":  token_count,
        "cost_usd":     cost_usd,
    }

    if is_mas and blocks:
        block_types = [b.get("block_type", "unknown") for b in blocks]
        type_counts: dict[str, int] = {}
        for bt in block_types:
            type_counts[bt] = type_counts.get(bt, 0) + 1

        # Shannon entropy (normalized)
        n = len(block_types)
        unique = len(type_counts)
        if n > 0 and unique > 1:
            entropy = -sum(
                (c / n) * math.log2(c / n) for c in type_counts.values() if c > 0
            )
            bd = round(entropy / math.log2(max(unique, 2)), 4)
        else:
            bd = 0.0

        # Structured Data Rate: blocks with actual data (not text/narrative)
        data_block_types = {"table", "kpi_card", "chart", "forecast", "risk_matrix"}
        sdr = round(
            sum(1 for bt in block_types if bt in data_block_types) / max(n, 1),
            4
        )

        result.update({
            "block_count":       n,
            "block_types":       type_counts,
            "block_diversity":   bd,
            "structured_rate":   sdr,
            "tokens_per_block":  round(token_count / max(n, 1), 1),
            "cost_per_block":    round(cost_usd / max(n, 1), 6),
        })
    else:
        result.update({
            "block_count":     0,
            "block_diversity": 0.0,
            "structured_rate": 0.0,
        })

    return result
