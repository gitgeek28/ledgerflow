"""Reset the demo and build realistic history by running the 'history' invoices through the REAL pipeline,
then have the AP manager approve a few of the ready ones (real review actions, fully audited).

Usage:  uv run python -m app.seed.demo_load [--keep]      (--keep: do not reset first)
"""
import argparse
import time

import yaml
from sqlalchemy import select

from app.core.config import REPO_DIR
from app.db.models import Invoice, ProcessingRun, User
from app.db.session import SessionLocal
from app.seed.seed import reset, seed
from app.services.ingestion import ingest
from app.services.review import perform
from app.workers.runner import Worker

APPROVE = ["H01", "H02", "H04", "H05"]


def wait_for_runs(timeout: float = 120) -> None:
    worker, deadline = Worker("demo-load"), time.time() + timeout
    while time.time() < deadline:
        worker.run_one()
        with SessionLocal() as db:
            pending = db.scalar(select(ProcessingRun).where(ProcessingRun.status.in_(["QUEUED", "RUNNING"])).limit(1))
        if not pending:
            return
        time.sleep(0.2)
    raise SystemExit("Timed out waiting for runs to finish")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    catalogue = yaml.safe_load((REPO_DIR / "data/fixtures/scenarios.yaml").read_text())
    with SessionLocal() as db:
        if not args.keep:
            reset(db)
        seed(db)
        db.commit()
    ids = {}
    for c in [c for c in catalogue if c["group"] == "history"]:
        with SessionLocal() as db:
            analyst = db.scalar(select(User).where(User.email == "rohan.desai@kestrel.example"))
            data = (REPO_DIR / "data/fixtures" / c["file"]).read_bytes()
            r = ingest(db, filename=c["file"].split("/")[-1], content_type="application/pdf", data=data, user=analyst)
            ids[c["id"]] = r.invoice.id
        wait_for_runs()
    with SessionLocal() as db:
        manager = db.scalar(select(User).where(User.role == "AP_MANAGER"))
        for sid in APPROVE:
            if db.get(Invoice, ids[sid]).status == "READY_FOR_APPROVAL":
                perform(db, ids[sid], manager, "APPROVE", note="Approved in weekly AP run")
        summary = {s: db.get(Invoice, i).status for s, i in ids.items()}
    print("history loaded:", summary)


if __name__ == "__main__":
    main()
