from __future__ import annotations
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.agents.query_mode import is_strict, strict_block_limit
from app.llm.provider import LLMMessage
from app.llm.structured import get_session_llm
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
        dept_str = task.department.value if hasattr(task.department, "value") else str(task.department)
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

        if nlp_results:
            sentiment = nlp_results.get("sentiment", {})
            keywords = nlp_results.get("keywords", {})
            risks = nlp_results.get("risks", {})
            sentiment_label = (
                sentiment.get("overall_sentiment") or
                (sentiment[0].get("label") if isinstance(sentiment, list) and sentiment else "н/д")
            )
            kw_list = keywords.get("keywords", keywords) if isinstance(keywords, dict) else keywords
            await self._bb_log(
                task.session_id, "nlp_analysis",
                f"NLP: тональность={sentiment_label}, "
                f"ключевых слов={len(kw_list) if isinstance(kw_list, list) else '?'}, "
                f"рисков={len(risks.get('risks', [])) if isinstance(risks, dict) else '?'}",
                task_id=task.task_id, department=dept_str,
                details={
                    "sentiment": sentiment,
                    "keywords": kw_list[:15] if isinstance(kw_list, list) else kw_list,
                    "extractive_summary": nlp_results.get("summary", ""),
                    "risks": risks,
                    "text_length_chars": len(full_text),
                    "chunks_analyzed": len(chunks),
                },
            )

        hints = task.context_hints or {}
        mode_block = self._mode_prompt(hints)
        max_blocks = 0 if is_strict(hints) and not (hints or {}).get("allow_qualitative") else (2 if is_strict(hints) else 5)

        if max_blocks == 0:
            return []

        system = f"""Ты QualWorker — агент качественного анализа. Создавай блоки на основе NLP-инструментов.

{mode_block}

Доступные типы: "text" и "insight". НЕ используй risk_matrix.
НЕ анализируй текст повторно — только предоставленные результаты NLP.
Максимум {max_blocks} блок(ов). Все тексты на РУССКОМ."""

        user = f"""Задача: {task.description}

Результаты NLP-анализа:
{str(nlp_results)[:2000]}

Контекст документа:
{context[:800]}

Создай до {max_blocks} блок(ов) строго по задаче."""

        try:
            output = await get_session_llm().complete(
                messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                response_model=QualWorkerOutput,
                role="worker",
                max_tokens=2000,
            )
            self._log("worker_done", task_id=task.task_id, blocks=len(output.blocks))

            await self._bb_log(
                task.session_id, "llm_response",
                f"Качественный анализ завершён: {len(output.blocks)} блоков",
                task_id=task.task_id, department=dept_str,
                details={
                    "blocks_count": len(output.blocks),
                    "block_types": [b.get("block_type") for b in output.blocks],
                    "block_titles": [b.get("title", "")[:60] for b in output.blocks],
                    "reasoning": output.reasoning[:500] if output.reasoning else "",
                },
            )

            return output.blocks
        except Exception as e:
            logger.error("qual_worker_failed", error=str(e))
            return []


class QualCritic(BaseAgent):
    agent_name = "QualCritic"
    role = "critic"
    department = "qual_analysis"

    async def review(
        self,
        task_id: str,
        blocks: list[dict],
        context_hints: dict | None = None,
    ) -> CriticVerdict:
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
        if is_strict(context_hints) and not (context_hints or {}).get("allow_qualitative") and blocks:
            return CriticVerdict(
                task_id=task_id, status="REJECT", score=0.3,
                issues=[CriticIssue(
                    severity="MAJOR", category="FORMAT_VIOLATION",
                    description="Качественные блоки не запрашивались",
                    suggested_fix="Удалить insight/text аналитику",
                )],
            )
        return CriticVerdict(task_id=task_id, status="APPROVED", score=0.82, reasoning="Блоки качественного анализа проверены")
