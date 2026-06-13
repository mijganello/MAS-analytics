from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
import uuid

from app.schemas.blocks import ReportBlock


class ReportMetadata(BaseModel):
    total_tokens_used: int = 0
    processing_time_seconds: float = 0.0
    departments_involved: list[str] = []
    files_analyzed: list[str] = []
    llm_provider: str = ""
    model_name: str = ""
    quality_score: float = 0.0
    partial_blocks_count: int = 0


class TOCEntry(BaseModel):
    block_id: str
    title: str
    block_type: str
    order: int


class ReportSchema(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    query: str
    blocks: list[ReportBlock] = []
    toc: list[TOCEntry] = []
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
