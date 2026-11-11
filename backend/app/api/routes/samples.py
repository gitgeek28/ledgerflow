"""Synthetic sample invoices for demos. The UI downloads one and uploads it through the normal intake endpoint,
so samples take exactly the same path as any other file."""
from functools import lru_cache

import yaml
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.config import REPO_DIR
from app.core.errors import NotFound
from app.core.security import current_user
from app.db.models import User

router = APIRouter(prefix="/samples", tags=["samples"])
FIXTURES = REPO_DIR / "data" / "fixtures"


@lru_cache
def _catalogue() -> list[dict]:
    path = FIXTURES / "scenarios.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else []


@router.get("")
def list_samples(_: User = Depends(current_user)):
    out = []
    for c in _catalogue():
        out.append({"id": c["id"], "title": c["title"], "group": c["group"], "description": c.get("description", ""),
                    "filename": c["file"].split("/")[-1], "expected_status": c.get("expect", {}).get("status"),
                    "expected_codes": c.get("expect", {}).get("codes") or c.get("expect", {}).get("codes_any") or [],
                    "prerequisites": c.get("prerequisites", [])})
    return out


@router.get("/{sample_id}/file")
def sample_file(sample_id: str, _: User = Depends(current_user)):
    c = next((c for c in _catalogue() if c["id"] == sample_id), None)
    if not c:
        raise NotFound("Sample not found.")
    path = (FIXTURES / c["file"]).resolve()
    if not path.is_relative_to(FIXTURES.resolve()) or not path.exists():
        raise NotFound("Sample file missing; run the fixture generator.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
