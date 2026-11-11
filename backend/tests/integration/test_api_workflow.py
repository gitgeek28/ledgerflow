import json

from sqlalchemy import text

from app.db.models import AuditEvent, Job, ProcessingRun
from app.db.session import SessionLocal
from tests.conftest import drain, login, upload


def _detail(client, h, inv_id):
    r = client.get(f"/api/invoices/{inv_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_required_and_auditor_is_read_only(client):
    assert client.get("/api/invoices").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "aisha.rao@kestrel.example", "password": "nope"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "UNAUTHORIZED"
    h = login(client, "meera.joshi@kestrel.example")
    assert upload(client, h, "S01").status_code == 403


def test_upload_validation_rejects_non_pdf(client):
    h = login(client)
    r = client.post("/api/invoices", headers=h, files={"file": ("x.pdf", b"hello world", "application/pdf")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_INVALID"
    r = client.post("/api/invoices", headers=h, files={"file": ("x.txt", b"%PDF-1.4", "text/plain")})
    assert r.status_code == 422


def test_happy_path_persists_run_events_checks_and_audit(client):
    h = login(client)
    r = upload(client, h, "S01")
    assert r.status_code == 201 and r.json()["outcome"] == "CREATED"
    inv_id, run_id = r.json()["invoice_id"], r.json()["run_id"]
    drain()
    d = _detail(client, h, inv_id)
    assert d["status"] == "READY_FOR_APPROVAL" and d["match_mode"] == "THREE_WAY"
    assert d["latest_run"]["policy_version"] == 1 and d["latest_run"]["extractor"].startswith("rules-v1")
    assert all(c["status"] == "PASS" or c["outcome"] == "NONE" for c in d["checks"])
    events = client.get(f"/api/runs/{run_id}/events", headers=h).json()
    completed = [e["stage"] for e in events if e["event_type"] == "STAGE_COMPLETED"]
    assert completed == ["RECEIVED", "FILE_VALIDATION", "TEXT_EXTRACTION", "FIELD_EXTRACTION", "VENDOR_RESOLUTION",
                         "PO_MATCHING", "FINANCIAL_RECONCILIATION", "DUPLICATE_CHECK", "RISK_AND_POLICY_CHECKS",
                         "DECISION"]
    assert client.get(f"/api/invoices/{inv_id}/document", headers=h).content[:5] == b"%PDF-"
    actions = [a["action"] for a in client.get(f"/api/invoices/{inv_id}/audit", headers=h).json()]
    assert "INVOICE_RECEIVED" in actions and "SYSTEM_DECISION" in actions
    # exact duplicate upload is linked, not created
    dup = upload(client, h, "S01", filename="resent.pdf").json()
    assert dup["outcome"] == "DUPLICATE_FILE" and dup["invoice_id"] == inv_id


def test_sse_stream_resumes_after_last_event_id(client):
    h = login(client)
    run_id = upload(client, h, "S01").json()["run_id"]
    drain()
    with client.stream("GET", f"/api/runs/{run_id}/events/stream", headers=h) as s:
        ids = [int(line[4:]) for line in s.iter_lines() if line.startswith("id: ")]
    assert ids == sorted(ids) and len(ids) >= 20
    with client.stream("GET", f"/api/runs/{run_id}/events/stream", headers={**h, "Last-Event-ID": str(ids[4])}) as s:
        resumed = [int(line[4:]) for line in s.iter_lines() if line.startswith("id: ")]
    assert resumed == ids[5:]


def test_price_variance_review_accept_and_two_person_approval(client):
    analyst = login(client)
    inv_id = upload(client, analyst, "S09").json()["invoice_id"]
    drain()
    d = _detail(client, analyst, inv_id)
    assert d["status"] == "NEEDS_REVIEW" and "PRICE_VARIANCE_EXCEEDED" in d["reason_codes"]
    pv = next(c for c in d["checks"] if c["code"] == "PRICE_VARIANCE_EXCEEDED" and c["status"] == "FAIL")
    assert pv["expected"] == "42,000.00" and pv["actual"] == "43,500.00" and pv["threshold"] == "+2.00%"
    # PO balance is exceeded too -> analyst cannot override that blocker
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=analyst,
                    json={"action": "MARK_READY", "reason": "Price increase agreed by buyer"})
    assert r.status_code == 403
    manager = login(client, "vikram.iyer@kestrel.example")
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=manager,
                    json={"action": "MARK_READY", "reason": "Rate revision approved; PO amendment raised"})
    assert r.status_code == 200 and r.json()["status"] == "READY_FOR_APPROVAL"
    # separation of duties: the same manager cannot approve
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=manager, json={"action": "APPROVE"})
    assert r.status_code == 403
    # value above threshold: analyst cannot approve either
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=analyst, json={"action": "APPROVE"})
    assert r.status_code == 403
    audit = [a["action"] for a in client.get(f"/api/invoices/{inv_id}/audit", headers=analyst).json()]
    assert "OVERRIDE_AND_MARK_READY" in audit


