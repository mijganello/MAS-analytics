from __future__ import annotations
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import llm
from app.schemas.tasks import CriticVerdict, TaskSpec
from app.schemas.report import ReportSchema, ReportMetadata, TOCEntry
from app.core.logging import logger
import uuid
from datetime import datetime


class AssemblyWorkerOutput(BaseModel):
    ordered_blocks: list[dict]
    executive_summary: dict
    toc: list[dict]
    reasoning: str = ""


class AssemblyWorker(BaseAgent):
    agent_name = "AssemblyWorker"
    role = "worker"
    department = "report_assembly"

    async def run(self, task: TaskSpec, all_blocks: list[dict]) -> dict:
        self._log("worker_start", task_id=task.task_id)

        # Order blocks logically without LLM
        type_order = {
            "executive_summary": 0,
            "text": 1,
            "kpi_card": 2,
            "table": 3,
            "chart": 4,
            "forecast": 5,
            "insight": 6,
            "comparison": 7,
        }
        ordered = sorted(all_blocks, key=lambda b: type_order.get(b.get("block_type", "text"), 99))
        for i, block in enumerate(ordered):
            block["order"] = i

        # LLM generates executive summary
        blocks_summary = str([{
            "type": b.get("block_type"), "title": b.get("title", "")
        } for b in ordered])[:800]

        class SummaryOutput(BaseModel):
            key_findings: list[str]
            recommendations: list[str]
            overall_conclusion: str

        system = """Ты AssemblyWorker — агент компиляции отчёта. Создай исполнительное резюме аналитического отчёта.
Будь лаконичен.

ОБЯЗАТЕЛЬНО: все поля (key_findings, recommendations, overall_conclusion) должны быть
ИСКЛЮЧИТЕЛЬНО на РУССКОМ языке. Никаких английских слов или фраз.

Верни JSON с полями:
- key_findings: список из 3–5 ключевых выводов (строки на русском)
- recommendations: список из 2–3 рекомендаций (строки на русском)
- overall_conclusion: общий вывод одним абзацем на русском"""

        user = f"""Запрос к отчёту: {task.description}

Доступные блоки отчёта:
{blocks_summary}

Сгенерируй исполнительное резюме на русском языке."""

        try:
            summary_result = await llm.complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=SummaryOutput, role="worker", max_tokens=800,
            )
            exec_summary = {
                "block_id": str(uuid.uuid4()),
                "block_type": "executive_summary",
                "title": "Исполнительное резюме",
                "order": -1,
                "status": "complete",
                "key_findings": summary_result.key_findings,
                "recommendations": summary_result.recommendations,
                "overall_conclusion": summary_result.overall_conclusion,
                "report_quality_score": 0.8,
                "created_by_dept": "report_assembly",
                "created_at": datetime.utcnow().isoformat(),
                "source_task_ids": [task.task_id],
                "warnings": [],
            }
        except Exception as e:
            logger.warning("assembly_summary_failed", error=str(e))
            exec_summary = {
                "block_id": str(uuid.uuid4()),
                "block_type": "executive_summary",
                "title": "Исполнительное резюме",
                "order": -1,
                "status": "partial",
                "key_findings": ["Отчёт сгенерирован успешно"],
                "recommendations": ["Проверьте данные"],
                "overall_conclusion": "Анализ завершён.",
                "report_quality_score": 0.6,
                "created_by_dept": "report_assembly",
                "created_at": datetime.utcnow().isoformat(),
                "source_task_ids": [task.task_id],
                "warnings": ["Summary generation had issues"],
            }

        # Build TOC
        toc = [
            {"block_id": exec_summary["block_id"], "title": "Исполнительное резюме", "block_type": "executive_summary", "order": -1}
        ] + [
            {"block_id": b.get("block_id", ""), "title": b.get("title", ""), "block_type": b.get("block_type", ""), "order": b.get("order", 0)}
            for b in ordered
        ]

        final_blocks = [exec_summary] + ordered
        for i, b in enumerate(final_blocks):
            b["order"] = i

        self._log("worker_done", task_id=task.task_id, total_blocks=len(final_blocks))
        return {"blocks": final_blocks, "toc": toc}


class AssemblyCritic(BaseAgent):
    agent_name = "AssemblyCritic"
    role = "critic"
    department = "report_assembly"

    async def review(self, task_id: str, report: dict) -> CriticVerdict:
        blocks = report.get("blocks", [])
        if not blocks:
            from app.schemas.tasks import CriticIssue
            return CriticVerdict(
                task_id=task_id, status="REJECT", score=0.0,
                issues=[CriticIssue(severity="CRITICAL", category="MISSING_INFO",
                                    description="Отчёт не содержит блоков", suggested_fix="Добавить блоки отчёта")]
            )
        has_summary = any(b.get("block_type") == "executive_summary" for b in blocks)
        score = 0.9 if has_summary else 0.7
        return CriticVerdict(task_id=task_id, status="APPROVED", score=score, reasoning="Сборка отчёта проверена")
