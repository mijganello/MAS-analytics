from __future__ import annotations
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import llm
from app.schemas.tasks import CriticVerdict, CriticIssue, TaskSpec
from app.tools.registry import tool_registry
from app.core.logging import logger


class QualWorkerOutput(BaseModel):
    blocks: list[dict]
    reasoning: str = ""


class QualWorker(BaseAgent):
    agent_name = "QualWorker"
    role = "worker"
    department = "qual_analysis"

    async def run(self, task: TaskSpec, chunks: list[dict]) -> list[dict]:
        self._log("worker_start", task_id=task.task_id)
        context = self._build_context_from_chunks(chunks)

        # Run NLP tools first
        full_text = " ".join(c.get("content", "") for c in chunks[:5])
        nlp_results = {}

        try:
            nlp_results["sentiment"] = tool_registry.call("analyze_sentiment", texts=[full_text[:2000]])
        except Exception:
            pass

        try:
            nlp_results["keywords"] = tool_registry.call("extract_keywords", text=full_text[:2000], method="tfidf", top_k=10)
        except Exception:
            pass

        try:
            nlp_results["summary"] = tool_registry.call("summarize_text_extractive", text=full_text[:3000], max_sentences=5)
        except Exception:
            pass

        try:
            nlp_results["risks"] = tool_registry.call("analyze_risk_factors", text=full_text[:2000])
        except Exception:
            pass

        system = """Ты QualWorker — агент качественного анализа. Создавай блоки отчёта на основе результатов NLP-инструментов.
Доступные типы блоков: "text" и "insight". НЕ используй risk_matrix.
НЕ анализируй текст повторно — используй только предоставленные результаты NLP.

Формат:
- text: {"block_type": "text", "title": "...", "content": "..."}
- insight: {"block_type": "insight", "title": "...", "headline": "...", "explanation": "...", "insight_type": "trend|risk|opportunity|anomaly", "severity": "low|medium|high", "confidence": 0.85}

ОБЯЗАТЕЛЬНО: ВСЕ текстовые поля (title, content, headline, explanation, text, description и т.д.)
должны быть ИСКЛЮЧИТЕЛЬНО на РУССКОМ языке."""

        user = f"""Задача: {task.description}

Результаты NLP-анализа:
{str(nlp_results)[:2000]}

Контекст документа:
{context[:800]}

Создай блоки отчёта. У каждого должно быть поле block_type. Весь текст — на русском."""

        try:
            output = await llm.complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=QualWorkerOutput,
                role="worker",
                max_tokens=2000,
            )
            self._log("worker_done", task_id=task.task_id, blocks=len(output.blocks))
            return output.blocks
        except Exception as e:
            logger.error("qual_worker_failed", error=str(e))
            return []


class QualCritic(BaseAgent):
    agent_name = "QualCritic"
    role = "critic"
    department = "qual_analysis"

    async def review(self, task_id: str, blocks: list[dict]) -> CriticVerdict:
        issues = []
        for block in blocks:
            if block.get("block_type") == "text" and not block.get("content", "").strip():
                issues.append(CriticIssue(
                    severity="MAJOR", category="MISSING_INFO",
                    description="Пустой текстовый блок", suggested_fix="Добавить содержимое",
                ))
            if block.get("block_type") == "insight" and not block.get("headline"):
                issues.append(CriticIssue(
                    severity="MAJOR", category="FORMAT_VIOLATION",
                    description="Блок insight не содержит заголовка", suggested_fix="Добавить headline",
                ))

        if issues:
            return CriticVerdict(task_id=task_id, status="REJECT", score=0.4, issues=issues)
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.82, reasoning="Блоки качественного анализа проверены")