def test_reject_requires_reason_and_releases_nothing_twice(client):
    h = login(client)
    inv_id = upload(client, h, "S10").json()["invoice_id"]
    drain()
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h, json={"action": "REJECT"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h,
                    json={"action": "REQUEST_INFO", "note": "ask for corrected invoice"})
    assert r.status_code == 200 and "DRAFT - NOT SENT" in r.json()["draft"] and r.json()["status"] == "ON_HOLD"
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h,
                    json={"action": "REJECT", "reason": "Totals do not reconcile; corrected invoice requested"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h, json={"action": "REJECT", "reason": "again"})
    assert r.status_code == 409


def test_select_po_reruns_deterministic_checks(client):
    h = login(client)
    inv_id = upload(client, h, "S06").json()["invoice_id"]
    drain()
    d = _detail(client, h, inv_id)
    assert d["status"] == "NEEDS_REVIEW"
    cands = d["latest_run"]["stage_outputs"]["PO_MATCHING"]["candidates"]
    assert {c["po_number"] for c in cands[:2]} == {"PO-450130", "PO-450131"}
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h,
                    json={"action": "SELECT_PO", "po_id": cands[0]["po_id"], "reason": "Confirmed with logistics"})
    assert r.status_code == 200 and r.json()["run_id"]
    drain()
    d = _detail(client, h, inv_id)
    assert d["status"] == "READY_FOR_APPROVAL" and d["po_selected_by_human"] and d["latest_run"]["attempt"] == 2
    assert d["latest_run"]["trigger"] == "REEVALUATION"


def test_correct_low_confidence_field(client):
    h = login(client)
    inv_id = upload(client, h, "S07").json()["invoice_id"]
    drain()
    d = _detail(client, h, inv_id)
    assert d["status"] == "NEEDS_REVIEW"
    r = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h,
                    json={"action": "CORRECT_FIELD", "field": "invoice_number", "value": "SPI/1311/26",
                          "reason": "Read from the paper original"})
    assert r.status_code == 200
    drain()
    d = _detail(client, h, inv_id)
    assert d["invoice_number"] == "SPI/1311/26"
    assert "LOW_EXTRACTION_CONFIDENCE" not in d["reason_codes"] or d["status"] != "NEEDS_REVIEW"
    bad = client.post(f"/api/invoices/{inv_id}/review-actions", headers=h,
                      json={"action": "CORRECT_FIELD", "field": "invoice_date", "value": "31/31/2026"})
    assert bad.status_code in (409, 422)


