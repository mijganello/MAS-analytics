from __future__ import annotations
import re
from typing import Any
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.agents.query_mode import is_strict, strict_block_limit
from app.agents.departments.quant_analysis.table_metrics import (
    build_computation_table_block,
    collect_table_rows,
)
from app.llm.provider import LLMMessage
from app.llm.structured import get_session_llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.tools.registry import tool_registry
from app.core.logging import logger


class BlocksOutput(BaseModel):
    """Shared structured output for QuantWorker LLM calls."""
    blocks: list[dict]
    reasoning: str = ""


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


# Column names that are row-index / non-metric — skip them when choosing
# series for mathematical analysis.
_INDEX_COLUMNS = frozenset([
    "№", "#", "no", "n", "id", "рейтинг", "rank", "order", "порядок",
    "зач. книжка", "зачетная книжка", "зач.книжка",
])


def _is_index_series(name: str) -> bool:
    """Return True for series that are row numbers or other non-metric identifiers."""
    return name.strip().lower() in _INDEX_COLUMNS


def _extract_numeric_series(chunks: list[dict]) -> dict[str, list[float]]:
    """Pre-extract named numeric series from chunks without LLM.

    Dispatches to one of two strategies:
    - Pipe-table chunks (first line contains ' | '): parse as structured table,
      skip timestamp columns to avoid extracting years as metric values.
    - Free-text chunks: regex per-line (single-line only) to avoid year leakage.

    Returns only series with ≥ 2 values, capped at 50 per series.
    Index/identifier columns (№, рейтинг, etc.) are excluded.
    """
    series: dict[str, list[float]] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        lines = [l for l in content.strip().splitlines() if l.strip()]
        if len(lines) >= 2 and ' | ' in lines[0]:
            _extract_pipe_table(lines, series)
        else:
            _extract_free_text(content, series)
    return {
        k: v[:50]
        for k, v in series.items()
        if len(v) >= 2 and not _is_index_series(k)
    }


