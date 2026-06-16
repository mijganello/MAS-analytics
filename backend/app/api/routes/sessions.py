from __future__ import annotations
import uuid
import asyncio
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.postgres import get_db
from app.storage.models import Session as SessionDB, UploadedFile
from app.schemas.api import CreateSessionRequest, CreateSessionResponse, SessionStatusResponse
from app.core.logging import logger

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Verify files exist and are processed
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id.in_(request.file_ids))
    )
    files = result.scalars().all()
    found_ids = {f.id for f in files}
    missing = set(request.file_ids) - found_ids
    if missing:
        raise HTTPException(404, f"Files not found: {missing}")

    not_ready = [f.id for f in files if f.processing_status not in ("done", "processing")]
    # Allow processing files — they'll be ready by the time agents need them

    session_id = str(uuid.uuid4())
    session_db = SessionDB(
        id=session_id,
        query=request.query,
        status="pending",
        report_title=request.report_title,
    )
    db.add(session_db)

    # Link files to session
    for f in files:
        f.session_id = session_id
    await db.commit()

    # Run orchestrator in background
    background_tasks.add_task(
        _run_orchestrator, session_id, request.query, request.file_ids, request.llm_provider
    )

    logger.info("session_created", session_id=session_id, files=len(files))
    return CreateSessionResponse(session_id=session_id, status="pending")


async def _run_orchestrator(
    session_id: str, query: str, file_ids: list[str], llm_provider: str | None = None
) -> None:
    # Wait for file processing
    await asyncio.sleep(2)
    from app.agents.orchestrator import chief_agent
    try:
        await chief_agent.run(session_id, query, file_ids, llm_provider=llm_provider)
    except Exception as e:
        logger.error("orchestrator_background_error", session_id=session_id, error=str(e))


@router.get("/{session_id}", response_model=SessionStatusResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SessionDB).where(SessionDB.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    return SessionStatusResponse(
        session_id=session_id,
        status=session.status,
        query=session.query,
        created_at=str(session.created_at),
        completed_at=str(session.completed_at) if session.completed_at else None,
        total_tokens=session.total_tokens or 0,
    )
