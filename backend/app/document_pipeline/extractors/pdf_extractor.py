from __future__ import annotations
import fitz  # PyMuPDF
import pdfplumber
import uuid
from app.document_pipeline.extractors.base import BaseExtractor, ExtractedDocument, ExtractedTable
from app.core.logging import logger


class PDFExtractor(BaseExtractor):
    @property
    def supported_types(self) -> list[str]:
        return ["pdf"]

    def extract(self, file_path: str, file_id: str) -> ExtractedDocument:
        doc = fitz.open(file_path)
        sections = []
        full_text_parts = []

        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            if text.strip():
                full_text_parts.append(text)
                sections.append({
                    "section_id": f"page_{page_num}",
                    "page_number": page_num,
                    "content": text,
                    "type": "text",
                })

        doc.close()

        # Extract tables via pdfplumber
        tables = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                for t_idx, table in enumerate(page.extract_tables()):
                    if table and len(table) > 1:
                        headers = [str(h or "") for h in table[0]]
                        rows = [[str(c or "") for c in row] for row in table[1:]]
                        tables.append(ExtractedTable(
                            table_id=str(uuid.uuid4()),
                            headers=headers,
                            rows=rows,
                            page_number=page_num,
                        ))

        raw_text = "\n".join(full_text_parts)
        logger.info("pdf_extracted", file_id=file_id, pages=len(sections), tables=len(tables))

        return ExtractedDocument(
            file_id=file_id,
            filename=file_path,
            file_type="pdf",
            raw_text=raw_text,
            tables=tables,
            sections=sections,
            metadata={"total_pages": len(sections)},
        )
