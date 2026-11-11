"""Every catalogued scenario goes through the real intake -> queue -> worker -> pipeline and must produce the
labelled outcome. Prerequisite invoices (e.g. the original of a duplicate) are processed first."""
import pytest
import yaml
from sqlalchemy import select

from app.core.config import REPO_DIR
from app.db.models import Invoice, User
from app.db.session import SessionLocal
from app.services.ingestion import ingest
from tests.conftest import drain

CAT = {c["id"]: c for c in yaml.safe_load((REPO_DIR / "data/fixtures/scenarios.yaml").read_text())}


def _ingest(sid: str):
    c = CAT[sid]
    data = (REPO_DIR / "data/fixtures" / c["file"]).read_bytes()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "AP_ANALYST"))
        r = ingest(db, filename=c["file"].split("/")[-1], content_type="application/pdf", data=data, user=user)
        return r.invoice.id, r.duplicate


@pytest.mark.parametrize("sid", [k for k in CAT if k != "S02"])
def test_scenario_outcome(db_reset, sid):
    for pre in CAT[sid].get("prerequisites", []):
        _ingest(pre)
        drain()
    inv_id, dup = _ingest(sid)
    assert not dup
    drain()
    exp = CAT[sid]["expect"]
    with SessionLocal() as db:
        inv = db.get(Invoice, inv_id)
        assert inv.status == exp["status"], (inv.status, inv.reason_codes, inv.decision_summary)
        for code in exp.get("codes", []):
            assert code in inv.reason_codes
        if exp.get("codes_any"):
            assert set(exp["codes_any"]) & set(inv.reason_codes)
        for code in exp.get("codes_absent", []):
            assert code not in inv.reason_codes
        if "match_mode" in exp:
            assert inv.match_mode == exp["match_mode"]
        if "priority" in exp:
            assert inv.priority == exp["priority"]
        if "grand_total" in exp:
            assert str(inv.grand_total) == exp["grand_total"]
        if "line_count" in exp:
            assert len(inv.lines) == exp["line_count"]


def test_exact_duplicate_file_creates_no_second_invoice(db_reset):
    first, _ = _ingest("S01")
    drain()
    again, dup = _ingest("S01")
    assert dup and again == first
    with SessionLocal() as db:
        assert db.query(Invoice).count() == 1
