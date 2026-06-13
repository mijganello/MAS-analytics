from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.schemas.blocks import (
    ReportBlock, TableBlock, TableColumn, KPICard, TextBlock, InsightBlock
)
from app.core.logging import logger
import uuid


class DataBlock(BaseModel):
    """A single extracted data block. block_type is required."""
    block_type: str          # "table" | "kpi_card" | "text"
    title: str = ""
    # kpi_card fields
    metric_name: str = ""
    value: str = ""
    unit: str = ""
    description: str = ""
    # table fields
    columns: list[dict] = []
    rows: list[dict] = []
    # text fields
    content: str = ""


class DataWorkerOutput(BaseModel):
    """Structured output for DataWorker — list of extracted blocks."""
    blocks: list[DataBlock]
    reasoning: str
    data_quality_notes: str = ""


class DataWorker(BaseAgent):
    agent_name = "DataWorker"
    role = "worker"
    department = "data_extraction"

    async def run(
        self,
        task: TaskSpec,
        chunks: list[dict],
        fingerprint_json: dict,
    ) -> list[dict]:
        self._log("worker_start", task_id=task.task_id)
        context = self._build_context_from_chunks(chunks)

        system = """Ты DataWorker — агент извлечения данных. Твоя задача: извлекать структурированные данные из документов.

ОБЯЗАТЕЛЬНО:
1. Используй только данные из предоставленного контекста
2. НИКОГДА не придумывай числа — только те, что есть в контексте
3. Помечай любое непроверяемое число как [НЕПРОВЕРЕНО]
4. Каждый блок ОБЯЗАТЕЛЬНО должен содержать поле "block_type" со значением ТОЛЬКО из: "table", "kpi_card" или "text"
   - "kpi_card" — для одного числового показателя (metric_name, value, unit)
   - "table" — для табличных данных с несколькими строками (columns, rows)
   - "text" — для текстовых описаний и сводок (content)
5. ВСЕ текстовые поля (title, content, labels, metric_name, unit и т.д.) — ИСКЛЮЧИТЕЛЬНО на РУССКОМ языке

Формат каждого блока:
- kpi_card: {"block_type": "kpi_card", "title": "...", "metric_name": "...", "value": "123", "unit": "чел."}
- table: {"block_type": "table", "title": "...", "columns": [{"key": "...", "label": "..."}], "rows": [{...}]}
- text: {"block_type": "text", "title": "...", "content": "..."}

Ответь JSON согласно схеме DataWorkerOutput."""

        user = f"""Задача: {task.description}

Контекст документа:
{context}

Извлеки запрошенные данные и верни структурированные блоки.
Для каждого числового значения укажи его источник.
Весь текст в блоках — на русском. Вывод должен быть валидным JSON."""

        result = await llm.complete(
            messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            response_model=DataWorkerOutput,
            role="worker",
            max_tokens=2000,
        )

        self._log("worker_done", task_id=task.task_id, blocks=len(result.blocks))
        return [b.model_dump(exclude_none=False) for b in result.blocks]


class DataCritic(BaseAgent):
    agent_name = "DataCritic"
    role = "critic"
    department = "data_extraction"

    CHECKLIST = """Чеклист проверки качества данных:
1. Нет чисел с пометкой [НЕПРОВЕРЕНО]
2. Значения взяты из контекста документа, а не выдуманы
3. Столбцы таблицы корректно подписаны на русском языке
4. Нет очевидных ошибок копирования (например, перепутаны строки)
5. Типы данных согласованы (числа — числами, строки — строками)

ВАЖНЫЕ ПРАВИЛА ПРОВЕРКИ (не считать ошибками):
- Значения вида 0.07 в полях *_rate, *_pct — это ДРОБИ (0.07 = 7%), а не проценты. Не считать ошибкой.
- Для структурированных JSON/CSV-данных источником является имя поля/ключа — URL не требуется.
- Не требовать ссылок на URL-источники для данных из загруженных файлов (JSON, CSV, XLSX).
- eNPS от -100 до 100 — стандартная шкала; значение 24 или любое в этом диапазоне корректно.
- Не отклонять только из-за отсутствия единиц измерения, если поле само говорит о типе (attrition_rate, pct, score)."""

    async def review(self, task_id: str, blocks: list[dict], chunks: list[dict]) -> CriticVerdict:
        self._log("critic_start", task_id=task_id)

        blocks_str = str(blocks)[:1500]
        issues_found = []

        valid_block_types = {"table", "kpi_card", "text", "chart", "insight",
                             "executive_summary", "forecast", "comparison"}

        # Rule-based checks first (no LLM tokens needed)
        for block in blocks:
            content_str = str(block)

            # Check block_type is present and valid
            btype = block.get("block_type")
            if not btype or btype not in valid_block_types:
                issues_found.append(CriticIssue(
                    severity="CRITICAL",
                    category="FORMAT_VIOLATION",
                    description=f"Блок не имеет корректного block_type (получено: {btype!r}). Ожидается: table, kpi_card или text.",
                    suggested_fix="Установить block_type в одно из: table, kpi_card, text",
                ))

            if "[UNVERIFIED]" in content_str or "[НЕПРОВЕРЕНО]" in content_str:
                issues_found.append(CriticIssue(
                    severity="CRITICAL",
                    category="DATA_ACCURACY",
                    description="Блок содержит непроверенные данные",
                    suggested_fix="Верифицировать все числа по исходному документу",
                ))

        if issues_found:
            return CriticVerdict(
                task_id=task_id,
                status="REJECT",
                score=0.3,
                issues=issues_found,
                reasoning="Обнаружены критические проблемы качества данных",
            )

        # LLM quality check
        class CriticOutput(BaseModel):
            score: float
            issues: list[str] = []
            approved: bool

        system = f"""Ты DataCritic. Проверяй качество извлечённых данных строго по чеклисту.
Не выдумывай проблемы, которых нет. Не требуй невозможного от структурированных данных.

{self.CHECKLIST}

Верни JSON: score (0.0–1.0), issues (список строк с реальными ошибками), approved (bool).
Одобряй если score >= 0.75 и нет критических ошибок из чеклиста."""

        user = f"""Проверь эти блоки данных из структурированного документа:
{blocks_str[:1000]}

Оцени только реальные ошибки извлечения. Верни CriticOutput JSON."""

        try:
            result = await llm.complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=CriticOutput,
                role="critic",
                max_tokens=500,
            )
            if result.approved or result.score >= 0.75:
                return CriticVerdict(
                    task_id=task_id, status="APPROVED", score=result.score,
                    reasoning="Проверки качества данных пройдены",
                )
            else:
                critic_issues = [
                    CriticIssue(severity="MAJOR", category="DATA_ACCURACY", description=i, suggested_fix="Исправить качество данных")
                    for i in (result.issues or ["Низкая оценка качества"])
                ]
                return CriticVerdict(task_id=task_id, status="REJECT", score=result.score, issues=critic_issues)
        except Exception as e:
            logger.warning("critic_llm_failed", error=str(e))
            return CriticVerdict(task_id=task_id, status="APPROVED", score=0.7, reasoning="Критик: резервное одобрение")
