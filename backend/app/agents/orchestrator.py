from __future__ import annotations
import asyncio
import math
import time
import uuid
from datetime import datetime
from typing import Any


def _sanitize_json(obj: Any) -> Any:
    """Recursively replace float NaN/Inf with None so PostgreSQL JSON accepts the payload."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(item) for item in obj]
    return obj
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.agents.base import BaseAgent
from app.llm.provider import LLMMessage
from app.llm.structured import StructuredLLM, set_session_provider, set_session_llm, get_active_provider_name
from app.blackboard.board import blackboard
from app.schemas.tasks import TaskSpec, TaskGraph, OrchestratorPlan, LightOrchestratorPlan, DepartmentEnum, LoopGuard
from app.schemas.report import ReportSchema, ReportMetadata, TOCEntry
from app.schemas.blocks import ReportBlock
from app.document_pipeline.retriever import retriever
from app.storage.models import UploadedFile, Session as SessionDB, ReportBlockDB
from app.storage.postgres import AsyncSessionLocal
from app.core.config import settings
from app.core.logging import logger


class ChiefAgent(BaseAgent):
    agent_name = "ChiefAgent"
    role = "orchestrator"
    department = "orchestrator"

    async def run(
        self,
        session_id: str,
        query: str,
        file_ids: list[str],
        llm_provider: str | None = None,
    ) -> None:
        """Main orchestration loop. Runs as a background task."""
        # Set per-session provider — propagates to all workers via contextvars
        if llm_provider:
            set_session_provider(llm_provider)

        # Fresh per-session token counter — shared with all workers via context var
        llm = StructuredLLM()
        set_session_llm(llm)   # workers call get_session_llm() → this instance

        start_time = time.time()
        logger.info("orchestrator_start", session_id=session_id,
                    files=len(file_ids), provider=get_active_provider_name())

        await blackboard.init_session(session_id, query, file_ids)

        async with AsyncSessionLocal() as db:
            # Update session status
            await db.execute(update(SessionDB).where(SessionDB.id == session_id).values(status="running"))
            await db.commit()

            try:
                await blackboard.append_log(session_id, "session_start", "ChiefAgent",
                    f"Сессия запущена. Файлов: {len(file_ids)}. Запрос: {query[:120]}")

                # 1. Load file metadata (NOT full content — token efficient)
                file_metas = await self._load_file_metadata(db, file_ids)

                # 2. Plan tasks
                plan = await self._plan(query, file_metas, llm)
                logger.info("plan_ready", tasks=len(plan.tasks), groups=len(plan.execution_order))
                await blackboard.append_log(session_id, "plan_created", "ChiefAgent",
                    f"План составлен: {len(plan.tasks)} задач, {len(plan.execution_order)} групп выполнения",
                    details={"reasoning": plan.reasoning,
                             "tasks": [{"id": t.task_id, "dept": t.department, "desc": t.description}
                                       for t in plan.tasks],
                             "groups": plan.execution_order})

                # 3. Build task graph on blackboard
                graph = TaskGraph(
                    session_id=session_id,
                    tasks={t.task_id: t for t in plan.tasks},
                    execution_groups=plan.execution_order,
                )
                await blackboard.write_task_graph(session_id, graph.model_dump(mode="json"))

                # 4. Execute groups sequentially, tasks within group in parallel
                all_blocks: list[dict] = []

                for group_idx, group in enumerate(plan.execution_order):
                    logger.info("executing_group", group=group_idx, tasks=group)
                    await blackboard.append_log(session_id, "group_start", "ChiefAgent",
                        f"Группа {group_idx + 1}/{len(plan.execution_order)}: {len(group)} задач параллельно",
                        details={"group_idx": group_idx, "task_ids": group})
                    group_results = await self._execute_group(
                        session_id, group, plan.tasks, file_ids, db, all_blocks
                    )
                    all_blocks.extend(group_results)
                    await blackboard.append_log(session_id, "group_done", "ChiefAgent",
                        f"Группа {group_idx + 1} завершена. Новых блоков: {len(group_results)}",
                        details={"blocks_added": len(group_results), "total_blocks": len(all_blocks)})

                # 5. Assemble final report
                await blackboard.append_log(session_id, "assembly_start", "AssemblyWorker",
                    f"Компиляция отчёта. Всего блоков для сборки: {len(all_blocks)}")
                report = await self._assemble_report(session_id, query, all_blocks, file_ids, db, llm)

                # 6. Persist report blocks
                await self._persist_report(db, session_id, report)

                # 7. Persist agent log
                elapsed = round(time.time() - start_time, 2)
                await blackboard.append_log(
                    session_id, "session_complete", "ChiefAgent",
                    f"Анализ завершён за {elapsed}с. "
                    f"Использовано токенов: {llm.total_tokens}. "
                    f"Блоков сгенерировано: {len(all_blocks)}. "
                    f"Качество: {report.metadata.quality_score:.0%}",
                    details={
                        "elapsed_s": elapsed,
                        "total_tokens": llm.total_tokens,
                        "blocks_count": len(all_blocks),
                        "quality_score": report.metadata.quality_score,
                        "departments_involved": report.metadata.departments_involved,
                        "files_analyzed": report.metadata.files_analyzed,
                        "llm_provider": report.metadata.llm_provider,
                        "model_name": report.metadata.model_name,
                    },
                )
                full_log = _sanitize_json(await blackboard.get_log(session_id))
                await db.execute(
                    update(SessionDB).where(SessionDB.id == session_id).values(
                        status="complete",
                        completed_at=datetime.utcnow(),
                        total_tokens=llm.total_tokens,
                        quality_score=report.metadata.quality_score,
                        log_json=full_log,
                    )
                )
                await db.commit()
                await blackboard.mark_session_done(session_id)
                logger.info("orchestrator_done", session_id=session_id, elapsed=elapsed, blocks=len(report.blocks))

            except Exception as e:
                logger.error("orchestrator_error", session_id=session_id, error=str(e))
                await blackboard.append_log(session_id, "session_error", "ChiefAgent",
                    f"Критическая ошибка: {str(e)[:300]}", details={"error": str(e)})
                err_log = _sanitize_json(await blackboard.get_log(session_id))
                await db.execute(update(SessionDB).where(SessionDB.id == session_id).values(
                    status="failed", log_json=err_log
                ))
                await db.commit()
                await blackboard.mark_session_done(session_id)
                raise

    async def _load_file_metadata(self, db: AsyncSession, file_ids: list[str]) -> list[dict]:
        result = await db.execute(select(UploadedFile).where(UploadedFile.id.in_(file_ids)))
        files = result.scalars().all()
        return [
            {
                "file_id": f.id,
                "filename": f.filename,
                "file_type": f.file_type,
                "size_bytes": f.size_bytes,
                "structure": f.doc_structure_json or {},
            }
            for f in files
        ]

    async def _plan(self, query: str, file_metas: list[dict], llm: StructuredLLM) -> OrchestratorPlan:
        files_summary = str(file_metas)[:500]

        # ── Why this prompt uses LightOrchestratorPlan + worker role ──────────
        # deepseek-reasoner expends 1 000–1 500 reasoning tokens before writing
        # the actual JSON response, leaving only ~500–800 tokens for the plan
        # when max_tokens=2000.  A full OrchestratorPlan with 5 tasks in
        # TaskSpec format (~500 tok/task) needs ~2 500+ tokens — it always gets
        # truncated, instructor cannot parse the incomplete JSON, and we fall
        # back to _default_plan on every single session.
        #
        # Fix: use deepseek-chat (role="worker") which produces no reasoning
        # overhead, and use LightOrchestratorPlan whose PlanTask has only
        # 5 fields (~80 tok/task) instead of 15.  A 6-task plan fits in ~500
        # output tokens.  We then inflate each PlanTask into a full TaskSpec.
        # ─────────────────────────────────────────────────────────────────────

        system = """Ты ChiefAgent — оркестратор многоагентной системы генерации аналитических отчётов.
