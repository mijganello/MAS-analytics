from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass
from typing import Any
from rapidfuzz import process, fuzz
from app.core.logging import logger


@dataclass
class NumericEntry:
    value: float
    unit: str
    source_chunk_id: str
    source_location: str
    value_hash: str
    extraction_confidence: float = 1.0
    context: str = ""


@dataclass
class VerificationResult:
    status: str              # VERIFIED | MISMATCH | NOT_FOUND
    matched_entry: NumericEntry | None = None
    claimed_value: float = 0.0
    actual_value: float | None = None
    confidence: float = 0.0


class NumericFingerprint:
    """Immutable catalog of all numeric values in a document."""

    def __init__(self):
        self.catalog: dict[str, NumericEntry] = {}

    def build(self, chunks: list[dict[str, Any]]) -> None:
        """Extract all numbers from chunks and index by normalized context."""
        # Pattern: число с опциональной единицей, предшествует контекст
        pattern = re.compile(
            r'([^\d]{0,60}?)'                   # контекст до числа
            r'(\b\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d+)?|\b\d+(?:[.,]\d+)?)'  # число
            r'\s*([%$€₽млн.мрд.тыс.]*)',        # единица
            re.UNICODE
        )

        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            page = chunk.get("page_number")

            for match in pattern.finditer(content):
                ctx_raw, num_str, unit = match.group(1), match.group(2), match.group(3)
                try:
                    # Normalize number: remove spaces/commas as thousand separators
                    clean = num_str.replace(" ", "").replace(",", ".")
                    value = float(clean)
                except ValueError:
                    continue

                ctx_clean = re.sub(r'\s+', ' ', ctx_raw).strip().lower()[-50:]
                if not ctx_clean:
                    ctx_clean = f"chunk_{chunk_id[:8]}"

                entry = NumericEntry(
                    value=value,
                    unit=unit.strip(),
                    source_chunk_id=chunk_id,
                    source_location=f"chunk {chunk_id[:8]}, page {page}",
                    value_hash=hashlib.sha256(f"{value}{ctx_clean}".encode()).hexdigest()[:16],
                    context=ctx_clean,
                )

                key = self._normalize_key(f"{ctx_clean} {value}")
                self.catalog[key] = entry

        logger.info("fingerprint_built", entries=len(self.catalog))

    def verify(self, claimed_value: float, context_hint: str) -> VerificationResult:
        if not self.catalog:
            return VerificationResult(status="NOT_FOUND", claimed_value=claimed_value)

        norm_hint = context_hint.lower().strip()
        keys = list(self.catalog.keys())

        # Fuzzy match context
        matches = process.extract(norm_hint, keys, scorer=fuzz.partial_ratio, limit=5)

        for match_key, score, _ in matches:
            if score < 40:
                continue
            entry = self.catalog[match_key]
            # Value comparison with tolerance
            if abs(entry.value - claimed_value) <= max(abs(entry.value) * 0.001, 0.01):
                return VerificationResult(
                    status="VERIFIED",
                    matched_entry=entry,
                    claimed_value=claimed_value,
                    actual_value=entry.value,
                    confidence=score / 100,
                )
            else:
                return VerificationResult(
                    status="MISMATCH",
                    matched_entry=entry,
                    claimed_value=claimed_value,
                    actual_value=entry.value,
                    confidence=score / 100,
                )

        return VerificationResult(status="NOT_FOUND", claimed_value=claimed_value)

    def to_dict(self) -> dict:
        return {k: vars(v) for k, v in self.catalog.items()}

    @staticmethod
    def from_dict(data: dict) -> "NumericFingerprint":
        fp = NumericFingerprint()
        for k, v in data.items():
            fp.catalog[k] = NumericEntry(**v)
        return fp

    @staticmethod
    def _normalize_key(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip().lower()
