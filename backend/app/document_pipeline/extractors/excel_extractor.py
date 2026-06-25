from __future__ import annotations
import pandas as pd
import openpyxl
import uuid
from app.document_pipeline.extractors.base import BaseExtractor, ExtractedDocument, ExtractedTable
from app.core.logging import logger


def _find_header_row(file_path: str, sheet_name: str) -> int:
    """Return the 0-based row index of the real column-header row.

    Many Excel reports have a merged title in row 0 (e.g.
    "ВЕДОМОСТЬ УСПЕВАЕМОСТИ — 1 КУРС | Направление: …") followed by an
    empty row, then the actual column headers in row 2.

    Strategy: scan from the top and return the first row index where at
    least MIN_HEADER_CELLS cells are non-empty.  Title rows typically have
    only 1 populated cell (the merged title); real header rows have one
    cell per column.
    """
    MIN_HEADER_CELLS = 3
    df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    for idx in range(min(10, len(df_raw))):
        row = df_raw.iloc[idx]
        non_empty = [v for v in row if pd.notna(v) and str(v).strip()]
        if len(non_empty) >= MIN_HEADER_CELLS:
            return idx
    return 0  # fallback: first row


def _clean_header(name: object) -> str:
    """Normalise a column name: flatten newlines, collapse whitespace.

    Grade-sheet headers often carry multi-line text such as
    'Осень\\nМатематический анализ I\\n(5 з.е.)'.  We join the lines
    with a space so the column is still readable but compact.
    """
    s = str(name).strip()
    # Replace newlines and tabs with a single space
    s = " ".join(s.splitlines())
    # Collapse multiple spaces
    import re as _re
    s = _re.sub(r"\s{2,}", " ", s)
    return s


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
            header_row = _find_header_row(file_path, sheet_name)
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header_row,
            )
            df = df.dropna(how="all")

            if df.empty:
                continue

            # Clean column names: flatten multi-line headers, strip whitespace
            df.columns = [_clean_header(c) for c in df.columns]
            # Drop columns whose cleaned name is entirely blank
            df = df.loc[:, df.columns.str.strip() != ""]

            headers = df.columns.tolist()
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
