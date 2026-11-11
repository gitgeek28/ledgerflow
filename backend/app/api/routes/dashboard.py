"""Operational KPIs computed live from persisted data. Definitions are returned with the numbers."""
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import invoice_item, run_out
from app.core.security import current_user
from app.db.models import Invoice, Job, ProcessingRun, User
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEFINITIONS = {
    "received": "Invoices whose PDF was received in the period (exact-file duplicates are not counted).",
    "total_value": "Sum of extracted grand totals of invoices received in the period (unreadable totals excluded).",
    "touchless_rate": "Share of invoices whose first completed automated run ended READY_FOR_APPROVAL with no human "
                      "action. Denominator: invoices with a completed first-pass run in the period.",
    "exception_rate": "1 - touchless rate: share routed to review, hold or rejection on the first automated pass.",
    "processing_time": "Pure stage work time of completed first-pass runs (excludes queue wait and any demo pacing).",
    "end_to_end": "Time from upload to the first decision, including queue wait.",
    "value_at_risk": "Grand total of invoices currently in NEEDS_REVIEW or ON_HOLD (all time).",
    "technical_failures": "Runs that failed for technical reasons (unreadable file, OCR unavailable). Not business "
                          "rejections.",
}


def _pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return s[k]


@router.get("/summary")
def summary(days: int = Query(30, ge=0, le=3650), db: Session = Depends(get_db), _: User = Depends(current_user)):
    now = datetime.now(UTC)
    since = now - timedelta(days=days) if days else datetime(2000, 1, 1, tzinfo=UTC)
    in_period = Invoice.created_at >= since
    received = db.scalar(select(func.count()).select_from(Invoice).where(in_period)) or 0
    total_value = db.scalar(select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
        in_period, Invoice.status.notin_(["FAILED", "CANCELLED"]))) or Decimal(0)
    status_counts = dict(db.execute(select(Invoice.status, func.count()).where(in_period)
                                    .group_by(Invoice.status)).all())
    status_value = {k: str(v) for k, v in db.execute(select(Invoice.status, func.coalesce(func.sum(Invoice.grand_total), 0))
                                                     .where(in_period).group_by(Invoice.status)).all()}

    first_runs = db.execute(
        select(ProcessingRun.invoice_id, ProcessingRun.decision, ProcessingRun.duration_ms, ProcessingRun.created_at,
               ProcessingRun.finished_at)
        .where(ProcessingRun.trigger.in_(["UPLOAD", "RETRY"]), ProcessingRun.status == "COMPLETED",
               ProcessingRun.created_at >= since)
        .order_by(ProcessingRun.invoice_id, ProcessingRun.attempt)).all()
    seen, decisions, durations, e2e = set(), [], [], []
    for inv_id, decision, dur, created, finished in first_runs:
        if inv_id in seen:
            continue
        seen.add(inv_id)
        decisions.append(decision)
        if dur is not None:
            durations.append(dur)
        if finished:
            e2e.append(int((finished - created).total_seconds() * 1000))
    decided = len(decisions)
    touchless = sum(1 for d in decisions if d == "READY_FOR_APPROVAL")
    failures = db.scalar(select(func.count()).select_from(ProcessingRun).where(
        ProcessingRun.status == "FAILED", ProcessingRun.created_at >= since)) or 0

    open_rows = db.execute(select(Invoice.reason_codes).where(
        in_period, Invoice.status.in_(["NEEDS_REVIEW", "ON_HOLD", "REJECTED"]))).scalars().all()
    breakdown = Counter(code for codes in open_rows for code in (codes or [])[:3])
    value_at_risk = db.scalar(select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
        Invoice.status.in_(["NEEDS_REVIEW", "ON_HOLD"]))) or Decimal(0)

    day = func.date_trunc("day", Invoice.created_at)
    series_rows = db.execute(
        select(day, func.count(), func.coalesce(func.sum(Invoice.grand_total), 0),
               func.sum(case((Invoice.status.in_(["READY_FOR_APPROVAL", "APPROVED"]), 1), else_=0)),
               func.sum(case((Invoice.status.in_(["NEEDS_REVIEW", "ON_HOLD", "REJECTED"]), 1), else_=0)))
        .where(in_period).group_by(day).order_by(day)).all()
    series = [{"date": d.date().isoformat(), "received": c, "value": str(v), "ready_or_approved": int(r or 0),
               "exceptions": int(x or 0)} for d, c, v, r, x in series_rows]

    recent = db.scalars(select(ProcessingRun).order_by(desc(ProcessingRun.created_at)).limit(8)).all()
    prio = case((Invoice.priority == "HIGH", 0), else_=1)
    attention = db.scalars(select(Invoice).options(selectinload(Invoice.vendor), selectinload(Invoice.po),
                                                   selectinload(Invoice.assignee))
                           .where(Invoice.status.in_(["NEEDS_REVIEW", "ON_HOLD"]))
                           .order_by(prio, Invoice.created_at).limit(6)).all()
    queued = db.scalar(select(func.count()).select_from(Job).where(Job.status == "QUEUED")) or 0
    running = db.scalar(select(func.count()).select_from(Job).where(Job.status == "RUNNING")) or 0
    return {
        "period_days": days, "generated_at": now.isoformat(),
        "kpis": {
            "received": received, "total_value": str(total_value), "currency": "INR",
            "ready_for_approval": status_counts.get("READY_FOR_APPROVAL", 0),
            "approved": status_counts.get("APPROVED", 0), "needs_review": status_counts.get("NEEDS_REVIEW", 0),
            "on_hold": status_counts.get("ON_HOLD", 0), "rejected": status_counts.get("REJECTED", 0),
            "failed": status_counts.get("FAILED", 0), "processing": status_counts.get("PROCESSING", 0),
            "touchless_rate": round(touchless / decided, 4) if decided else None,
            "exception_rate": round(1 - touchless / decided, 4) if decided else None,
            "decided_first_pass": decided,
            "processing_ms_median": _pct(durations, 50), "processing_ms_p95": _pct(durations, 95),
            "end_to_end_ms_median": _pct(e2e, 50), "technical_failures": failures,
            "value_at_risk": str(value_at_risk),
        },
        "status_counts": status_counts, "status_value": status_value,
        "exception_breakdown": [{"code": c, "count": n} for c, n in breakdown.most_common(10)],
        "series": series,
        "recent_runs": [run_out(db, r).model_dump(mode="json") for r in recent],
        "attention": [invoice_item(i).model_dump(mode="json") for i in attention],
        "queue": {"queued": queued, "running": running},
        "definitions": DEFINITIONS,
    }
