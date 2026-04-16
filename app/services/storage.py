"""
Local filesystem storage service (replaces MinIO).
"""
import shutil
from pathlib import Path
from typing import Optional

from core.config import settings


class StorageService:

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_data: bytes, filename: str, doc_id: str) -> str:
        doc_dir = self.upload_dir / str(doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        filepath = doc_dir / filename
        with open(filepath, "wb") as f:
            f.write(file_data)
        return str(filepath.relative_to(self.upload_dir))

    def get_full_path(self, relative_path: str) -> str:
        return str(self.upload_dir / relative_path)

    def read_file(self, relative_path: str) -> bytes:
        with open(self.upload_dir / relative_path, "rb") as f:
            return f.read()

    def delete_file(self, relative_path: str) -> bool:
        try:
            path = self.upload_dir / relative_path
            if path.exists():
                # Remove the entire document directory
                doc_dir = path.parent
                if doc_dir != self.upload_dir:
                    shutil.rmtree(doc_dir)
                else:
                    path.unlink()
            return True
        except Exception:
            return False


storage_service = StorageService()
