from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any
import uuid


class UploadFileResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    status: str = "processing"


class CreateSessionRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    file_ids: list[str]
    llm_provider: str | None = None      # переопределить провайдер для сессии
    report_title: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str = "pending"


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    query: str
    created_at: str
    completed_at: str | None
    total_tokens: int
    task_statuses: list[dict[str, Any]] = []


class HealthResponse(BaseModel):
    status: str
    postgres: str
    redis: str
    llm_api: str
    version: str = "0.1.0"
