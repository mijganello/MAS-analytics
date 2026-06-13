from __future__ import annotations
from app.core.logging import logger


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """No-op embedder — returns empty embeddings. BM25-only retrieval is used instead."""
    return []


def embed_query(text: str) -> list[float]:
    return []
