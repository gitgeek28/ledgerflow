import shutil
import subprocess

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.models import Job, Policy
from app.db.session import SessionLocal
from app.services.extraction.llm import OllamaClient
from app.services.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "ledgerflow-api"}


@router.get("/health/ready")
def ready():
    s = get_settings()
    out = {"database": False, "storage": False, "ocr": None, "llm": None, "queue": None, "policy_version": None,
           "demo_stage_pacing_ms": s.demo_stage_pacing_ms, "embedded_worker": s.embedded_worker}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            out["database"] = True
            out["policy_version"] = db.scalar(select(Policy.version).where(Policy.is_active.is_(True)))
            out["queue"] = {
                "queued": db.scalar(select(func.count()).select_from(Job).where(Job.status == "QUEUED")) or 0,
                "running": db.scalar(select(func.count()).select_from(Job).where(Job.status == "RUNNING")) or 0,
                "oldest_queued_seconds": db.scalar(select(func.extract("epoch", func.now() - func.min(Job.created_at)))
                                                   .where(Job.status == "QUEUED")),
            }
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        out["database_error"] = type(exc).__name__
    out["storage"] = get_storage().healthy()
    out["storage_backend"] = s.storage_backend
    cmd = s.tesseract_cmd or shutil.which("tesseract")
    if cmd:
        try:
            version = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5).stdout.split("\n")[0]
            out["ocr"] = {"available": True, "engine": version}
        except (OSError, subprocess.SubprocessError):
            out["ocr"] = {"available": False}
    else:
        out["ocr"] = {"available": False}
    out["llm"] = {"provider": s.llm_provider, **(OllamaClient().status() if s.llm_provider == "ollama" else {})}
    out["status"] = "ready" if out["database"] and out["storage"] else "degraded"
    return out
