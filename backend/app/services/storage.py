"""Document storage behind an interface; local filesystem today, object storage later."""
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class DocumentStorage(Protocol):
    def put(self, data: bytes, suffix: str = ".pdf") -> str: ...
    def path(self, key: str) -> Path: ...
    def read(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self, base: Path | None = None):
        self.base = (base or get_settings().storage_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str = ".pdf") -> str:
        now = datetime.now(UTC)
        key = f"{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"  # server-generated; never derived from the client filename
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(target)
        return key

    def path(self, key: str) -> Path:
        p = (self.base / key).resolve()
        if not p.is_relative_to(self.base):
            raise ValueError("Invalid storage key")
        return p

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()


def get_storage() -> DocumentStorage:
    return LocalStorage()
