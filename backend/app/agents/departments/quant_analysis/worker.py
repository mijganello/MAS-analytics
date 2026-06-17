from __future__ import annotations
import re
from typing import Any
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import get_session_llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.tools.registry import tool_registry
from app.core.logging import logger


def _is_timestamp(value: str) -> bool:
    """Return True for ISO-like timestamps (2025-01-01, 2024-12-31T…)."""
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}', value.strip()))


def _try_float(s: str) -> float | None:
    """Parse a cell value as float; return None on failure."""
    s = s.strip()
    if not s or s in ('-', 'n/a', 'null', 'none', '—', 'н/а'):
        return None
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


def _extract_pipe_table(lines: list[str], series: dict[str, list[float]]) -> None:
    """Parse a pipe-delimited table, adding each numeric column to *series*.

    Timestamps (values matching \\d{4}-\\d{2}-\\d{2}…) are skipped so that
    years like 2025 from ISO timestamps are never mistaken for data values.
    Node-ID and string columns are automatically excluded because they
    cannot be parsed as floats.
    """
    if not lines:
        return
    headers = [h.strip() for h in lines[0].split('|')]

    # Identify numeric columns by probing first 5 data rows
    numeric_cols: set[int] = set()
    for line in lines[1:6]:
        cells = [c.strip() for c in line.split('|')]
        if len(cells) != len(headers):
            continue
        for i, cell in enumerate(cells):
            if _is_timestamp(cell):
                continue
            if _try_float(cell) is not None:
                numeric_cols.add(i)

    # Collect values for those columns
    for line in lines[1:]:
        cells = [c.strip() for c in line.split('|')]
        if len(cells) != len(headers):
            continue
        for i in numeric_cols:
            if i >= len(cells) or i >= len(headers):
                continue
            val = _try_float(cells[i])
            if val is None:
                continue
            col_name = headers[i].lower()[:30]
            series.setdefault(col_name, []).append(val)


def _extract_free_text(content: str, series: dict[str, list[float]]) -> None:
    """Extract label→number pairs from free text, one line at a time.

    Deliberately restricted to single lines so that year numbers in
    ISO timestamps on the *next* line are never pulled into a preceding
    label's values (the old bug: 'anomaly\\n2025-01-01' → series[anomaly]=[2025]).
    """
    number_pattern = re.compile(
        r'([A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ\w_]{1,29}?)[\s:=]+(\d[\d,.]*)',
    )
    for line in content.splitlines():
        for match in number_pattern.finditer(line):
            label = match.group(1).strip().lower()[:30]
            nums = []
            for n in re.findall(r'\d+(?:[.,]\d+)?', match.group(2))[:20]:
                v = _try_float(n)
                if v is not None:
                    nums.append(v)
            if nums:
                series.setdefault(label, []).extend(nums)


def _extract_numeric_series(chunks: list[dict]) -> dict[str, list[float]]:
    """Pre-extract named numeric series from chunks without LLM.

    Dispatches to one of two strategies:
    - Pipe-table chunks (first line contains ' | '): parse as structured table,
      skip timestamp columns to avoid extracting years as metric values.
    - Free-text chunks: regex per-line (single-line only) to avoid year leakage.

    Returns only series with ≥ 2 values, capped at 50 per series.
    """
    series: dict[str, list[float]] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        lines = [l for l in content.strip().splitlines() if l.strip()]
        if len(lines) >= 2 and ' | ' in lines[0]:
            _extract_pipe_table(lines, series)
        else:
            _extract_free_text(content, series)
    return {k: v[:50] for k, v in series.items() if len(v) >= 2}


class QuantWorkerOutput(BaseModel):
    blocks: list[dict]
    calculations_performed: list[str] = []
    reasoning: str = ""


