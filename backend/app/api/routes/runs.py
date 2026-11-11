import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import Paging
from app.api.serializers import run_out
from app.core.errors import Conflict, InvalidTransition, NotFound
from app.core.security import OPERATOR, current_user
from app.db.models import Invoice, ProcessingRun, RunEvent, User
from app.db.session import SessionLocal, get_db
from app.schemas import api
from app.services import audit
from app.services.ingestion import create_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=api.Page[api.RunOut])
def list_runs(status: str | None = None, trigger: str | None = None, invoice_id: uuid.UUID | None = None,
              paging: Paging = Depends(), db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(ProcessingRun)
    if status:
        q = q.where(ProcessingRun.status == status)
    if trigger:
        q = q.where(ProcessingRun.trigger == trigger)
    if invoice_id:
        q = q.where(ProcessingRun.invoice_id == invoice_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(desc(ProcessingRun.created_at)).offset(paging.offset).limit(paging.page_size)).all()
    return api.Page(items=[run_out(db, r) for r in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/{run_id}", response_model=api.RunDetail)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    run = db.get(ProcessingRun, run_id)
    if not run:
        raise NotFound("Run not found.")
    return run_out(db, run, detail=True)


@router.get("/{run_id}/events", response_model=list[api.RunEventOut])
def get_events(run_id: uuid.UUID, after: int = Query(0, ge=0), db: Session = Depends(get_db),
               _: User = Depends(current_user)):
    return db.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > after)
                      .order_by(RunEvent.id)).all()


def _fetch(run_id: uuid.UUID, after: int) -> tuple[list[dict], str | None]:
    with SessionLocal() as db:
        events = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > after)
                            .order_by(RunEvent.id).limit(200)).all()
        status = db.scalar(select(ProcessingRun.status).where(ProcessingRun.id == run_id))
        return [api.RunEventOut.model_validate(e).model_dump(mode="json") for e in events], status


@router.get("/{run_id}/events/stream")
async def stream_events(run_id: uuid.UUID, request: Request, after: int = Query(0, ge=0),
                        last_event_id: str | None = Header(None), _: User = Depends(current_user)):
    """Server-Sent Events tailing the persisted run_events table.

    Resume semantics: the client's Last-Event-ID header (sent automatically by EventSource on reconnect) or the
    `after` query parameter sets the cursor, so a reconnect neither loses nor duplicates events.
    """
    cursor = max(after, int(last_event_id) if last_event_id and last_event_id.isdigit() else 0)

    async def gen():
        nonlocal cursor
        yield "retry: 1500\n\n"
        idle = 0
        while True:
            if await request.is_disconnected():
                return
            events, status = await asyncio.to_thread(_fetch, run_id, cursor)
            if status is None:
                yield "event: error\ndata: {\"message\": \"run not found\"}\n\n"
                return
            for e in events:
                cursor = e["id"]
                yield f"id: {e['id']}\nevent: run_event\ndata: {json.dumps(e)}\n\n"
            if not events and status in ("COMPLETED", "FAILED"):
                yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                return
            idle = 0 if events else idle + 1
            if idle and idle % 40 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/retry", response_model=api.RunOut, status_code=201)
def retry(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(OPERATOR)):
    run = db.get(ProcessingRun, run_id)
    if not run:
        raise NotFound("Run not found.")
    invoice = db.execute(select(Invoice).where(Invoice.id == run.invoice_id).with_for_update()).scalar_one()
    active = db.scalar(select(ProcessingRun).where(ProcessingRun.invoice_id == invoice.id,
                                                   ProcessingRun.status.in_(["QUEUED", "RUNNING"])))
    if active:
        raise Conflict("A run is already in progress for this invoice.", details={"run_id": str(active.id)})
    if invoice.latest_run_id != run.id:
        raise InvalidTransition("Only the latest run of an invoice can be retried.")
    if run.status != "FAILED":
        raise InvalidTransition("Only failed runs can be retried.")
    if not run.retryable:
        raise InvalidTransition("This failure is not retryable: the document itself cannot be read. Ask the vendor "
                                "to re-send it.")
    new = create_run(db, invoice, trigger="RETRY", start_stage="FILE_VALIDATION", user=user, previous=run)
    audit.record(db, action="RETRY_REQUESTED", actor=user, invoice=invoice, run_id=new.id,
                 note=f"Retry of run #{run.attempt} ({run.error_code})")
    db.commit()
    return run_out(db, new, invoice=invoice)
