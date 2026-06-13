from __future__ import annotations
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.models import DocumentChunk
from app.core.logging import logger


class VectorStore:
    async def upsert_chunks(
        self,
        session: AsyncSession,
        file_id: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Store document chunks. Embeddings are optional (BM25-only mode)."""
        emb_lookup = {i: e for i, e in enumerate(embeddings or [])}
        for i, chunk_data in enumerate(chunks):
            chunk = DocumentChunk(
                id=chunk_data["chunk_id"],
                file_id=file_id,
                chunk_index=chunk_data["chunk_index"],
                chunk_type=chunk_data.get("chunk_type", "text"),
                content=chunk_data["content"],
                metadata_json=chunk_data.get("metadata", {}),
                embedding=emb_lookup.get(i),
                numeric_density=chunk_data.get("numeric_density", 0.0),
                page_number=chunk_data.get("page_number"),
                section_header=chunk_data.get("section_header"),
            )
            await session.merge(chunk)
        await session.commit()
        logger.info("upserted_chunks", file_id=file_id, count=len(chunks))

    async def get_chunks_by_file(
        self,
        session: AsyncSession,
        file_id: str,
    ) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.file_id == file_id).order_by(DocumentChunk.chunk_index)
        result = await session.execute(stmt)
        return list(result.scalars().all())


vector_store = VectorStore()
