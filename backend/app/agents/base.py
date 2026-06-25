from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import Any
from app.llm.structured import get_session_llm, get_active_provider_name
from app.llm.provider import LLMMessage
from app.tools.registry import tool_registry
from app.blackboard.board import blackboard
from app.schemas.tasks import TaskSpec, LoopGuard, CriticVerdict
from app.schemas.blocks import ReportBlock
from app.core.config import settings
from app.core.logging import logger
from app.agents.query_mode import strict_mode_instructions, is_strict


class BaseAgent(ABC):
    """Abstract base for all agents."""

    agent_name: str = "base_agent"
    role: str = "worker"   # worker | critic | orchestrator
    department: str = ""

    def _build_system_prompt(self) -> str:
        return f"You are {self.agent_name}, a specialized AI agent."

    def _get_model(self) -> str:
        provider = get_active_provider_name()
        if self.role == "orchestrator":
            model_key = settings.orchestrator_model if provider == "deepseek" else settings.ollama_orchestrator_model
        elif self.role == "critic":
            model_key = settings.critic_model if provider == "deepseek" else settings.ollama_critic_model
        else:
            model_key = settings.worker_model if provider == "deepseek" else settings.ollama_worker_model
        return model_key

    def _call_tool(self, tool_name: str, **kwargs) -> Any:
        return tool_registry.call(tool_name, **kwargs)

    def _build_context_from_chunks(self, chunks: list[dict]) -> str:
        parts = []
        # Allow up to 12 chunks so that large Excel files with multiple table
        # chunks per sheet (MAX_ROWS_PER_CHUNK=15 → ~3 chunks / 33-row sheet)
        # are all visible to the LLM.
        for c in chunks[:12]:
            header = c.get("section_header") or c.get("chunk_type", "")
            # Table chunks may contain up to 15 rows × ~140 chars = 2 100 chars
            # plus a ~250-char header row — use 3 000 chars to show all rows.
            # Text / insight chunks stay at 2 000.
            limit = 3000 if c.get("chunk_type") == "table" else 2000
            parts.append(f"[{header}]\n{c['content'][:limit]}")
        return "\n\n---\n\n".join(parts)

    def _mode_prompt(self, context_hints: dict | None) -> str:
        return strict_mode_instructions(context_hints)

    def _log(self, action: str, **kwargs) -> None:
        logger.info(action, agent=self.agent_name, department=self.department, **kwargs)

    async def _bb_log(
        self,
        session_id: str,
        event_type: str,
        message: str,
        *,
        task_id: str | None = None,
        department: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Emit a structured log event to the live SSE stream and persistent store."""
        await blackboard.append_log(
            session_id,
            event_type,
            self.agent_name,
            message,
            task_id=task_id,
            department=department or self.department,
            details=details,
        )