def test_failed_run_is_not_retryable_for_corrupt_pdf(client):
    h = login(client)
    r = upload(client, h, "S12")
    inv_id, run_id = r.json()["invoice_id"], r.json()["run_id"]
    drain()
    d = _detail(client, h, inv_id)
    assert d["status"] == "FAILED" and d["latest_run"]["retryable"] is False
    assert "not a business rejection" in d["decision_summary"]
    r = client.post(f"/api/runs/{run_id}/retry", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_TRANSITION"


def test_retryable_failure_creates_new_attempt_once(client, monkeypatch):
    from app.services.extraction import document

    h = login(client)

    def boom(*a, **k):
        raise document.OCRUnavailable("simulated OCR outage")
    monkeypatch.setattr("app.services.workflow.stages.load_document", boom)
    r = upload(client, h, "S01")
    run_id, inv_id = r.json()["run_id"], r.json()["invoice_id"]
    drain()
    assert _detail(client, h, inv_id)["latest_run"]["retryable"] is True
    monkeypatch.undo()
    r1 = client.post(f"/api/runs/{run_id}/retry", headers=h)
    assert r1.status_code == 201 and r1.json()["attempt"] == 2
    r2 = client.post(f"/api/runs/{run_id}/retry", headers=h)
    assert r2.status_code == 409  # already in progress / not latest
    drain()
    assert _detail(client, h, inv_id)["status"] == "READY_FOR_APPROVAL"


def test_audit_events_are_immutable(client):
    h = login(client)
    upload(client, h, "S01")
    with SessionLocal() as db:
        try:
            db.execute(text("UPDATE audit_events SET note = 'tampered'"))
            db.commit()
            raise AssertionError("update should have been blocked")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            assert "append-only" in str(exc)
        assert db.query(AuditEvent).filter(AuditEvent.note == "tampered").count() == 0


def test_worker_lease_expiry_resumes_run(client):
    h = login(client)
    run_id = upload(client, h, "S01").json()["run_id"]
    with SessionLocal() as db:  # simulate a worker that claimed the job and died mid-run
        db.execute(text("UPDATE jobs SET status='RUNNING', attempts=1, lease_until=now() - interval '1 minute'"))
        db.execute(text("UPDATE processing_runs SET status='RUNNING', current_stage='TEXT_EXTRACTION'"))
        db.commit()
    drain()
    with SessionLocal() as db:
        run = db.get(ProcessingRun, run_id)
        assert run.status == "COMPLETED" and run.decision == "READY_FOR_APPROVAL"
        assert db.query(Job).filter(Job.run_id == run.id).one().attempts == 2
    events = client.get(f"/api/runs/{run_id}/events", headers=h).json()
    assert any(e["event_type"] == "RUN_RESUMED" for e in events)


def test_concurrent_split_invoices_cannot_double_consume(client):
    """Two invoices each claiming the full remaining quantity of the same PO: only one may reserve it."""
    from app.seed.fixtures import Doc, render_spec  # noqa: F401
    from app.seed.scenarios import SPEC_BY_ID
    import dataclasses
    import tempfile
    from pathlib import Path
    h = login(client)
    base = SPEC_BY_ID["S04"]
    paths = []
    for n in ("SGS/26-27/9001", "SGS/26-27/9002"):
        spec = dataclasses.replace(base, invoice_number=n, lines=[dataclasses.replace(base.lines[0], qty="400")],
                                   prerequisites=[])
        p = Path(tempfile.mkdtemp()) / f"{n.replace('/', '-')}.pdf"
        p.write_bytes(render_spec(spec))
        paths.append(p)
    ids = [upload(client, h, p).json()["invoice_id"] for p in paths]
    drain()
    statuses = sorted(_detail(client, h, i)["status"] for i in ids)
    assert statuses == ["NEEDS_REVIEW", "READY_FOR_APPROVAL"], statuses


def test_dashboard_and_lists_reflect_real_data(client):
    h = login(client)
    for name in ("S01", "S09", "S11"):
        upload(client, h, name)
    drain()
    s = client.get("/api/dashboard/summary?days=0", headers=h).json()
    k = s["kpis"]
    assert k["received"] == 3 and k["ready_for_approval"] == 1 and k["needs_review"] == 1 and k["rejected"] == 1
    assert k["decided_first_pass"] == 3 and abs(k["touchless_rate"] - 1 / 3) < 0.01
    lst = client.get("/api/invoices?status=NEEDS_REVIEW", headers=h).json()
    assert lst["total"] == 1 and lst["items"][0]["vendor"]["vendor_code"] == "V-1001"
    q = client.get("/api/invoices?q=PO-450101", headers=h).json()
    assert q["total"] == 1
    csv_text = client.get("/api/invoices/export.csv", headers=h).text
    assert csv_text.count("\n") == 4
    assert client.get("/api/review-queue", headers=h).json()
    pol = client.get("/api/policies/current", headers=h).json()
    assert pol["version"] == 1 and json.dumps(pol["settings"])
