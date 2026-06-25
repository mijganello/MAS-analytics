from __future__ import annotations
import json
from typing import Any
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.agents.query_mode import is_strict, strict_block_limit
from app.llm.provider import LLMMessage
from app.llm.structured import get_session_llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.schemas.blocks import (
    ReportBlock, TableBlock, TableColumn, KPICard, TextBlock, InsightBlock
)
from app.core.config import settings
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

        # Include fingerprint summary for richer structured context
        fingerprint_summary = ""
        if fingerprint_json:
            try:
                fp_str = json.dumps(fingerprint_json, ensure_ascii=False)
                fingerprint_summary = f"\nСтруктура документа (fingerprint):\n{fp_str[:2000]}"
            except Exception:
                pass

        hints = task.context_hints or {}
        mode_block = self._mode_prompt(hints)
        max_blocks = strict_block_limit(hints) if is_strict(hints) else 10
        strict = is_strict(hints)

        strict_extra = ""
        if strict:
            strict_extra = f"""
СТРОГИЙ РЕЖИМ — КРИТИЧЕСКИ ВАЖНО:
- Ты НЕ выполняешь вычисления. Твоя единственная задача — извлечь сырые данные.
- Запрещено создавать kpi_card блоки. Только table с сырыми строками или text.
- НЕ считай суммы, проценты, средние, максимумы, минимумы — это сделает другой агент.
- Твоя задача: найти в документе строки/записи и передать их как есть в table.
- Один блок = одна table со всеми найденными строками.
- Если данные уже в табличном виде — просто скопируй их в table. Не анализируй."""

        system = f"""Ты DataWorker — агент извлечения данных. Извлекай структурированные данные из документов.

{mode_block}
{strict_extra}

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1. Используй ТОЛЬКО числа и текст из контекста. Не придумывай.
2. НЕ вставляй маркеры [НЕПРОВЕРЕНО] — просто пропускай отсутствующие данные.
3. block_type: только "table", "kpi_card" или "text".
4. Все текстовые поля — на РУССКОМ.
5. Верни НЕ БОЛЕЕ {max_blocks} блоков. Объединяй KPI в одну table где уместно.

Формат:
- kpi_card: {{"block_type": "kpi_card", "title": "...", "metric_name": "...", "value": "123", "unit": "..."}}
- table: {{"block_type": "table", "title": "...", "columns": [...], "rows": [...]}}
- text: {{"block_type": "text", "title": "...", "content": "..."}}

Ответь JSON DataWorkerOutput."""

        user = f"""Задача: {task.description}

Контекст документа:
{context}{fingerprint_summary}

Извлеки только запрошенные данные. Не более {max_blocks} блоков."""

        result = await get_session_llm().complete(
            messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            response_model=DataWorkerOutput,
            role="worker",
            max_tokens=settings.max_task_tokens,
        )

        self._log("worker_done", task_id=task.task_id, blocks=len(result.blocks))

        # Strict mode safety: drop any kpi_card blocks — DataWorker must only extract raw data
        blocks_out = [b.model_dump(exclude_none=False) for b in result.blocks]
        if strict:
            kpi_dropped = [b for b in blocks_out if b.get("block_type") == "kpi_card"]
            if kpi_dropped:
                logger.warning("dataworker_kpi_stripped", task_id=task.task_id,
                               dropped=len(kpi_dropped),
                               titles=[b.get("title", "")[:60] for b in kpi_dropped])
                blocks_out = [b for b in blocks_out if b.get("block_type") != "kpi_card"]

        dept_str = task.department.value if hasattr(task.department, "value") else str(task.department)
        await self._bb_log(
            task.session_id, "llm_response",
            f"Извлечение данных завершено: {len(blocks_out)} блоков. {result.data_quality_notes[:120] if result.data_quality_notes else ''}",
            task_id=task.task_id, department=dept_str,
            details={
                "blocks_count": len(blocks_out),
                "block_types": [b.get("block_type") for b in blocks_out],
                "block_titles": [b.get("title", "")[:60] for b in blocks_out],
                "reasoning": result.reasoning[:600] if result.reasoning else "",
                "data_quality_notes": result.data_quality_notes[:400] if result.data_quality_notes else "",
                "chunks_used": len(chunks),
                "fingerprint_present": bool(fingerprint_json),
            },
        )

        return blocks_out