class QuantWorker(BaseAgent):
    agent_name = "QuantWorker"
    role = "worker"
    department = "quant_analysis"

    async def run(self, task: TaskSpec, chunks: list[dict], data_context: dict) -> list[dict]:
        self._log("worker_start", task_id=task.task_id)
        dept_str = task.department.value if hasattr(task.department, "value") else str(task.department)
        context = self._build_context_from_chunks(chunks)

        # ── Step 1: Pre-extract numeric series deterministically ──────────────
        numeric_series = _extract_numeric_series(chunks)
        logger.info("numeric_series_extracted", task_id=task.task_id, series=list(numeric_series.keys()))

        await self._bb_log(
            task.session_id, "tool_call",
            f"Извлечено числовых рядов: {len(numeric_series)} — {', '.join(list(numeric_series.keys())[:6]) or 'нет данных'}",
            task_id=task.task_id, department=dept_str,
            details={
                "numeric_series": {
                    name: {"count": len(vals), "values": vals[:10]}
                    for name, vals in list(numeric_series.items())[:8]
                },
                "chunks_analyzed": len(chunks),
            },
        )

        # ── Step 2: Run math tools directly on extracted data ─────────────────
        calc_results: dict[str, Any] = {}

        for name, values in list(numeric_series.items())[:3]:  # max 3 series
            if len(values) >= 2:
                # Statistics
                try:
                    calc_results[f"stats_{name}"] = tool_registry.call(
                        "calculate_statistics",
                        values=values,
                        metrics=["mean", "min", "max", "std", "p25", "p75"],
                    )
                except Exception as e:
                    logger.warning("stats_tool_failed", series=name, error=str(e))

                # Growth rate
                try:
                    periods = [str(i + 1) for i in range(len(values))]
                    calc_results[f"growth_{name}"] = tool_registry.call(
                        "calculate_growth_rate",
                        values=values,
                        periods=periods,
                    )
                except Exception as e:
                    logger.warning("growth_tool_failed", series=name, error=str(e))

                # Trend
                try:
                    periods = [str(i + 1) for i in range(len(values))]
                    calc_results[f"trend_{name}"] = tool_registry.call(
                        "run_trend_analysis",
                        values=values,
                        periods=periods,
                    )
                except Exception as e:
                    logger.warning("trend_tool_failed", series=name, error=str(e))

        # Outlier detection on first series
        if numeric_series:
            first_name, first_vals = next(iter(numeric_series.items()))
            try:
                calc_results[f"outliers_{first_name}"] = tool_registry.call(
                    "detect_outliers",
                    values=first_vals,
                    method="iqr",
                )
            except Exception as e:
                logger.warning("outlier_tool_failed", error=str(e))

        if calc_results:
            await self._bb_log(
                task.session_id, "tool_call",
                f"Математические инструменты: выполнено {len(calc_results)} вычислений",
                task_id=task.task_id, department=dept_str,
                details={
                    "calculations": {
                        k: (v if isinstance(v, dict) else str(v))
                        for k, v in list(calc_results.items())[:10]
                    },
                },
            )

        # ── Step 3: LLM interprets tool results → creates blocks ──────────────
        class BlocksOutput(BaseModel):
            blocks: list[dict]
            reasoning: str = ""

        system = """Ты QuantWorker. На основе результатов математических инструментов создавай блоки отчёта.
Поддерживаемые типы блоков: chart, kpi_card, table, text, forecast.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
- Для блоков chart: предоставь валидную vega_lite_spec с заполненными data.values; все подписи осей и легенды — на русском
- Для блоков kpi_card: укажи metric_name (на русском), value (float), unit (на русском)
- Для блоков table: columns с label на русском, dtype; rows как список dict
- НЕ придумывай числа — используй только значения из результатов вычислений
- Каждый блок должен содержать: block_type, title (на русском), и специфичные для типа поля
- ВСЕ текстовые поля ИСКЛЮЧИТЕЛЬНО на РУССКОМ языке"""

        calc_summary = str(calc_results)[:3000] if calc_results else "Вычисления не выполнены — недостаточно числовых данных в документе."

        user = f"""Задача: {task.description}

Извлечённые числовые ряды: {list(numeric_series.keys())}

Результаты вычислений (из детерминированных инструментов):
{calc_summary}

Создай 1-3 блока отчёта, наилучшим образом представляющих количественные результаты.
Весь текст — на русском языке."""

        try:
            output = await get_session_llm().complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=BlocksOutput,
                role="worker",
                max_tokens=2000,
            )
            self._log("worker_done", task_id=task.task_id, blocks=len(output.blocks))

            await self._bb_log(
                task.session_id, "llm_response",
                f"Количественный анализ завершён: {len(output.blocks)} блоков",
                task_id=task.task_id, department=dept_str,
                details={
                    "blocks_count": len(output.blocks),
                    "block_types": [b.get("block_type") for b in output.blocks],
                    "block_titles": [b.get("title", "")[:60] for b in output.blocks],
                    "reasoning": output.reasoning[:500] if output.reasoning else "",
                    "series_used": list(numeric_series.keys()),
                },
            )

            return output.blocks
        except Exception as e:
            logger.error("quant_blocks_failed", error=str(e))
            # Fallback: create a simple text block with stats summary
            if calc_results:
                return [{
                    "block_type": "text",
                    "title": "Количественный анализ",
                    "content": f"Анализ выполнен. Извлечено рядов данных: {len(numeric_series)}. "
                               f"Результаты вычислений: {str(calc_results)[:500]}",
                    "style": "body",
                }]
            return []


class QuantCritic(BaseAgent):
    agent_name = "QuantCritic"
    role = "critic"
    department = "quant_analysis"

    async def review(self, task_id: str, blocks: list[dict]) -> CriticVerdict:
        issues = []

        for block in blocks:
            if block.get("block_type") == "chart":
                spec = block.get("vega_lite_spec", {})
                data = spec.get("data", {}).get("values", [])
                if not data:
                    issues.append(CriticIssue(
                        severity="MAJOR", category="MISSING_INFO",
                        description="График не содержит данных",
                        suggested_fix="Заполнить vega_lite_spec.data.values",
                    ))
            if block.get("block_type") == "kpi_card":
                if block.get("value") is None:
                    issues.append(CriticIssue(
                        severity="CRITICAL", category="MISSING_INFO",
                        description="KPI-карточка не содержит числового значения",
                        suggested_fix="Указать числовое поле value",
                    ))

        if issues:
            return CriticVerdict(task_id=task_id, status="REJECT", score=0.4, issues=issues)
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.85, reasoning="Количественные блоки проверены")
