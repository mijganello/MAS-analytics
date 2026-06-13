from __future__ import annotations
from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class BlackboardEventType(str, Enum):
    TASK_ASSIGNED = "task_assigned"
    DRAFT_READY = "draft_ready"
    VERDICT = "verdict"
    ESCALATION = "escalation"
    BLOCK_APPROVED = "block_approved"
    SESSION_DONE = "session_done"
    ERROR = "error"
    TASK_STATUS = "task_status"


class BlackboardMessage(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: str | None = None
    session_id: str
    task_id: str
    msg_type: BlackboardEventType
    payload_ref: str                     # ключ в Redis / id объекта
    payload: dict[str, Any] = {}        # легковесный payload для фронтенда
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: int = 3600


class AgentTaskStatus(BaseModel):
    task_id: str
    session_id: str
    department: str
    status: Literal["pending", "running", "review", "approved", "failed", "escalated"]
    retries: int = 0
    tokens_used: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