def _normalize_quant_blocks(blocks: list[dict]) -> list[dict]:
    """Ensure every block has a valid block_type and required fields."""
    normalized: list[dict] = []
    for raw in blocks:
        block = dict(raw)
        btype = block.get("block_type")
        if not btype:
            if block.get("columns") and block.get("rows"):
                block["block_type"] = "table"
            elif block.get("content"):
                block["block_type"] = "text"
            elif block.get("value") is not None or block.get("metric_name"):
                block["block_type"] = "kpi_card"
            elif block.get("title") and any(k in block for k in ("value", "metric_name")):
                block["block_type"] = "kpi_card"
            else:
                continue

        if block["block_type"] == "kpi_card":
            block.setdefault("metric_name", block.get("title", ""))
            if block.get("value") is not None:
                block["value"] = str(block["value"])
        normalized.append(block)
    return normalized


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

        hints = task.context_hints or {}
        table_rows = collect_table_rows(chunks, data_context)

        # Strict mode: deterministic computation + LLM formatting into answer KPI cards
        if is_strict(hints):
            strict_block = build_computation_table_block(table_rows)
            if not strict_block:
                return []

            metrics_rows = strict_block.get("rows", [])
            await self._bb_log(
                task.session_id, "tool_call",
                f"Строгий режим: {len(table_rows)} строк → {len(metrics_rows)} метрик",
                task_id=task.task_id, department=dept_str,
                details={"row_count": len(table_rows), "metrics_count": len(metrics_rows)},
            )

            # Format answers as KPI cards using LLM (values from deterministic computation)
            user_query = hints.get("user_query", task.description)
            metrics_text = "\n".join(
                f"{r['metric']}: {r['value']}" for r in metrics_rows[:80]
            )

            kpi_blocks = await self._format_strict_answers(user_query, metrics_text, task)
            if kpi_blocks:
                self._log("worker_done", task_id=task.task_id, blocks=len(kpi_blocks), mode="strict_kpi")
                return kpi_blocks

            # Fallback: return computation table (but mark it so assembly can handle)
            self._log("worker_done", task_id=task.task_id, blocks=1, mode="strict_fallback_table")
            return [strict_block]

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
                # Statistics (include sum — needed for totals, not just means)
                try:
                    calc_results[f"stats_{name}"] = tool_registry.call(
                        "calculate_statistics",
                        values=values,
                        metrics=["sum", "mean", "min", "max", "std", "count"],
                    )
                except Exception as e:
                    logger.warning("stats_tool_failed", series=name, error=str(e))

                if not is_strict(hints):
                    # Growth/trend only for exploratory reports
                    try:
                        periods = [str(i + 1) for i in range(len(values))]
                        calc_results[f"growth_{name}"] = tool_registry.call(
                            "calculate_growth_rate",
                            values=values,
                            periods=periods,
                        )
                    except Exception as e:
                        logger.warning("growth_tool_failed", series=name, error=str(e))

                    try:
                        periods = [str(i + 1) for i in range(len(values))]
                        calc_results[f"trend_{name}"] = tool_registry.call(
                            "run_trend_analysis",
                            values=values,
                            periods=periods,
                        )
                    except Exception as e:
                        logger.warning("trend_tool_failed", series=name, error=str(e))

        # Outlier detection on first series (exploratory only)
        if numeric_series and not is_strict(hints):
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

        mode_block = self._mode_prompt(hints)
        max_blocks = strict_block_limit(hints) if is_strict(hints) else 3

        system = f"""Ты QuantWorker. Создавай блоки на основе результатов математических инструментов.

{mode_block}

Поддерживаемые типы: kpi_card, table, text (chart/forecast — только если явно запрошены).
- Каждый блок ОБЯЗАН содержать поле "block_type"
- kpi_card: {{"block_type": "kpi_card", "title": "...", "metric_name": "...", "value": "123", "unit": "..."}}
- table: {{"block_type": "table", "title": "...", "columns": [...], "rows": [...]}}
- НЕ придумывай числа — только из результатов вычислений
- Максимум {max_blocks} блок(ов)
- Все тексты на РУССКОМ"""

        # Build a compact summary: drop list-valued fields (period arrays, fitted
        # values) that blow up the string budget.  Only keep scalar summaries.
        def _compact_results(results: dict) -> str:
            compact: dict = {}
            for key, val in results.items():
                if not isinstance(val, dict):
                    compact[key] = val
                    continue
                # Strip any keys whose value is a list (period_changes_pct,
                # fitted_values, periods, outliers …) — keep only scalars.
                compact[key] = {k: v for k, v in val.items() if not isinstance(v, list)}
            return str(compact)[:4000]

        calc_summary = (
            _compact_results(calc_results)
            if calc_results
            else "Вычисления не выполнены — недостаточно числовых данных в документе."
        )

        user = f"""Задача: {task.description}

Извлечённые числовые ряды: {list(numeric_series.keys())}

Результаты вычислений (из детерминированных инструментов):
{calc_summary}

Создай до {max_blocks} блок(ов) строго по задаче. Без лишней аналитики."""

        try:
            output = await get_session_llm().complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=BlocksOutput,
                role="worker",
                max_tokens=2000,
            )
            blocks = _normalize_quant_blocks(output.blocks)
            if not blocks and table_rows:
                fallback = build_computation_table_block(table_rows)
                if fallback:
                    blocks = [fallback]

            self._log("worker_done", task_id=task.task_id, blocks=len(blocks))

            await self._bb_log(
                task.session_id, "llm_response",
                f"Количественный анализ завершён: {len(blocks)} блоков",
                task_id=task.task_id, department=dept_str,
                details={
                    "blocks_count": len(blocks),
                    "block_types": [b.get("block_type") for b in blocks],
                    "block_titles": [b.get("title", "")[:60] for b in blocks],
                    "reasoning": output.reasoning[:500] if output.reasoning else "",
                    "series_used": list(numeric_series.keys()),
                },
            )

            return blocks
        except Exception as e:
            logger.error("quant_blocks_failed", error=str(e))
            if table_rows:
                fallback = build_computation_table_block(table_rows)
                if fallback:
                    return [fallback]
            if calc_results:
                return [{
                    "block_type": "text",
                    "title": "Количественный анализ",
                    "content": f"Анализ выполнен. Извлечено рядов данных: {len(numeric_series)}. "
                               f"Результаты вычислений: {str(calc_results)[:500]}",
                    "style": "body",
                }]
            return []

    async def _format_strict_answers(
        self, user_query: str, metrics_text: str, task: TaskSpec
    ) -> list[dict]:
        """In strict mode, format deterministic computation results as KPI cards
        that answer the user's specific questions.  The LLM is only used for
        question→metric matching; all numeric values come from the tool output."""
        from app.agents.query_mode import count_questions

        n_questions = count_questions(user_query)
        max_blocks = min(n_questions + 1, 10)

        system = f"""Ты — агент форматирования ответов. Твоя задача: на каждый вопрос пользователя дать ОДИН блок kpi_card с ТОЧНЫМ значением из RESULTS.

ПРАВИЛА (нарушение — ошибка):
1. Значения бери ТОЛЬКО из RESULTS ниже. НЕ вычисляй, НЕ округляй, НЕ меняй.
2. Один вопрос = один kpi_card блок.
3. Каждый блок ОБЯЗАН содержать поля: block_type, title, metric_name, value, unit.
4. Не добавляй блоков «для полноты». Ровно столько, сколько вопросов.
5. Все тексты на РУССКОМ.
6. Верни НЕ БОЛЕЕ {max_blocks} блоков.

Формат kpi_card:
{{"block_type": "kpi_card", "title": "краткий заголовок", "metric_name": "название метрики", "value": "число из RESULTS", "unit": "единицы"}}"""

        user = f"""Вопросы пользователя:
{user_query}

RESULTS (точные значения из инструментов):
{metrics_text}

На каждый вопрос создай один kpi_card с ТОЧНЫМ значением из RESULTS. Не добавляй лишнего."""

        try:
            output = await get_session_llm().complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=BlocksOutput,
                role="worker",
                max_tokens=2000,
                temperature=0.0,  # zero temperature for deterministic mapping
            )
            blocks = _normalize_quant_blocks(output.blocks)
            # Keep only kpi_card blocks — table/text are not answers in strict mode
            blocks = [b for b in blocks if b.get("block_type") == "kpi_card"]
            if blocks:
                return blocks[:max_blocks]
        except Exception as e:
            logger.warning("strict_kpi_formatting_failed", error=str(e), task_id=task.task_id)

        return []


