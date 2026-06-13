from __future__ import annotations
import pandas as pd
import chardet
import uuid
from app.document_pipeline.extractors.base import BaseExtractor, ExtractedDocument, ExtractedTable
from app.core.logging import logger


class CSVExtractor(BaseExtractor):
    @property
    def supported_types(self) -> list[str]:
        return ["csv"]

    def _detect_encoding(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            raw = f.read(50000)
        result = chardet.detect(raw)
        return result.get("encoding") or "utf-8"

    def extract(self, file_path: str, file_id: str) -> ExtractedDocument:
        encoding = self._detect_encoding(file_path)

        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                if len(df.columns) > 1:
                    break
            except Exception:
                continue
        else:
            df = pd.read_csv(file_path, encoding=encoding)

        df = df.dropna(how="all")
        headers = [str(c) for c in df.columns.tolist()]
        rows = [[str(v) if pd.notna(v) else "" for v in row] for row in df.values.tolist()]

        table = ExtractedTable(
            table_id=str(uuid.uuid4()),
            headers=headers,
            rows=rows,
        )

        raw_text = df.to_string(index=False)
        logger.info("csv_extracted", file_id=file_id, rows=len(rows), cols=len(headers))

        return ExtractedDocument(
            file_id=file_id,
            filename=file_path,
            file_type="csv",
            raw_text=raw_text,
            tables=[table],
            sections=[{"section_id": "main", "content": raw_text, "type": "table"}],
            metadata={"rows": len(rows), "columns": len(headers), "encoding": encoding},
        )