Декомпозируй аналитический запрос на атомарные подзадачи и распредели по отделам.

ВАЖНО: все поля description и reasoning — строго на РУССКОМ языке.

Доступные отделы (department):
- data_extraction  — извлечение и верификация данных из документа
- quant_analysis   — статистика, тренды, прогнозы (инструменты делают математику)
- qual_analysis    — анализ текста, тональность, риски, резюме
- visualization    — спецификации графиков и диаграмм
- report_assembly  — финальный отчёт с исполнительным резюме

Правила компоновки плана:
1. data_extraction — всегда первым (группа 0)
2. quant_analysis и qual_analysis — параллельно во второй группе, после data_extraction
3. visualization — после quant_analysis (зависит от quant-задач)
4. report_assembly — последним, зависит от всех остальных
5. task_id — короткая строка без пробелов (напр. "extract_1", "quant_2")
6. description — не длиннее 200 символов, строго на русском
7. Не добавляй лишних задач — только те, что нужны для данного запроса

Верни LightOrchestratorPlan JSON."""

        user = f"""Запрос: {query}

Доступные файлы:
{files_summary}

Составь план: задачи и execution_order (список групп параллельного выполнения)."""

        try:
            light_plan = await llm.complete(
                messages=[
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user",   content=user),
                ],
                response_model=LightOrchestratorPlan,
                role="worker",        # → deepseek-chat: no reasoning overhead, great at JSON
                max_tokens=4000,      # ample room: 6 PlanTasks ≈ 480 tokens
                temperature=0.1,
            )

            # Validate execution_order references
            valid_ids = {t.task_id for t in light_plan.tasks}
            clean_order = [
                [tid for tid in group if tid in valid_ids]
                for group in light_plan.execution_order
            ]
            clean_order = [g for g in clean_order if g]
            if not clean_order:
                # Fallback: sequential order if LLM produced empty groups
                clean_order = [[t.task_id] for t in light_plan.tasks]

            # Inflate PlanTask → full TaskSpec
            tasks = [
                TaskSpec(
                    task_id=t.task_id,
                    session_id="pending",
                    department=t.department,
                    description=t.description,
                    depends_on_tasks=t.depends_on_tasks,
                    expected_output_type=t.expected_output_type,
                )
                for t in light_plan.tasks
            ]

            return OrchestratorPlan(
                reasoning=light_plan.reasoning,
                tasks=tasks,
                execution_order=clean_order,
            )

        except Exception as e:
            logger.warning("plan_failed_using_default", error=str(e))
            return self._default_plan(query)

    def _default_plan(self, query: str) -> OrchestratorPlan:
        """Резервный план при сбое планировщика LLM."""
        t1 = TaskSpec(task_id=str(uuid.uuid4()), session_id="pending",
                      department=DepartmentEnum.DATA_EXTRACTION, description=f"Извлечь ключевые данные для: {query[:100]}",
                      expected_output_type="table", priority=1)
        t2 = TaskSpec(task_id=str(uuid.uuid4()), session_id="pending",
                      department=DepartmentEnum.QUAL_ANALYSIS, description=f"Качественный анализ: {query[:100]}",
                      expected_output_type="text", priority=2, depends_on_tasks=[t1.task_id])
        t3 = TaskSpec(task_id=str(uuid.uuid4()), session_id="pending",
                      department=DepartmentEnum.REPORT_ASSEMBLY, description="Компиляция финального отчёта",
                      expected_output_type="executive_summary", priority=3, depends_on_tasks=[t1.task_id, t2.task_id])
        return OrchestratorPlan(
            reasoning="Резервный план по умолчанию",
            tasks=[t1, t2, t3],
            execution_order=[[t1.task_id], [t2.task_id], [t3.task_id]],
        )

    async def _execute_group(
        self,
        session_id: str,
        task_ids: list[str],
        all_tasks: list[TaskSpec],
        file_ids: list[str],
        db: AsyncSession,
        existing_blocks: list[dict],
    ) -> list[dict]:
        task_map = {t.task_id: t for t in all_tasks}
        tasks_to_run = [task_map[tid] for tid in task_ids if tid in task_map]

        async def run_single(task: TaskSpec) -> list[dict]:
            task.session_id = session_id
            return await self._execute_task(task, file_ids, db, existing_blocks)

        results = await asyncio.gather(*[run_single(t) for t in tasks_to_run], return_exceptions=True)
        all_new_blocks = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("task_exception", error=str(r))
            elif isinstance(r, list):
                all_new_blocks.extend(r)
        return all_new_blocks

    async def _execute_task(
        self,
        task: TaskSpec,
        file_ids: list[str],
        db: AsyncSession,
        existing_blocks: list[dict],
    ) -> list[dict]:
        dept = task.department
        loop_guard = LoopGuard(task_id=task.task_id, max_retries=settings.max_task_retries)

        await blackboard.update_task_status(task.task_id, task.session_id, "running")
        await blackboard.write_task(task)
        await blackboard.append_log(task.session_id, "task_start",
            f"{dept.value.title().replace('_', '')}Worker",
            f"Задача запущена: «{task.description[:100]}»",
            task_id=task.task_id, department=dept.value,
            details={
                "task_id": task.task_id,
                "department": dept.value,
                "description": task.description,
                "max_retries": task.max_retries,
                "max_tokens": task.max_tokens,
                "file_ids": file_ids,
            })

        # Retrieve relevant chunks
        chunks = await retriever.search(db, task.description, file_ids, top_k=8)
        if chunks:
            sources = list(dict.fromkeys(
                c.get("filename") or c.get("source") or "документ"
                for c in chunks if isinstance(c, dict)
            ))
            await blackboard.append_log(
                task.session_id, "context_loaded",
                f"{dept.value.title().replace('_', '')}Worker",
                f"Контекст загружен: {len(chunks)} фрагментов из {len(sources)} источников",
                task_id=task.task_id, department=dept.value,
                details={
                    "chunks_count": len(chunks),
                    "sources": sources[:10],
                    "top_chunk_preview": chunks[0].get("content", "")[:300] if chunks else "",
                    "chunk_headers": [
                        c.get("section_header") or c.get("chunk_type", "")
                        for c in chunks[:8]
                    ],
                }
            )

        # Load fingerprint from first file
        fingerprint_json = {}
        if file_ids:
            result = await db.execute(select(UploadedFile).where(UploadedFile.id == file_ids[0]))
            file = result.scalar_one_or_none()
            if file and file.fingerprint_json:
                fingerprint_json = file.fingerprint_json

        blocks: list[dict] = []

        for attempt in range(settings.max_task_retries + 1):
            try:
                # Run worker
                if dept == DepartmentEnum.DATA_EXTRACTION:
                    from app.agents.departments.data_extraction.worker import DataWorker, DataCritic
                    blocks = await DataWorker().run(task, chunks, fingerprint_json)
                    verdict = await DataCritic().review(task.task_id, blocks, chunks)

                elif dept == DepartmentEnum.QUANT_ANALYSIS:
                    from app.agents.departments.quant_analysis.worker import QuantWorker, QuantCritic
                    data_ctx = {b.get("title", ""): b for b in existing_blocks if b.get("block_type") in ("table", "kpi_card")}
                    blocks = await QuantWorker().run(task, chunks, data_ctx)
                    verdict = await QuantCritic().review(task.task_id, blocks)

                elif dept == DepartmentEnum.QUAL_ANALYSIS:
                    from app.agents.departments.qual_analysis.worker import QualWorker, QualCritic
                    blocks = await QualWorker().run(task, chunks)
                    verdict = await QualCritic().review(task.task_id, blocks)

                elif dept == DepartmentEnum.VISUALIZATION:
                    from app.agents.departments.visualization.worker import VizWorker, VizCritic
                    data_results = {b.get("title", ""): b for b in existing_blocks}
                    blocks = await VizWorker().run(task, data_results)
                    verdict = await VizCritic().review(task.task_id, blocks)

                elif dept == DepartmentEnum.REPORT_ASSEMBLY:
                    # Assembly is handled separately by _assemble_report() after all groups complete.
                    # This task slot exists in the plan only for dependency ordering.
                    await blackboard.append_log(task.session_id, "task_skipped",
                        "ChiefAgent",
                        "Сборка отчёта запланирована — выполнится после всех групп через _assemble_report()",
                        task_id=task.task_id, department=dept.value)
                    return []
                else:
                    return []

                # Sanity-filter blocks before publishing: drop any with missing/null block_type
                _valid_types = {"table", "kpi_card", "text", "chart", "insight",
                                "executive_summary", "forecast", "comparison"}
                valid_blocks = []
                for b in blocks:
                    btype = b.get("block_type")
                    if btype and btype in _valid_types:
                        valid_blocks.append(b)
                    else:
                        logger.warning("block_skipped_no_type", block_type=btype,
                                       title=b.get("title", ""), task_id=task.task_id)
                if len(valid_blocks) < len(blocks):
                    dropped = len(blocks) - len(valid_blocks)
                    await blackboard.append_log(task.session_id, "task_error",
                        "Blackboard",
                        f"Отброшено {dropped} блоков без корректного block_type",
                        task_id=task.task_id, department=dept.value)
                blocks = valid_blocks

                # Check verdict
                if verdict.status == "APPROVED":
                    await blackboard.update_task_status(task.task_id, task.session_id, "approved")
                    await blackboard.append_log(task.session_id, "verdict_approved",
                        f"{dept.value.title().replace('_', '')}Critic",
                        f"✓ Одобрено (score={verdict.score:.2f}). Блоков: {len(blocks)}",
                        task_id=task.task_id, department=dept.value,
                        details={
                            "score": verdict.score,
                            "reasoning": verdict.reasoning,
                            "blocks": [
                                {"type": b.get("block_type"), "title": b.get("title", "")[:80]}
                                for b in blocks
                            ],
                        })
                    # Publish approved blocks
                    for block in blocks:
                        block.setdefault("block_id", str(uuid.uuid4()))
                        block.setdefault("status", "complete")
                        block.setdefault("created_by_dept", dept)
                        block.setdefault("created_at", datetime.utcnow().isoformat())
                        block.setdefault("source_task_ids", [task.task_id])
                        block.setdefault("warnings", [])
                        await blackboard.write_approved_block(task.session_id, block)
                        await blackboard.append_log(task.session_id, "block_published",
                            "Blackboard",
                            f"Блок опубликован: {block.get('block_type')} «{block.get('title', '')[:60]}»",
                            task_id=task.task_id, department=dept.value,
                            details={"block_type": block.get("block_type"), "block_id": block.get("block_id")})
                    return blocks

                # REJECT — retry if allowed
                issues_summary = "; ".join(i.description for i in verdict.issues[:3])
                await blackboard.append_log(task.session_id, "verdict_rejected",
                    f"{dept.value.title().replace('_', '')}Critic",
                    f"✗ Отклонено (score={verdict.score:.2f}): {issues_summary}",
                    task_id=task.task_id, department=dept.value,
                    details={
                        "score": verdict.score,
                        "reasoning": verdict.reasoning,
                        "issues": [
                            {
                                "severity": i.severity,
                                "category": i.category,
                                "description": i.description,
                                "suggested_fix": i.suggested_fix,
                            }
                            for i in verdict.issues
                        ],
                    })
                if attempt < settings.max_task_retries:
                    logger.warning("task_rejected_retry", task_id=task.task_id, attempt=attempt, issues=len(verdict.issues))
                    await blackboard.increment_retry(task.task_id)
                    await blackboard.append_log(task.session_id, "task_retry",
                        f"{dept.value.title().replace('_', '')}Worker",
                        f"Повтор {attempt + 2}/{settings.max_task_retries + 1}",
                        task_id=task.task_id, department=dept.value)
                    continue

                # Exhausted retries — use best available
                logger.warning("task_escalated", task_id=task.task_id)
                await blackboard.update_task_status(task.task_id, task.session_id, "escalated")
                await blackboard.append_log(task.session_id, "task_escalated",
                    "ChiefAgent",
                    f"Эскалация: попытки исчерпаны, используется лучший черновик",
                    task_id=task.task_id, department=dept.value)
                for block in blocks:
                    block.setdefault("block_id", str(uuid.uuid4()))
                    block["status"] = "partial"
                    block["warnings"] = [f"Critic issues after {attempt+1} attempts"]
                    block.setdefault("created_by_dept", dept)
                    block.setdefault("created_at", datetime.utcnow().isoformat())
                    block.setdefault("source_task_ids", [task.task_id])
                    await blackboard.write_approved_block(task.session_id, block)
                return blocks

            except Exception as e:
                logger.error("task_execution_error", task_id=task.task_id, error=str(e), attempt=attempt)
                await blackboard.append_log(task.session_id, "task_error",
                    f"{dept.value.title().replace('_', '')}Worker",
                    f"Ошибка выполнения (попытка {attempt + 1}): {str(e)[:200]}",
                    task_id=task.task_id, department=dept.value, details={"error": str(e)})
                if attempt == settings.max_task_retries:
                    await blackboard.update_task_status(task.task_id, task.session_id, "failed", error_message=str(e))
                    return []

        return blocks

    async def _assemble_report(
        self,
        session_id: str,
        query: str,
        all_blocks: list[dict],
        file_ids: list[str],
        db: AsyncSession,
        llm: StructuredLLM,
    ) -> ReportSchema:
        from app.agents.departments.report_assembly.worker import AssemblyWorker, AssemblyCritic

        assembly_task = TaskSpec(
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            department=DepartmentEnum.REPORT_ASSEMBLY,
            description=f"Assemble final report for: {query[:100]}",
        )

        assembled = await AssemblyWorker().run(assembly_task, all_blocks)
        final_blocks = assembled.get("blocks", all_blocks)
        toc_data = assembled.get("toc", [])

        toc = [TOCEntry(**t) for t in toc_data if all(k in t for k in ("block_id", "title", "block_type", "order"))]
        scores = [b.get("quality_score", 0.8) for b in final_blocks if isinstance(b.get("quality_score"), float)]
        avg_score = sum(scores) / len(scores) if scores else 0.75
        partial_count = sum(1 for b in final_blocks if b.get("status") == "partial")

        result = await db.execute(select(UploadedFile).where(UploadedFile.id.in_(file_ids)))
        files = result.scalars().all()

        provider_name = get_active_provider_name()
        model_name = (settings.ollama_worker_model if provider_name == "ollama"
                      else settings.worker_model)
        metadata = ReportMetadata(
            total_tokens_used=llm.total_tokens,
            processing_time_seconds=0,
            departments_involved=list({b.get("created_by_dept", "") for b in final_blocks}),
            files_analyzed=[f.filename for f in files],
            llm_provider=provider_name,
            model_name=model_name,
            quality_score=round(avg_score, 2),
            partial_blocks_count=partial_count,
        )

        return ReportSchema(
            report_id=session_id,
            title=f"Аналитический отчёт: {query[:80]}",
            query=query,
            blocks=[],  # Raw dicts stored separately
            toc=toc,
            metadata=metadata,
        )

    async def _persist_report(self, db: AsyncSession, session_id: str, report: ReportSchema) -> None:
        blocks = await blackboard.get_session_blocks(session_id)
        for block in blocks:
            block_db = ReportBlockDB(
                id=block.get("block_id", str(uuid.uuid4())),
                session_id=session_id,
                block_type=block.get("block_type", "text"),
                block_json=block,
                order=block.get("order", 0),
                status=block.get("status", "complete"),
            )
            await db.merge(block_db)
        await db.commit()


chief_agent = ChiefAgent()
