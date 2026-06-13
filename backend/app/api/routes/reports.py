from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.postgres import get_db
from app.storage.models import Session as SessionDB, ReportBlockDB
from app.blackboard.board import blackboard
from app.schemas.report import ReportSchema, ReportMetadata, TOCEntry
from app.core.logging import logger

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    """List all completed reports (no auth required)."""
    result = await db.execute(
        select(SessionDB)
        .where(SessionDB.status.in_(["complete", "failed"]))
        .order_by(SessionDB.created_at.desc())
        .limit(100)
    )
    sessions = result.scalars().all()
    return [
        {
            "report_id": s.id,
            "title": s.report_title or f"Отчёт: {s.query[:60]}",
            "query": s.query,
            "status": s.status,
            "llm_provider": s.llm_provider or "",
            "created_at": str(s.created_at),
            "completed_at": str(s.completed_at) if s.completed_at else None,
            "total_tokens": s.total_tokens or 0,
        }
        for s in sessions
    ]


@router.get("/{session_id}/stream")
async def stream_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint — streams block_approved and task_status events."""
    result = await db.execute(select(SessionDB).where(SessionDB.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    async def event_generator():
        # 1. Send already-approved blocks first (if any)
        try:
            existing = await blackboard.get_session_blocks(session_id)
            for block in existing:
                data = json.dumps({"type": "block_approved", **block}, default=str)
                yield f"data: {data}\n\n"
        except Exception as e:
            logger.warning("sse_existing_blocks_error", error=str(e))

        # 2. If already done, send final event and stop
        sess_state = await blackboard.get_session(session_id)
        if sess_state and sess_state.get("status") == "complete":
            yield f"data: {json.dumps({'type': 'session_done', 'session_id': session_id})}\n\n"
            return

        # 3. Subscribe to live events with heartbeat
        try:
            async for event in blackboard.subscribe_session(session_id):
                event_type = event.get("type", "")

                if event_type == "__keepalive__":
                    yield ": heartbeat\n\n"
                    continue

                if event_type == "block_approved":
                    block = event.get("block", {})
                    if not block:
                        block_id = event.get("block_id")
                        if block_id:
                            block = await blackboard.get_block(block_id) or {}
                    if block:
                        data = json.dumps({"type": "block_approved", **block}, default=str)
                        yield f"data: {data}\n\n"

                elif event_type == "task_status":
                    data = json.dumps(event, default=str)
                    yield f"data: {data}\n\n"

                elif event_type == "agent_log":
                    data = json.dumps(event, default=str)
                    yield f"data: {data}\n\n"

                elif event_type == "session_done":
                    yield f"data: {json.dumps({'type': 'session_done', 'session_id': session_id})}\n\n"
                    return

        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning("sse_stream_error", session_id=session_id, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{session_id}/log")
async def get_report_log(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return the full agent interaction log for a session."""
    result = await db.execute(select(SessionDB).where(SessionDB.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # Prefer persisted log from DB; fallback to live blackboard log
    log_events = session.log_json or []
    if not log_events:
        log_events = await blackboard.get_log(session_id)

    # Also include blackboard snapshot for debugging
    task_graph = await blackboard.get_task_graph(session_id) or {}
    session_state = await blackboard.get_session(session_id) or {}

    return {
        "session_id": session_id,
        "query": session.query,
        "status": session.status,
        "created_at": str(session.created_at),
        "completed_at": str(session.completed_at) if session.completed_at else None,
        "total_tokens": session.total_tokens or 0,
        "events": log_events,
        "blackboard_snapshot": {
            "session": session_state,
            "task_graph": task_graph,
        },
    }


@router.get("/{session_id}")
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return complete report JSON after session is done."""
    result = await db.execute(select(SessionDB).where(SessionDB.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status not in ("complete", "failed"):
        raise HTTPException(202, "Report not ready yet")

    blocks_result = await db.execute(
        select(ReportBlockDB)
        .where(ReportBlockDB.session_id == session_id)
        .order_by(ReportBlockDB.order)
    )
    blocks_db = blocks_result.scalars().all()
    blocks = [b.block_json for b in blocks_db]

    return {
        "report_id": session_id,
        "title": session.report_title or f"Отчёт: {session.query[:60]}",
        "query": session.query,
        "status": session.status,
        "created_at": str(session.created_at),
        "completed_at": str(session.completed_at) if session.completed_at else None,
        "blocks": blocks,
        "metadata": {
            "total_tokens_used": session.total_tokens or 0,
            "llm_provider": session.llm_provider or "",
            "quality_score": session.quality_score or 0,
        },
    }
