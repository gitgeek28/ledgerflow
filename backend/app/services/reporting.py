"""Printable decision report (HTML) assembled from persisted records only."""
import html

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Invoice, User
from app.services.money import fmt
from app.services.review import latest_checks


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def decision_report_html(db: Session, inv: Invoice, viewer: User) -> str:
    checks = latest_checks(db, inv)
    events = db.scalars(select(AuditEvent).where(AuditEvent.invoice_id == inv.id).order_by(AuditEvent.id)).all()
    rows = "".join(
        f"<tr><td>{_e(c.code)}</td><td>{_e(c.subject)}</td><td class='{c.status.lower()}'>{_e(c.status)}</td>"
        f"<td>{_e(c.severity)}</td><td>{_e(c.message)}</td><td>{_e(c.actual)}</td><td>{_e(c.expected)}</td>"
        f"<td>{_e(c.delta)}</td><td>{_e(c.threshold)}</td></tr>" for c in checks)
    trail = "".join(f"<tr><td>{e.occurred_at:%Y-%m-%d %H:%M:%S} UTC</td><td>{_e(e.actor_type)}</td>"
                    f"<td>{_e(e.actor_name)}</td><td>{_e(e.action)}</td><td>{_e(e.note)}</td></tr>" for e in events)
    lines = "".join(f"<tr><td>{ln.line_number}</td><td>{_e(ln.description)}</td><td>{_e(ln.quantity)}</td>"
                    f"<td>{_e(fmt(ln.unit_price))}</td><td>{_e(ln.tax_rate)}</td><td>{_e(fmt(ln.line_subtotal))}</td>"
                    "</tr>" for ln in inv.lines)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{_e(inv.reference)} decision report</title>
<style>body{{font:13px/1.45 -apple-system,Segoe UI,Inter,sans-serif;color:#1d2433;margin:32px;max-width:1100px}}
h1{{font-size:20px;margin:0}}h2{{font-size:14px;margin:24px 0 8px;text-transform:uppercase;letter-spacing:.04em;
color:#5b6475}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #e3e6ec;padding:6px 8px;
text-align:left;vertical-align:top}}th{{color:#5b6475;font-weight:600}}.pass{{color:#1a7f4b}}.fail{{color:#b42318}}
.indeterminate{{color:#a15c07}}.meta td{{border:0;padding:2px 12px 2px 0}}.badge{{display:inline-block;padding:2px 8px;
border:1px solid #c9ced8;border-radius:4px;font-weight:600}}</style></head><body>
<p style="color:#5b6475">LedgerFlow decision report &middot; generated for {_e(viewer.name)} &middot; synthetic demo data</p>
<h1>{_e(inv.reference)} &mdash; {_e(inv.vendor.legal_name if inv.vendor else inv.vendor_name_raw)}</h1>
<p><span class="badge">{_e(inv.status.replace('_', ' '))}</span> decided by {_e(inv.decided_by.lower())}
{_e(inv.decided_at.strftime('%Y-%m-%d %H:%M UTC') if inv.decided_at else '')}</p>
<p>{_e(inv.decision_summary)}</p>
<table class="meta"><tr><td>Invoice number</td><td>{_e(inv.invoice_number)}</td><td>Invoice date</td>
<td>{_e(inv.invoice_date)}</td></tr><tr><td>PO</td><td>{_e(inv.po.po_number if inv.po else inv.po_reference_raw)}</td>
<td>Match</td><td>{_e(inv.match_mode)}</td></tr><tr><td>Subtotal</td><td>{_e(fmt(inv.subtotal, inv.currency))}</td>
<td>Tax</td><td>{_e(fmt(inv.tax_total, inv.currency))}</td></tr><tr><td>Grand total</td>
<td>{_e(fmt(inv.grand_total, inv.currency))}</td><td>Source file</td><td>{_e(inv.original_filename)}
(SHA-256 {inv.file_sha256[:16]}&hellip;)</td></tr></table>
<h2>Line items</h2><table><tr><th>#</th><th>Description</th><th>Qty</th><th>Rate</th><th>GST %</th><th>Amount</th></tr>
{lines}</table>
<h2>Checks (policy v{checks[0].policy_version if checks else '-'})</h2><table><tr><th>Code</th><th>Subject</th>
<th>Result</th><th>Severity</th><th>Explanation</th><th>Actual</th><th>Expected</th><th>Delta</th><th>Tolerance</th></tr>
{rows}</table><h2>Audit trail</h2><table><tr><th>When</th><th>Type</th><th>Actor</th><th>Action</th><th>Note</th></tr>
{trail}</table></body></html>"""
