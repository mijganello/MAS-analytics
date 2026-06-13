from __future__ import annotations
from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid

from app.schemas.blocks import ReportBlock


class DepartmentEnum(str, Enum):
    DATA_EXTRACTION = "data_extraction"
    QUANT_ANALYSIS = "quant_analysis"
    QUAL_ANALYSIS = "qual_analysis"
    VISUALIZATION = "visualization"
    REPORT_ASSEMBLY = "report_assembly"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    REVIEW = "review"
    APPROVED = "approved"
    FAILED = "failed"
    ESCALATED = "escalated"


class EscalationPolicy(BaseModel):
    on_retry_exhausted: Literal["use_best_draft", "skip_block", "fail_task"] = "use_best_draft"
    on_timeout: Literal["use_best_draft", "skip_block", "fail_task"] = "use_best_draft"
    on_token_limit: Literal["use_best_draft", "truncate_and_finalize"] = "use_best_draft"
    notify_orchestrator: bool = True


class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    department: DepartmentEnum
    description: str = Field(max_length=500)
    required_inputs: list[str] = []       # file_ids или task_ids
    depends_on_tasks: list[str] = []      # task_ids которые должны завершиться
    expected_output_type: str = "text"
    priority: int = 5
    max_retries: int = 2
    timeout_seconds: int = 120
    max_tokens: int = 8000
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    context_hints: dict[str, Any] = {}   # дополнительные подсказки для агента
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoopGuard(BaseModel):
    task_id: str
    max_retries: int = 2
    current_retries: int = 0
    max_total_tokens: int = 8000
    tokens_used: int = 0
    timeout_seconds: int = 120
    started_at: datetime = Field(default_factory=datetime.utcnow)
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    draft_scores: list[float] = []        # оценки всех черновиков для use_best_draft
    draft_ids: list[str] = []


class CriticIssue(BaseModel):
    severity: Literal["CRITICAL", "MAJOR", "MINOR"]
    category: Literal[
        "DATA_ACCURACY", "MATH_ERROR", "MISSING_INFO",
        "FORMAT_VIOLATION", "LOGIC_ERROR", "UNVERIFIED_DATA"
    ]
    description: str = Field(max_length=300)
    suggested_fix: str = Field(max_length=300)


class CriticVerdict(BaseModel):
    task_id: str
    status: Literal["APPROVED", "REJECT"]
    score: float = Field(ge=0.0, le=1.0)
    issues: list[CriticIssue] = []
    approved_block: ReportBlock | None = None
    reasoning: str = Field(default="", max_length=300)


class OrchestratorPlan(BaseModel):
    reasoning: str = Field(max_length=500)
    tasks: list[TaskSpec]
    execution_order: list[list[str]]      # группы параллельных задач
    estimated_total_tokens: int = 0


class TaskGraph(BaseModel):
    session_id: str
    tasks: dict[str, TaskSpec] = {}
    execution_groups: list[list[str]] = []
    current_group_idx: int = 0
    completed_task_ids: list[str] = []
    failed_task_ids: list[str] = []
    approved_blocks: list[str] = []       # block_ids
