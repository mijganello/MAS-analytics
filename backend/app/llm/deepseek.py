from __future__ import annotations
from typing import Type
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel
from app.llm.provider import LLMProvider, LLMMessage
from app.core.config import settings
from app.core.logging import logger


class DeepSeekProvider(LLMProvider):
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self._instructor = instructor.from_openai(self._client, mode=instructor.Mode.JSON)

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: Type[BaseModel],
        model: str,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> BaseModel:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        logger.info("llm_structured_call", model=model, response_model=response_model.__name__)
        result = await self._instructor.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=2,
        )
        return result

    async def complete_text(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await self._client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
