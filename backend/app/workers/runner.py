"""DB-backed job runner. Claims jobs with FOR UPDATE SKIP LOCKED and a renewable lease, so a crashed worker's
job is picked up again after the lease expires and its run resumes (stages are idempotent).

Usage:  uv run python -m app.workers.runner
"""
import os
import signal
import socket
import threading
import time
import uuid

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.services.workflow.engine import _fail, execute_run

log = get_logger("worker")

CLAIM_SQL = text("""
UPDATE jobs SET status = 'RUNNING', locked_by = :worker, attempts = attempts + 1,
       lease_until = now() + make_interval(secs => :lease), updated_at = now()
WHERE id = (
    SELECT id FROM jobs
    WHERE (status = 'QUEUED' AND available_at <= now()) OR (status = 'RUNNING' AND lease_until < now())
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1)
RETURNING id, run_id, attempts
""")


class Worker:
    def __init__(self, name: str | None = None):
        self.settings = get_settings()
        self.name = name or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.stop = threading.Event()

    def claim(self):
        with SessionLocal() as db:
            row = db.execute(CLAIM_SQL, {"worker": self.name, "lease": self.settings.job_lease_seconds}).first()
            db.commit()
            return row

    def heartbeat(self, job_id) -> None:
        with SessionLocal() as db:
            db.execute(text("UPDATE jobs SET lease_until = now() + make_interval(secs => :lease) WHERE id = :id"),
                       {"lease": self.settings.job_lease_seconds, "id": job_id})
            db.commit()

    def finish(self, job_id, status: str, error: str | None = None) -> None:
        with SessionLocal() as db:
            db.execute(text("UPDATE jobs SET status = :s, last_error = :e, lease_until = NULL, updated_at = now() "
                            "WHERE id = :id"), {"s": status, "e": error, "id": job_id})
            db.commit()

    def run_one(self) -> bool:
        row = self.claim()
        if not row:
            return False
        job_id, run_id, attempts = row
        log.info("job_claimed", job_id=str(job_id), run_id=str(run_id), attempts=attempts, worker=self.name)
        if attempts > self.settings.job_max_attempts:
            with SessionLocal() as db:
                _fail(db, run_id, None, "WORKER_RETRIES_EXHAUSTED",
                      f"The job was interrupted {attempts - 1} times and has been stopped.", True, None)
            self.finish(job_id, "FAILED", "attempts exhausted")
            return True
        try:
            with SessionLocal() as db:
                result = execute_run(db, run_id, heartbeat=lambda: self.heartbeat(job_id))
            self.finish(job_id, "DONE")
            log.info("job_done", job_id=str(job_id), run_id=str(run_id), result=result)
        except Exception as exc:  # noqa: BLE001 - engine already records stage failures; this is a last resort
            log.exception("job_crashed", job_id=str(job_id), run_id=str(run_id))
            with SessionLocal() as db:
                _fail(db, run_id, None, "UNEXPECTED_ERROR", f"{type(exc).__name__} in worker.", True, None)
            self.finish(job_id, "FAILED", type(exc).__name__)
        return True

    def loop(self) -> None:
        log.info("worker_started", worker=self.name)
        while not self.stop.is_set():
            try:
                worked = self.run_one()
            except Exception:  # noqa: BLE001 - e.g. database restarting; back off and retry
                log.exception("worker_loop_error")
                worked = False
                time.sleep(2)
            if not worked:
                self.stop.wait(self.settings.worker_poll_interval_s)
        log.info("worker_stopped", worker=self.name)


def start_background_workers(count: int) -> list[Worker]:
    workers = []
    for _ in range(count):
        w = Worker()
        threading.Thread(target=w.loop, daemon=True, name=f"lf-worker-{w.name}").start()
        workers.append(w)
    return workers


def main() -> None:
    configure_logging()
    settings = get_settings()
    workers = [Worker() for _ in range(settings.worker_concurrency)]
    threads = [threading.Thread(target=w.loop, name=w.name) for w in workers]

    def _stop(*_):
        for w in workers:
            w.stop.set()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
