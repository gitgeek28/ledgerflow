"""Document storage behind one interface.

* LocalStorage (default for local runs): files under STORAGE_DIR.
* DatabaseStorage (STORAGE_BACKEND=db, used on hosts with ephemeral disks): bytes in the `stored_documents`
  table, so uploads survive redeploys without an extra service. Demo invoices are 3-400 KB.
Keys are always server-generated; client filenames never become paths.
"""
import contextlib
import tempfile
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import text

from app.core.config import get_settings


class DocumentStorage(Protocol):
    def put(self, data: bytes, suffix: str = ".pdf") -> str: ...
    def read(self, key: str) -> bytes: ...
    def local_path(self, key: str) -> contextlib.AbstractContextManager[Path]: ...
    def healthy(self) -> bool: ...


def _new_key(suffix: str) -> str:
    return f"{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}{suffix}"


class LocalStorage:
    def __init__(self, base: Path | None = None):
        self.base = (base or get_settings().storage_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str = ".pdf") -> str:
        key = _new_key(suffix)
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

    @contextlib.contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        yield self.path(key)

    def healthy(self) -> bool:
        try:
            probe = self.base / ".probe"
            probe.write_text("ok")
            probe.unlink()
            return True
        except OSError:
            return False


class DatabaseStorage:
    def put(self, data: bytes, suffix: str = ".pdf") -> str:
        from app.db.session import engine
        key = _new_key(suffix)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO stored_documents (key, content, size_bytes) VALUES (:k, :c, :s)"),
                         {"k": key, "c": data, "s": len(data)})
        return key

    def read(self, key: str) -> bytes:
        from app.db.session import engine
        with engine.connect() as conn:
            row = conn.execute(text("SELECT content FROM stored_documents WHERE key = :k"), {"k": key}).first()
        if row is None:
            raise FileNotFoundError(key)
        return bytes(row[0])

    @contextlib.contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        """PDF/OCR libraries read from a path, so stream the bytes into a private temp file for the stage."""
        data = self.read(key)
        with tempfile.NamedTemporaryFile(suffix=".pdf", prefix="lf-") as fh:
            fh.write(data)
            fh.flush()
            yield Path(fh.name)

    def healthy(self) -> bool:
        from app.db.session import engine
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM stored_documents LIMIT 1"))
            return True
        except Exception:  # noqa: BLE001 - reported as unhealthy, not raised
            return False


def get_storage() -> DocumentStorage:
    return DatabaseStorage() if get_settings().storage_backend == "db" else LocalStorage()
