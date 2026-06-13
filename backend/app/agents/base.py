from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import Any
from app.llm.structured import llm
from app.llm.provider import LLMMessage
from app.tools.registry import tool_registry
from app.blackboard.board import blackboard
from app.schemas.tasks import TaskSpec, LoopGuard, CriticVerdict
from app.schemas.blocks import ReportBlock
from app.core.config import settings
from app.core.logging import logger


class BaseAgent(ABC):
    """Abstract base for all agents."""

    agent_name: str = "base_agent"
    role: str = "worker"   # worker | critic | orchestrator
    department: str = ""

    def _build_system_prompt(self) -> str:
        return f"You are {self.agent_name}, a specialized AI agent."

    def _get_model(self) -> str:
        if self.role == "orchestrator":
            model_key = settings.orchestrator_model if settings.llm_provider == "deepseek" else settings.ollama_orchestrator_model
        elif self.role == "critic":
            model_key = settings.critic_model if settings.llm_provider == "deepseek" else settings.ollama_critic_model
        else:
            model_key = settings.worker_model if settings.llm_provider == "deepseek" else settings.ollama_worker_model
        return model_key

    def _call_tool(self, tool_name: str, **kwargs) -> Any:
        return tool_registry.call(tool_name, **kwargs)

    def _build_context_from_chunks(self, chunks: list[dict]) -> str:
        parts = []
        for c in chunks[:8]:  # max 8 chunks
            header = c.get("section_header") or c.get("chunk_type", "")
            parts.append(f"[{header}]\n{c['content'][:500]}")
        return "\n\n---\n\n".join(parts)

    def _log(self, action: str, **kwargs) -> None:
        logger.info(action, agent=self.agent_name, department=self.department, **kwargs)
