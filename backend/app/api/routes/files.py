from __future__ import annotations
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.postgres import get_db
from app.storage.file_store import file_store
from app.storage.models import UploadedFile, Session as SessionDB
from app.document_pipeline.pipeline import document_pipeline
from app.schemas.api import UploadFileResponse
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=list[UploadFileResponse])
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(400, "No files provided")

    responses = []
    for upload in files:
        size = 0
        file_id = str(uuid.uuid4())
        file_type = file_store.detect_type(upload.filename or "file")

        if file_type == "unknown":
            raise HTTPException(400, f"Unsupported file type: {upload.filename}")

        # Check size
        content = await upload.read()
        size = len(content)
        if size > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(413, f"File too large: {upload.filename}")

        # Reset file pointer and save
        await upload.seek(0)
        storage_path = await file_store.save(upload, file_id)

        # Create DB record
        file_db = UploadedFile(
            id=file_id,
            session_id=None,  # assigned when session is created
            filename=upload.filename or "file",
            file_type=file_type,
            size_bytes=size,
            storage_path=storage_path,
            processing_status="processing",
        )
        db.add(file_db)
        await db.commit()

        # Process in background
        background_tasks.add_task(
            _process_file_background, file_id, storage_path, file_type
        )

        responses.append(UploadFileResponse(
            file_id=file_id,
            filename=upload.filename or "file",
            file_type=file_type,
            size_bytes=size,
        ))

    return responses


async def _process_file_background(file_id: str, storage_path: str, file_type: str) -> None:
    from app.storage.postgres import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await document_pipeline.process(db, storage_path, file_id, file_type)
        except Exception as e:
            from sqlalchemy import update
            await db.execute(
                update(UploadedFile).where(UploadedFile.id == file_id).values(processing_status="error")
            )
            await db.commit()
            logger.error("file_processing_error", file_id=file_id, error=str(e))


@router.get("/{file_id}/status")
async def get_file_status(file_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")
    return {"file_id": file_id, "status": file.processing_status, "filename": file.filename}
