from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedTable:
    table_id: str
    headers: list[str]
    rows: list[list[Any]]
    page_number: int | None = None
    caption: str | None = None


@dataclass
class ExtractedDocument:
    file_id: str
    filename: str
    file_type: str
    raw_text: str
    tables: list[ExtractedTable] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    numeric_values: list[dict[str, Any]] = field(default_factory=list)


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str, file_id: str) -> ExtractedDocument:
        ...

    def supports(self, file_type: str) -> bool:
        return file_type in self.supported_types

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        ...
