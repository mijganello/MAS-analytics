from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Type
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str  # system, user, assistant
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: Type[BaseModel],
        model: str,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> BaseModel:
        ...

    @abstractmethod
    async def complete_text(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        ...

    def count_tokens(self, text: str) -> int:
        # Rough approximation: 1 token ≈ 4 chars
        return len(text) // 4
