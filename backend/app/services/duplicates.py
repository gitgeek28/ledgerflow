"""Layered duplicate detection. Layer 1 (file hash) runs at intake; layers 2 and 3 run here."""
from datetime import timedelta
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Invoice
from app.services.checks import CheckResult
from app.services.money import fmt
from app.services.policy import PolicySettings

EXCLUDED = ("FAILED", "CANCELLED")


def line_signature(inv: Invoice) -> str:
    return "|".join(sorted(f"{(ln.description or '').lower()[:30]}:{ln.quantity}" for ln in inv.lines))


def check_duplicates(db: Session, inv: Invoice, policy: PolicySettings) -> tuple[list[CheckResult], dict]:
    report = {"business_key": None, "exact": [], "similar": []}
    if inv.vendor_id is None:
        return [CheckResult("INVOICE_DUPLICATE_SUSPECTED", "INDETERMINATE",
                            "Vendor unresolved; business-key duplicate check could not run", outcome="NONE",
                            severity="WARNING")], report
    # Serialise duplicate checks for this vendor so two copies processed concurrently cannot both pass.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"dup:{inv.vendor_id}"})
    others = db.scalars(select(Invoice).where(Invoice.vendor_id == inv.vendor_id, Invoice.id != inv.id,
                                              Invoice.status.notin_(EXCLUDED))).all()
    key = (inv.invoice_number_normalised, inv.currency, inv.grand_total)
    report["business_key"] = {"vendor_id": str(inv.vendor_id), "invoice_number": inv.invoice_number_normalised,
                              "currency": inv.currency, "grand_total": str(inv.grand_total)}
    checks: list[CheckResult] = []
    exact = [o for o in others if inv.invoice_number_normalised and
             (o.invoice_number_normalised, o.currency, o.grand_total) == key]
    if exact:
        orig = sorted(exact, key=lambda o: o.created_at)[0]
        report["exact"] = [{"invoice_id": str(o.id), "reference": o.reference, "status": o.status} for o in exact]
        checks.append(CheckResult(
            "INVOICE_DUPLICATE_SUSPECTED", "FAIL",
            f"Same vendor, invoice number {inv.invoice_number}, currency and total {fmt(inv.grand_total)} as "
            f"{orig.reference} (received {orig.created_at:%d %b %Y}, status {orig.status}). Held to prevent a "
            "second payment.", actual=inv.invoice_number, expected="unique business key",
            evidence={"duplicate_of": str(orig.id), "duplicate_reference": orig.reference}))
        return checks, report

    checks.append(CheckResult("INVOICE_DUPLICATE_SUSPECTED", "PASS",
                              f"No other invoice from this vendor has the same number, currency and total "
                              f"({len(others)} compared)"))
    # Layer 3: near duplicates (transparent rule, warning only)
    window = timedelta(days=policy.near_duplicate_window_days)
    sig = line_signature(inv)
    for o in others:
        reasons = []
        if inv.invoice_number_normalised and o.invoice_number_normalised:
            r = fuzz.ratio(inv.invoice_number_normalised, o.invoice_number_normalised) / 100
            if r >= 0.85:
                reasons.append(f"invoice number {o.invoice_number} similar ({r:.2f})")
        same_amount = (inv.grand_total is not None and o.grand_total is not None and o.grand_total != 0 and
                       abs(inv.grand_total - o.grand_total) / o.grand_total * 100 <= policy.near_duplicate_amount_pct)
        close_date = inv.invoice_date and o.invoice_date and abs(inv.invoice_date - o.invoice_date) <= window
        if same_amount and close_date:
            reasons.append(f"amount within {policy.near_duplicate_amount_pct}% and dated within "
                           f"{policy.near_duplicate_window_days} days")
        if sig and sig == line_signature(o):
            reasons.append("identical line items")
        if len(reasons) >= 2:
            report["similar"].append({"invoice_id": str(o.id), "reference": o.reference, "reasons": reasons})
    if report["similar"]:
        top = report["similar"][0]
        checks.append(CheckResult("INVOICE_NEAR_DUPLICATE", "FAIL",
                                  f"Similar to {top['reference']}: " + "; ".join(top["reasons"]) +
                                  ". Not conclusive; shown for awareness.",
                                  evidence={"candidates": report["similar"]}))
    return checks, report


def similarity_value(a: Decimal | None, b: Decimal | None) -> bool:
    return a is not None and b is not None and a == b
