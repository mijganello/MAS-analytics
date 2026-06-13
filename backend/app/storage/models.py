from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey,
    JSON, Boolean, BigInteger
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid


class Base(DeclarativeBase):
    pass


def gen_uuid():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    query = Column(Text, nullable=False)
    status = Column(String(20), default="pending")   # pending, running, complete, failed
    report_title = Column(String(500), nullable=True)
    llm_provider = Column(String(50), default="deepseek")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_tokens = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)
    log_json = Column(JSON, nullable=True)      # agent interaction log events

    files = relationship("UploadedFile", back_populates="session")
    tasks = relationship("Task", back_populates="session")
    report_blocks = relationship("ReportBlockDB", back_populates="session")
    audit_logs = relationship("AgentAudit", back_populates="session")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)  # NULL until session created
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)   # pdf, xlsx, csv, docx, json
    size_bytes = Column(BigInteger, default=0)
    storage_path = Column(Text, nullable=False)
    processing_status = Column(String(20), default="pending")
    fingerprint_json = Column(JSON, nullable=True)
    doc_structure_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="files")
    chunks = relationship("DocumentChunk", back_populates="file")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=gen_uuid)
    file_id = Column(String, ForeignKey("uploaded_files.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String(20), default="text")   # text, table, numeric
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding = Column(Vector(1024), nullable=True)
    numeric_density = Column(Float, default=0.0)
    page_number = Column(Integer, nullable=True)
    section_header = Column(String(500), nullable=True)

    file = relationship("UploadedFile", back_populates="chunks")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    department = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    spec_json = Column(JSON, nullable=False)
    result_block_id = Column(String, nullable=True)
    retries = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    session = relationship("Session", back_populates="tasks")


class ReportBlockDB(Base):
    __tablename__ = "report_blocks"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    block_type = Column(String(50), nullable=False)
    block_json = Column(JSON, nullable=False)
    order = Column(Integer, default=0)
    status = Column(String(20), default="complete")
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="report_blocks")


class AgentAudit(Base):
    __tablename__ = "agent_audit"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    task_id = Column(String, nullable=True)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="audit_logs")
