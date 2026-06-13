from __future__ import annotations
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.tools.registry import tool_registry
from app.core.logging import logger


class VizWorkerOutput(BaseModel):
    blocks: list[dict]
    reasoning: str = ""


class VizWorker(BaseAgent):
    agent_name = "VizWorker"
    role = "worker"
    department = "visualization"

    async def run(self, task: TaskSpec, data_results: dict) -> list[dict]:
        self._log("worker_start", task_id=task.task_id)

        # Use tool to suggest chart types
        try:
            suggestion = tool_registry.call(
                "suggest_chart_type",
                data_description=str(data_results)[:300],
                analysis_goal=task.description,
            )
            primary_chart = suggestion.get("primary", "bar")
        except Exception:
            primary_chart = "bar"

        # Generate Vega-Lite specs via tools
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
            system = """Ты VizWorker — агент визуализации. Создавай блоки-графики с валидными Vega-Lite спецификациями.

У каждого блока ОБЯЗАТЕЛЬНО должно быть:
- block_type: "chart"
- title: название графика (русский)
- chart_type: "bar" | "line" | "area" | "pie"
- vega_lite_spec: валидный Vega-Lite JSON со структурой:
  {
    "mark": "bar",          // bar | line | area | arc (для pie)
    "data": {"values": [...]},
    "encoding": {
      "x": {"field": "название_поля", "type": "nominal|temporal|ordinal"},
      "y": {"field": "название_поля", "type": "quantitative"}
    }
  }

КРИТИЧЕСКИ ВАЖНО:
1. data.values ДОЛЖЕН содержать реальные числа из предоставленных данных (не пустой массив)
2. Поля в encoding.x.field и encoding.y.field ДОЛЖНЫ совпадать с ключами в data.values
3. Для временных рядов используй mark: "line" или "area"
4. Для сравнения категорий используй mark: "bar"
5. Для долей используй mark: "arc" (pie chart)
6. Все title и текстовые поля — ИСКЛЮЧИТЕЛЬНО на РУССКОМ языке"""

            user = f"""Задача: {task.description}
Доступные данные: {str(data_results)[:2000]}
Рекомендуемый тип: {primary_chart}

Создай 1-3 блока с графиками. Каждый vega_lite_spec.data.values должен содержать числа из данных выше."""

            try:
                output = await llm.complete(
                    messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                    response_model=VizWorkerOutput, role="worker", max_tokens=2000,
                )
                chart_blocks = output.blocks
            except Exception as e:
                logger.error("viz_llm_failed", error=str(e))

        self._log("worker_done", task_id=task.task_id, blocks=len(chart_blocks))
        return chart_blocks


class VizCritic(BaseAgent):
    agent_name = "VizCritic"
    role = "critic"
    department = "visualization"

    async def review(self, task_id: str, blocks: list[dict]) -> CriticVerdict:
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

        if issues:
            return CriticVerdict(task_id=task_id, status="REJECT", score=0.3, issues=issues)
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.9, reasoning="Спецификации визуализации проверены")
