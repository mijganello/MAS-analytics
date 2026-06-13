from __future__ import annotations
import pandas as pd
import openpyxl
import uuid
from app.document_pipeline.extractors.base import BaseExtractor, ExtractedDocument, ExtractedTable
from app.core.logging import logger


class ExcelExtractor(BaseExtractor):
    @property
    def supported_types(self) -> list[str]:
        return ["xlsx"]

    def extract(self, file_path: str, file_id: str) -> ExtractedDocument:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        tables = []
        sections = []
        all_text = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
            df = df.dropna(how="all")

            if df.empty:
                continue

            headers = [str(c) for c in df.columns.tolist()]
            rows = [[str(v) if pd.notna(v) else "" for v in row] for row in df.values.tolist()]

            tables.append(ExtractedTable(
                table_id=str(uuid.uuid4()),
                headers=headers,
                rows=rows,
                caption=sheet_name,
            ))
            sections.append({
                "section_id": f"sheet_{sheet_name}",
                "sheet_name": sheet_name,
                "content": df.to_string(index=False),
                "type": "table",
                "rows": len(rows),
                "cols": len(headers),
            })
            all_text.append(f"Sheet: {sheet_name}\n{df.to_string(index=False)}")

        raw_text = "\n\n".join(all_text)
        logger.info("excel_extracted", file_id=file_id, sheets=len(tables))
        return ExtractedDocument(
            file_id=file_id,
            filename=file_path,
            file_type="xlsx",
            raw_text=raw_text,
            tables=tables,
            sections=sections,
            metadata={"sheets": wb.sheetnames},
        )
