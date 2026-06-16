from __future__ import annotations
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Type
from pydantic import BaseModel
from app.llm.provider import LLMProvider, LLMMessage
from app.core.config import settings
from app.core.logging import logger

if TYPE_CHECKING:
    pass

# Per-async-task context variable: overrides the global settings.llm_provider
# Set by the orchestrator at the start of each session run.
_session_provider: ContextVar[str | None] = ContextVar("session_provider", default=None)

# Cache of instantiated providers — shared across sessions (they're stateless)
_providers: dict[str, LLMProvider] = {}

# Per-session StructuredLLM context variable.
# Set by ChiefAgent.run() so that all workers/critics in the same async
# context accumulate their tokens into a single shared instance.
# This gives accurate per-session token totals without any global mutable state.
_session_llm: "ContextVar[StructuredLLM | None]" = ContextVar("session_llm", default=None)


def set_session_provider(name: str) -> None:
    """Set the LLM provider for the current async context (task + all its children)."""
    _session_provider.set(name)


def get_active_provider_name() -> str:
    """Return the effective provider name for the current async context."""
    return _session_provider.get(None) or settings.llm_provider


def set_session_llm(instance: "StructuredLLM") -> None:
    """Register a StructuredLLM instance for the current async context.

    Must be called by ChiefAgent.run() before dispatching any worker/critic
    tasks so that all token counters roll up into one shared instance.
    """
    _session_llm.set(instance)


def get_session_llm() -> "StructuredLLM":
    """Return the per-session StructuredLLM for the current async context.

    Falls back to the module-level singleton if the orchestrator hasn't
    installed one yet (e.g. during tests or standalone worker calls).
    """
    return _session_llm.get(None) or llm


def get_provider(name: str | None = None) -> LLMProvider:
    """Return a (cached) provider instance by name."""
    key = name or get_active_provider_name()
    if key not in _providers:
        if key == "ollama":
            from app.llm.ollama import OllamaProvider
            _providers[key] = OllamaProvider()
        else:
            from app.llm.deepseek import DeepSeekProvider
            _providers[key] = DeepSeekProvider()
    return _providers[key]


class StructuredLLM:
    """Facade around LLMProvider with logging and per-session token tracking."""

    def __init__(self) -> None:
        self._total_tokens = 0

    def _get_model(self, role: str) -> str:
        provider = get_active_provider_name()
        if provider == "ollama":
            mapping = {
                "orchestrator": settings.ollama_orchestrator_model,
                "worker": settings.ollama_worker_model,
                "critic": settings.ollama_critic_model,
            }
        else:
            mapping = {
                "orchestrator": settings.orchestrator_model,
                "worker": settings.worker_model,
                "critic": settings.critic_model,
            }
        return mapping.get(role, mapping["worker"])

    async def complete(
        self,
        messages: list[LLMMessage],
        response_model: Type[BaseModel],
        role: str = "worker",
        model: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> BaseModel:
        model = model or self._get_model(role)
        provider = get_provider()

        start = time.time()
        result = await provider.complete_structured(
            messages=messages,
            response_model=response_model,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        elapsed = round((time.time() - start) * 1000)

        total_content = " ".join(m.content for m in messages)
        tokens_in = provider.count_tokens(total_content)
        tokens_out = provider.count_tokens(result.model_dump_json())
        self._total_tokens += tokens_in + tokens_out

        logger.info(
            "llm_complete",
            provider=get_active_provider_name(),
            model=model,
            role=role,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=elapsed,
        )
        return result

    async def complete_text(
        self,
        messages: list[LLMMessage],
        role: str = "worker",
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        model = model or self._get_model(role)
        provider = get_provider()
        return await provider.complete_text(messages, model, max_tokens, temperature)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


# Global singleton — used only as a fallback when no per-session llm is set
# (e.g. standalone scripts, tests). Real sessions use set_session_llm().
llm = StructuredLLM()