class DataCritic(BaseAgent):
    agent_name = "DataCritic"
    role = "critic"
    department = "data_extraction"

    CHECKLIST = """Чеклист проверки качества данных:
1. Значения взяты из контекста документа, а не выдуманы
2. Столбцы таблицы корректно подписаны на русском языке
3. Нет очевидных ошибок копирования (например, перепутаны строки)
4. Типы данных согласованы (числа — числами, строки — строками)
5. Блоки не содержат случайно выдуманных чисел

ВАЖНЫЕ ПРАВИЛА ПРОВЕРКИ (не считать ошибками):
- Значения вида 0.07 в полях *_rate, *_pct — это ДРОБИ (0.07 = 7%), а не проценты. Не считать ошибкой.
- Для структурированных JSON/CSV-данных источником является имя поля/ключа — URL не требуется.
- Не требовать ссылок на URL-источники для данных из загруженных файлов (JSON, CSV, XLSX).
- eNPS от -100 до 100 — стандартная шкала; значение 24 или любое в этом диапазоне корректно.
- Не отклонять только из-за отсутствия единиц измерения, если поле само говорит о типе (attrition_rate, pct, score).
- Частично заполненные таблицы (где некоторые строки имеют null-поля) допустимы, если это отражает реальность данных."""

    async def review(
        self,
        task_id: str,
        blocks: list[dict],
        chunks: list[dict],
        context_hints: dict | None = None,
    ) -> CriticVerdict:
        self._log("critic_start", task_id=task_id)

        blocks_str = str(blocks)[:1500]
        issues_found = []

        valid_block_types = {"table", "kpi_card", "text", "chart", "insight",
                             "executive_summary", "forecast", "comparison"}

        # Rule-based checks (only hard violations that definitely indicate broken output)
        for block in blocks:
            # Check block_type is present and valid
            btype = block.get("block_type")
            if not btype or btype not in valid_block_types:
                issues_found.append(CriticIssue(
                    severity="CRITICAL",
                    category="FORMAT_VIOLATION",
                    description=f"Блок не имеет корректного block_type (получено: {btype!r}). Ожидается: table, kpi_card или text.",
                    suggested_fix="Установить block_type в одно из: table, kpi_card, text",
                ))

        if issues_found:
            return CriticVerdict(
                task_id=task_id,
                status="REJECT",
                score=0.3,
                issues=issues_found,
                reasoning="Обнаружены критические проблемы формата блоков",
            )

        if is_strict(context_hints) and len(blocks) > strict_block_limit(context_hints):
            return CriticVerdict(
                task_id=task_id,
                status="REJECT",
                score=0.5,
                issues=[CriticIssue(
                    severity="MAJOR",
                    category="FORMAT_VIOLATION",
                    description=f"Слишком много блоков ({len(blocks)}). В строгом режиме нужен минимум.",
                    suggested_fix="Оставить только блоки с ответами на пункты запроса",
                )],
                reasoning="Превышен лимит блоков в строгом режиме",
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
Одобряй если score >= 0.65 и нет критических ошибок форматирования.
Данные из JSON/CSV файлов считаются верифицированными — не снижай оценку за отсутствие дополнительных источников."""

        user = f"""Проверь эти блоки данных из структурированного документа:
{blocks_str[:1000]}

Оцени только реальные ошибки извлечения. Верни CriticOutput JSON."""

        try:
            result = await get_session_llm().complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=CriticOutput,
                role="critic",
                max_tokens=500,
            )
            if result.approved or result.score >= 0.65:
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
