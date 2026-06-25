from __future__ import annotations
import re
import uuid
from typing import Any
from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    chunk_index: int
    content: str
    chunk_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)
    numeric_density: float = 0.0
    page_number: int | None = None
    section_header: str | None = None


class TextChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, section_header: str | None = None, page: int | None = None) -> list[Chunk]:
        # Split by sentences then merge into chunks
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        chunks = []
        current = []
        current_len = 0
        idx = 0

        for sent in sentences:
            words = sent.split()
            if current_len + len(words) > self.chunk_size and current:
                content = " ".join(current)
                chunks.append(self._make_chunk(content, idx, "text", section_header, page))
                idx += 1
                # Overlap: keep last N words
                overlap_words = current[-self.overlap:] if len(current) > self.overlap else current
                current = overlap_words + words
                current_len = len(current)
            else:
                current.extend(words)
                current_len += len(words)

        if current:
            content = " ".join(current)
            chunks.append(self._make_chunk(content, idx, "text", section_header, page))

        return chunks if chunks else [self._make_chunk(text, 0, "text", section_header, page)]

    def _make_chunk(self, content: str, idx: int, ctype: str, header: str | None, page: int | None) -> Chunk:
        nums = re.findall(r'\b\d+[\.,]?\d*\b', content)
        words = content.split()
        density = len(nums) / max(len(words), 1)
        return Chunk(
            chunk_id=str(uuid.uuid4()),
            chunk_index=idx,
            content=content,
            chunk_type=ctype,
            numeric_density=density,
            page_number=page,
            section_header=header,
            metadata={"page": page, "section": header},
        )


class TableChunker:
    # Each chunk must fit inside a single LLM context slot (≈ 3 000 chars).
    # With wide Excel tables (17 cols × ~140 chars/row + 250-char header) the
    # safe limit is around 15 rows: 250 + 15×140 = 2 350 chars.
    # Smaller chunks also improve BM25 recall: chunks covering a specific subset
    # of teachers rank higher for targeted queries than one huge chunk.
    MAX_ROWS_PER_CHUNK = 15

    def chunk_table(self, headers: list[str], rows: list[list[str]], caption: str | None = None, page: int | None = None) -> list[Chunk]:
        chunks = []
        idx = 0
        header_str = " | ".join(headers)

        for start in range(0, max(len(rows), 1), self.MAX_ROWS_PER_CHUNK):
            batch = rows[start:start + self.MAX_ROWS_PER_CHUNK]
            content_rows = [header_str]
            for row in batch:
                content_rows.append(" | ".join(str(c) for c in row))
            content = "\n".join(content_rows)

            all_vals = " ".join(str(c) for row in batch for c in row)
            nums = re.findall(r'\b\d+[\.,]?\d*\b', all_vals)
            words = all_vals.split()
            density = len(nums) / max(len(words), 1)

            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                chunk_index=idx,
                content=content,
                chunk_type="table",
                numeric_density=density,
                page_number=page,
                section_header=caption,
                metadata={"headers": headers, "caption": caption, "row_start": start},
            ))
            idx += 1

        return chunks
