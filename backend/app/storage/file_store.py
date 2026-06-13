from __future__ import annotations
import os
import shutil
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.logging import logger


class FileStore:
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, file_id: str, filename: str) -> Path:
        ext = Path(filename).suffix.lower()
        return self.upload_dir / f"{file_id}{ext}"

    async def save(self, upload_file: UploadFile, file_id: str) -> str:
        path = self._get_path(file_id, upload_file.filename or "file")
        async with aiofiles.open(path, "wb") as f:
            content = await upload_file.read()
            await f.write(content)
        logger.info("file_saved", file_id=file_id, path=str(path))
        return str(path)

    def get_path(self, file_id: str, filename: str) -> str:
        return str(self._get_path(file_id, filename))

    def delete(self, storage_path: str) -> None:
        try:
            os.remove(storage_path)
        except FileNotFoundError:
            pass

    def detect_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        mapping = {
            ".pdf": "pdf", ".xlsx": "xlsx", ".xls": "xlsx",
            ".csv": "csv", ".docx": "docx", ".doc": "docx",
            ".txt": "txt", ".json": "json",
        }
        return mapping.get(ext, "unknown")


file_store = FileStore()
