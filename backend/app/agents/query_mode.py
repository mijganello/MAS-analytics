"""
Query response mode: strict (follow instructions exactly) vs exploratory (full report).

Strict mode is activated when the user gives numbered questions or asks for exact answers.
Exploratory mode is for open-ended "general report" requests without concrete questions.
"""
from __future__ import annotations

import re
from typing import Any


STRICT_SIGNALS = (
    r"(?m)^\s*\d+[\.)]\s",
    r"ответь\s+точно",
    r"ответь\s+на\s+следующ",
    r"следующие\s+вопросы",
    r"точно\s+на\s+следующ",
)

EXPLORATORY_SIGNALS = (
    r"общий\s+отч",
    r"сводн\w*\s+отч",
    r"комплексн\w*\s+анализ",
    r"полный\s+отч",
    r"дай\s+обзор",
    r"подготовь\s+отч",
)

VIZ_KEYWORDS = re.compile(r"график|диаграмм|chart|визуализ|plot", re.I)
QUAL_KEYWORDS = re.compile(
    r"тональност|sentiment|риск\w*|рекомендац|insight|качественн|отзыв\w*\s+текст",
    re.I,
)
FORECAST_KEYWORDS = re.compile(r"прогноз|forecast|тренд\s+на\s+будущ", re.I)


def count_questions(query: str) -> int:
    """Count numbered items or question marks in the query."""
    numbered = re.findall(r"(?m)^\s*\d+[\.)]\s", query)
    if numbered:
        return len(numbered)
    return max(1, query.count("?"))


def classify_query(query: str) -> str:
    """
    Return 'strict' or 'exploratory'.
    """
    q = query.strip()
    if not q:
        return "exploratory"

    has_strict = any(re.search(p, q, re.I) for p in STRICT_SIGNALS)
    has_exploratory = any(re.search(p, q, re.I) for p in EXPLORATORY_SIGNALS)

    if has_strict:
        return "strict"
    if q.count("?") >= 2:
        return "strict"
    if has_exploratory:
        return "exploratory"
    return "exploratory"


def build_context_hints(query: str) -> dict[str, Any]:
    mode = classify_query(query)
    n_q = count_questions(query)
    return {
        "response_mode": mode,
        "user_query": query,
        "question_count": n_q,
        "allow_visualization": bool(VIZ_KEYWORDS.search(query)),
        "allow_qualitative": bool(QUAL_KEYWORDS.search(query)),
        "allow_forecast": bool(FORECAST_KEYWORDS.search(query)),
    }


def is_strict(hints: dict[str, Any] | None) -> bool:
    return (hints or {}).get("response_mode") == "strict"


def strict_block_limit(hints: dict[str, Any] | None) -> int:
    """Max blocks a worker should produce in strict mode."""
    n = (hints or {}).get("question_count", 6)
    return min(max(int(n) + 1, 3), 10)


def strict_mode_instructions(hints: dict[str, Any] | None) -> str:
    if not is_strict(hints):
        return """РЕЖИМ: ОБЩИЙ АНАЛИТИЧЕСКИЙ ОТЧЁТ
- Можно структурировать ответ широко: KPI, таблицы, графики, insights, резюме.
- Добавляй блоки, если они помогают понять данные и ответить на запрос."""

    user_query = (hints or {}).get("user_query", "")
    limit = strict_block_limit(hints)
    extra = []
    if not (hints or {}).get("allow_visualization"):
        extra.append("- НЕ создавай графики/chart — их не просили.")
    if not (hints or {}).get("allow_qualitative"):
        extra.append("- НЕ создавай insight/качественный анализ/риски — их не просили.")
    if not (hints or {}).get("allow_forecast"):
        extra.append("- НЕ создавай forecast/прогнозы — их не просили.")
    extra_rules = "\n".join(extra)

    return f"""РЕЖИМ: СТРОГОЕ СЛЕДОВАНИЕ ИНСТРУКЦИЯМ
- Отвечай ТОЛЬКО на то, что явно запрошено. Ничего «для полноты».
- НЕ добавляй исполнительное резюме, рекомендации, лишние KPI и дубли.
- Один блок = один конкретный ответ на пункт запроса (kpi_card или строка table).
- Максимум {limit} блоков. Лучше меньше, чем больше.
- НЕ повторяй одну метрику в table и kpi_card одновременно.
{extra_rules}

Исходный запрос пользователя:
{user_query}"""


def filter_blocks_for_mode(blocks: list[dict], hints: dict[str, Any] | None) -> list[dict]:
    """Post-filter: drop block types not requested in strict mode."""
    if not is_strict(hints):
        return blocks

    allowed_types = {"table", "kpi_card", "text"}
    if (hints or {}).get("allow_visualization"):
        allowed_types.add("chart")
    if (hints or {}).get("allow_qualitative"):
        allowed_types.add("insight")
    if (hints or {}).get("allow_forecast"):
        allowed_types.add("forecast")

    filtered = [b for b in blocks if b.get("block_type") in allowed_types]
    return filtered[: strict_block_limit(hints)]
