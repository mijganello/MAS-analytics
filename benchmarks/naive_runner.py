"""
Naive baseline runner.

Sends the raw file content + query directly to DeepSeek API in a single call.
Measures latency and collects token usage from the API response.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

MAX_FILE_CHARS = 80_000  # ~20k tokens — fits comfortably in deepseek-chat context


def read_file_for_prompt(data_file: Path, max_chars: int = MAX_FILE_CHARS) -> str:
    """Read file content and truncate if it exceeds the limit."""
    text = data_file.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        note = (
            f"\n\n[... файл обрезан: показаны первые {max_chars} из "
            f"{len(text)} символов ...]"
        )
        text = text[:max_chars] + note
    return text


def extract_report_text_naive(response_text: str) -> str:
    """For the naive method the response is already plain text."""
    return response_text


async def run_naive(
    fixture: dict,
    client: AsyncOpenAI,
    model: str = "deepseek-chat",
) -> dict[str, Any]:
    """
    Run the naive baseline for one fixture.

    Args:
        fixture: dict with keys data_file, ground_truth
        client:  AsyncOpenAI client pointed at DeepSeek
        model:   DeepSeek model name

    Returns:
        raw result dict ready for metrics computation
    """
    gt = fixture["ground_truth"]
    query: str = gt["query"]
    data_file: Path = fixture["data_file"]
    dataset_id: str = fixture["dataset_id"]

    file_content = read_file_for_prompt(data_file)

    system_prompt = (
        "Ты аналитик данных. Тебе предоставлены данные и аналитический вопрос. "
        "Проанализируй данные и дай точный, детальный ответ на русском языке. "
        "Обязательно приводи конкретные числа, проценты и статистику из данных."
    )
    user_prompt = f"Данные:\n\n{file_content}\n\nВопрос: {query}"

    t0 = time.monotonic()
    error: str | None = None
    text = ""
    tokens_in = tokens_out = 0

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=4000,
            temperature=0.3,
        )
        text = response.choices[0].message.content or ""
        if response.usage:
            tokens_in  = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
    except Exception as exc:
        error = str(exc)

    latency = time.monotonic() - t0

    return {
        "dataset_id":    dataset_id,
        "mode":          "naive",
        "latency":       latency,
        "token_count":   tokens_in + tokens_out,
        "tokens_in":     tokens_in,
        "tokens_out":    tokens_out,
        "response_text": text,
        "blocks":        [],
        "error":         error,
    }
