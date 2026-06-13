from __future__ import annotations
import json
import uuid
from typing import Any
from app.document_pipeline.extractors.base import BaseExtractor, ExtractedDocument, ExtractedTable
from app.core.logging import logger


def _flatten(obj: Any, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten nested dict/list into dot-notation keys."""
    items: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}{sep}{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, new_key, sep))
            else:
                items[new_key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{prefix}{sep}{i}" if prefix else str(i)
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, new_key, sep))
            else:
                items[new_key] = v
    else:
        items[prefix] = obj
    return items


def _is_records_array(data: Any) -> bool:
    """True if data is a list of dicts with at least one common key."""
    if not isinstance(data, list) or len(data) == 0:
        return False
    if not all(isinstance(r, dict) for r in data):
        return False
    return True


class JSONExtractor(BaseExtractor):
    @property
    def supported_types(self) -> list[str]:
        return ["json"]

    def extract(self, file_path: str, file_id: str) -> ExtractedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_error", file_id=file_id, error=str(e))
            return ExtractedDocument(
                file_id=file_id,
                filename=file_path,
                file_type="json",
                raw_text=raw[:5000],
                sections=[{"section_id": "raw", "content": raw[:5000], "type": "text"}],
                metadata={"error": str(e)},
            )

        tables: list[ExtractedTable] = []
        sections: list[dict] = []
        text_parts: list[str] = []

        # ── Case 1: array of records → tabular data ──────────────────────────
        if _is_records_array(data):
            tables, sections, text_parts = self._handle_records(data, file_id)

        # ── Case 2: dict with array values → multiple tables ─────────────────
        elif isinstance(data, dict):
            for key, val in data.items():
                if _is_records_array(val):
                    tbl, sec, txt = self._handle_records(val, file_id, caption=str(key))
                    tables.extend(tbl)
                    sections.extend(sec)
                    text_parts.extend(txt)
                else:
                    # Flatten scalar/nested fields as key-value text
                    flat = _flatten({key: val})
                    kv_text = "\n".join(f"{k}: {v}" for k, v in flat.items())
                    text_parts.append(kv_text)
                    sections.append({
                        "section_id": key,
                        "content": kv_text,
                        "type": "text",
                    })

        # ── Case 3: primitive or other ────────────────────────────────────────
        else:
            text = json.dumps(data, ensure_ascii=False, indent=2)[:5000]
            text_parts.append(text)
            sections.append({"section_id": "main", "content": text, "type": "text"})

        raw_text = "\n\n".join(text_parts)[:20000]
        logger.info("json_extracted", file_id=file_id, tables=len(tables), sections=len(sections))

        return ExtractedDocument(
            file_id=file_id,
            filename=file_path,
            file_type="json",
            raw_text=raw_text,
            tables=tables,
            sections=sections,
            metadata={
                "top_level_type": type(data).__name__,
                "tables": len(tables),
                "sections": len(sections),
            },
        )

    def _handle_records(
        self,
        records: list[dict],
        file_id: str,
        caption: str | None = None,
    ) -> tuple[list[ExtractedTable], list[dict], list[str]]:
        """Convert a list of dicts into a table + text section."""
        # Collect all keys preserving order
        all_keys: list[str] = []
        seen: set[str] = set()
        for rec in records:
            for k in rec.keys():
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        headers = [str(k) for k in all_keys]
        rows = [
            [str(rec.get(k, "")) for k in all_keys]
            for rec in records[:1000]  # cap at 1000 rows
        ]

        table = ExtractedTable(
            table_id=str(uuid.uuid4()),
            headers=headers,
            rows=rows,
            caption=caption,
        )

        # Also represent as readable text for BM25 retrieval
        lines = ["\t".join(headers)]
        for row in rows[:200]:
            lines.append("\t".join(row))
        text = "\n".join(lines)

        section = {
            "section_id": caption or "records",
            "content": text,
            "type": "table",
        }

        return [table], [section], [text]