class QuantCritic(BaseAgent):
    agent_name = "QuantCritic"
    role = "critic"
    department = "quant_analysis"

    async def review(
        self,
        task_id: str,
        blocks: list[dict],
        context_hints: dict | None = None,
    ) -> CriticVerdict:
        issues = []

        if not blocks:
            if is_strict(context_hints):
                return CriticVerdict(
                    task_id=task_id, status="REJECT", score=0.2,
                    issues=[CriticIssue(
                        severity="CRITICAL", category="MISSING_INFO",
                        description="Нет блоков с вычислениями в строгом режиме",
                        suggested_fix="Вернуть table/kpi_card с агрегатами",
                    )],
                )
            return CriticVerdict(task_id=task_id, status="APPROVED", score=0.5,
                                 reasoning="Нет количественных блоков")

        for block in blocks:
            if not block.get("block_type"):
                issues.append(CriticIssue(
                    severity="CRITICAL", category="FORMAT_VIOLATION",
                    description="Блок без block_type",
                    suggested_fix='Добавить block_type: "kpi_card", "table" или "text"',
                ))
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
                if block.get("value") is None or str(block.get("value", "")).strip() == "":
                    issues.append(CriticIssue(
                        severity="CRITICAL", category="MISSING_INFO",
                        description="KPI-карточка не содержит числового значения",
                        suggested_fix="Указать числовое поле value",
                    ))

        if issues:
            return CriticVerdict(task_id=task_id, status="REJECT", score=0.4, issues=issues)
        if is_strict(context_hints) and len(blocks) > strict_block_limit(context_hints):
            return CriticVerdict(
                task_id=task_id, status="REJECT", score=0.5,
                issues=[CriticIssue(
                    severity="MAJOR", category="FORMAT_VIOLATION",
                    description="Слишком много quant-блоков для строгого запроса",
                    suggested_fix="Оставить один блок с ключевыми вычислениями",
                )],
            )
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.85, reasoning="Количественные блоки проверены")
