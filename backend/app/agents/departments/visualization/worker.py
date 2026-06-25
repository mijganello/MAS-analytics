from __future__ import annotations
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.agents.query_mode import is_strict
from app.llm.provider import LLMMessage
from app.llm.structured import get_session_llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.tools.registry import tool_registry
from app.core.logging import logger


def _summarise_data_results(data_results: dict) -> str:
    """Build a compact, LLM-readable summary of all available blocks.

    Table blocks are converted to a concise representation that lists
    column names and shows actual data rows (up to 30) so that the LLM
    has real numbers to embed in chart data.values.

    kpi_card / chart blocks are represented by their key metrics only.
    """
    parts: list[str] = []
    for title, block in data_results.items():
        if not isinstance(block, dict):
            continue
        btype = block.get("block_type", "")

        if btype == "table":
            columns = block.get("columns", [])
            rows = block.get("rows", [])
            if columns:
                col_labels = [c.get("label", c.get("key", "?")) if isinstance(c, dict) else str(c) for c in columns]
            else:
                # Infer columns from first row keys
                col_labels = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
            header = " | ".join(col_labels)
            row_lines = []
            for row in rows[:30]:
                if isinstance(row, dict):
                    row_lines.append(" | ".join(str(v) for v in row.values()))
                elif isinstance(row, list):
                    row_lines.append(" | ".join(str(v) for v in row))
            table_text = header + "\n" + "\n".join(row_lines)
            parts.append(f"[{title} (таблица)]\n{table_text}")

        elif btype == "kpi_card":
            metric = block.get("metric_name", title)
            value = block.get("value")
            unit = block.get("unit", "")
            parts.append(f"[{title} (KPI)]: {metric} = {value} {unit}")

        elif btype == "chart":
            spec = block.get("vega_lite_spec", {})
            vals = spec.get("data", {}).get("values", [])
            parts.append(f"[{title} (график)]: {len(vals)} точек данных")

        else:
            # insight / text — include short preview
            content = block.get("content", block.get("text", ""))
            parts.append(f"[{title} ({btype})]: {str(content)[:200]}")

    return "\n\n".join(parts)[:4000]


class VizWorkerOutput(BaseModel):
    blocks: list[dict]
    reasoning: str = ""


class VizWorker(BaseAgent):
    agent_name = "VizWorker"
    role = "worker"
    department = "visualization"

    async def run(self, task: TaskSpec, data_results: dict) -> list[dict]:
        self._log("worker_start", task_id=task.task_id)
        hints = task.context_hints or {}
        if is_strict(hints) and not hints.get("allow_visualization"):
            return []

        dept_str = task.department.value if hasattr(task.department, "value") else str(task.department)

        # Use tool to suggest chart types
        suggestion: dict = {}
        try:
            suggestion = tool_registry.call(
                "suggest_chart_type",
                data_description=str(list(data_results.keys()))[:300],
                analysis_goal=task.description,
            )
            primary_chart = suggestion.get("primary", "bar")
        except Exception:
            primary_chart = "bar"

        await self._bb_log(
            task.session_id, "tool_call",
            f"Рекомендован тип графика: {primary_chart}. Источников данных: {len(data_results)}",
            task_id=task.task_id, department=dept_str,
            details={
                "chart_suggestion": suggestion,
                "data_sources": list(data_results.keys())[:10],
                "primary_chart_type": primary_chart,
            },
        )

        # Generate Vega-Lite specs via tools for growth-rate series
        chart_blocks = []
        for key, data in data_results.items():
            if isinstance(data, dict) and "period_changes_pct" in data:
                labels = data.get("periods", [])
                values = data.get("period_changes_pct", [])
                if labels and values:
                    try:
                        spec = tool_registry.call(
                            "generate_line_chart_spec",
                            labels=labels, values=values,
                            title=f"Темп роста — {key}",
                            y_label="Изменение %",
                        )
                        chart_blocks.append({
                            "block_type": "chart",
                            "title": f"Темп роста — {key}",
                            "chart_type": "line",
                            "vega_lite_spec": spec,
                            "data_source_description": key,
                        })
                    except Exception as e:
                        logger.warning("viz_chart_failed", error=str(e))

        if not chart_blocks and data_results:
            # Build a compact, human-readable summary with actual row data so the
            # LLM can embed real numbers in data.values (not leave them empty).
            data_summary = _summarise_data_results(data_results)

            mode_block = self._mode_prompt(hints)
            max_charts = 1 if is_strict(hints) else 3

            system = f"""Ты VizWorker — агент визуализации. Создавай блоки-графики с валидными Vega-Lite спецификациями.

{mode_block}

У каждого блока: block_type "chart", title (русский), chart_type, vega_lite_spec с реальными data.values.
Максимум {max_charts} график(ов). Только если графики явно нужны по задаче."""

            user = f"""Задача: {task.description}

Доступные данные (таблицы показаны целиком с реальными значениями):
{data_summary}

Рекомендуемый тип графика: {primary_chart}

Создай до {max_charts} график(ов) строго по задаче."""

            try:
                output = await get_session_llm().complete(
                    messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                    response_model=VizWorkerOutput, role="worker", max_tokens=3000,
                )
                chart_blocks = output.blocks
            except Exception as e:
                logger.error("viz_llm_failed", error=str(e))

        self._log("worker_done", task_id=task.task_id, blocks=len(chart_blocks))

        await self._bb_log(
            task.session_id, "llm_response",
            f"Визуализация завершена: {len(chart_blocks)} график(ов)",
            task_id=task.task_id, department=dept_str,
            details={
                "charts_count": len(chart_blocks),
                "chart_titles": [b.get("title", "")[:60] for b in chart_blocks],
                "chart_types": [b.get("chart_type") for b in chart_blocks],
            },
        )

        return chart_blocks


class VizCritic(BaseAgent):
    agent_name = "VizCritic"
    role = "critic"
    department = "visualization"

    async def review(
        self,
        task_id: str,
        blocks: list[dict],
        context_hints: dict | None = None,
    ) -> CriticVerdict:
        issues = []
        for block in blocks:
            if block.get("block_type") == "chart":
                spec = block.get("vega_lite_spec", {})
                if not spec.get("data") or not spec.get("mark"):
                    issues.append(CriticIssue(
                        severity="CRITICAL", category="FORMAT_VIOLATION",
                        description="Невалидная Vega-Lite спецификация (отсутствует data или mark)",
                        suggested_fix="Добавить data.values и поле mark",
                    ))
                elif not spec.get("data", {}).get("values"):
                    issues.append(CriticIssue(
                        severity="MAJOR", category="MISSING_INFO",
                        description="График содержит пустой массив data.values — нет реальных данных",
                        suggested_fix="Заполнить data.values числами из исходных данных",
                    ))

        if issues:
            return CriticVerdict(task_id=task_id, status="REJECT", score=0.3, issues=issues)
        if is_strict(context_hints) and not (context_hints or {}).get("allow_visualization") and blocks:
            return CriticVerdict(
                task_id=task_id, status="REJECT", score=0.3,
                issues=[CriticIssue(
                    severity="MAJOR", category="FORMAT_VIOLATION",
                    description="Графики не запрашивались",
                    suggested_fix="Удалить chart-блоки",
                )],
            )
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.9, reasoning="Спецификации визуализации проверены")
