from __future__ import annotations
import re
from typing import Any
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.vector_store import vector_store
from app.storage.models import DocumentChunk
from app.core.logging import logger


class HybridRetriever:
    """BM25 keyword retrieval (fast, no local ML model required)."""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        file_ids: list[str],
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        all_chunks: list[DocumentChunk] = []
        for file_id in file_ids:
            chunks = await vector_store.get_chunks_by_file(db, file_id)
            all_chunks.extend(chunks)

        if not all_chunks:
            return []

        bm25_results = self._bm25_search(query, all_chunks, top_k=top_k)

        return [
            {
                "chunk_id": c.id,
                "content": c.content,
                "chunk_type": c.chunk_type,
                "page_number": c.page_number,
                "section_header": c.section_header,
                "rrf_score": 1.0,
                "file_id": c.file_id,
                "metadata": c.metadata_json or {},
            }
            for c in bm25_results
        ]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer: lowercase words (supports Cyrillic + Latin)."""
        return re.findall(r"[а-яёА-ЯЁa-zA-Z0-9]+", text.lower())

    def _bm25_search(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[DocumentChunk]:
        if not chunks:
            return []
        tokenized = [self._tokenize(c.content) for c in chunks]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(self._tokenize(query))
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [chunks[i] for i in ranked_idx]


retriever = HybridRetriever()
