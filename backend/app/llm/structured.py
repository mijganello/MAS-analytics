from __future__ import annotations
import time
from typing import Type
from pydantic import BaseModel
from app.llm.provider import LLMProvider, LLMMessage
from app.core.config import settings
from app.core.logging import logger

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if settings.llm_provider == "ollama":
            from app.llm.ollama import OllamaProvider
            _provider = OllamaProvider()
        else:
            from app.llm.deepseek import DeepSeekProvider
            _provider = DeepSeekProvider()
    return _provider


class StructuredLLM:
    """Facade around LLMProvider with logging and token tracking."""

    def __init__(self):
        self._total_tokens = 0

    def _get_models(self, role: str) -> str:
        provider = settings.llm_provider
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
        model = model or self._get_models(role)
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

        # Rough token estimate
        total_content = " ".join(m.content for m in messages)
        tokens_in = provider.count_tokens(total_content)
        tokens_out = provider.count_tokens(result.model_dump_json())
        self._total_tokens += tokens_in + tokens_out

        logger.info(
            "llm_complete",
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
        model = model or self._get_models(role)
        provider = get_provider()
        return await provider.complete_text(messages, model, max_tokens, temperature)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


llm = StructuredLLM()
