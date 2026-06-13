from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.document_pipeline.extractors.base import ExtractedDocument
from app.document_pipeline.extractors.pdf_extractor import PDFExtractor
from app.document_pipeline.extractors.excel_extractor import ExcelExtractor
from app.document_pipeline.extractors.csv_extractor import CSVExtractor
from app.document_pipeline.extractors.docx_extractor import DocxExtractor, TxtExtractor
from app.document_pipeline.extractors.json_extractor import JSONExtractor
from app.document_pipeline.chunker import TextChunker, TableChunker, Chunk
from app.document_pipeline.fingerprint import NumericFingerprint
from app.storage.vector_store import vector_store
from app.storage.models import UploadedFile
from app.core.logging import logger


class DocumentPipeline:
    def __init__(self):
        self.extractors = {
            "pdf": PDFExtractor(),
            "xlsx": ExcelExtractor(),
            "csv": CSVExtractor(),
            "docx": DocxExtractor(),
            "txt": TxtExtractor(),
            "json": JSONExtractor(),
        }
        self.text_chunker = TextChunker(chunk_size=512, overlap=64)
        self.table_chunker = TableChunker()

    async def process(
        self,
        db: AsyncSession,
        file_path: str,
        file_id: str,
        file_type: str,
    ) -> dict[str, Any]:
        logger.info("pipeline_start", file_id=file_id, file_type=file_type)

        # 1. Extract
        extractor = self.extractors.get(file_type)
        if not extractor:
            raise ValueError(f"Unsupported file type: {file_type}")

        extracted: ExtractedDocument = extractor.extract(file_path, file_id)

        # 2. Chunk
        all_chunks: list[Chunk] = []

        for section in extracted.sections:
            text = section.get("content", "")
            if not text.strip():
                continue
            if section.get("type") == "text":
                chunks = self.text_chunker.chunk(
                    text,
                    section_header=section.get("section_id"),
                    page=section.get("page_number"),
                )
                all_chunks.extend(chunks)

        for table in extracted.tables:
            tbl_chunks = self.table_chunker.chunk_table(
                headers=table.headers,
                rows=table.rows,
                caption=table.caption,
                page=table.page_number,
            )
            all_chunks.extend(tbl_chunks)

        # 3. Build fingerprint
        fp = NumericFingerprint()
        fp.build([{"chunk_id": c.chunk_id, "content": c.content, "page_number": c.page_number} for c in all_chunks])

        # 4. Store chunks (no embeddings — BM25-only retrieval)
        chunk_dicts = [
            {
                "chunk_id": c.chunk_id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "chunk_type": c.chunk_type,
                "numeric_density": c.numeric_density,
                "page_number": c.page_number,
                "section_header": c.section_header,
                "metadata": c.metadata,
            }
            for c in all_chunks
        ]
        if chunk_dicts:
            await vector_store.upsert_chunks(db, file_id, chunk_dicts)

        # 5. Update file record
        await db.execute(
            update(UploadedFile)
            .where(UploadedFile.id == file_id)
            .values(
                processing_status="done",
                fingerprint_json=fp.to_dict(),
                doc_structure_json={
                    "sections": len(extracted.sections),
                    "tables": len(extracted.tables),
                    "chunks": len(all_chunks),
                    "metadata": extracted.metadata,
                },
            )
        )
        await db.commit()

        logger.info("pipeline_done", file_id=file_id, chunks=len(all_chunks))
        return {
            "file_id": file_id,
            "chunks": len(all_chunks),
            "fingerprint_entries": len(fp.catalog),
            "tables": len(extracted.tables),
        }


document_pipeline = DocumentPipeline()
