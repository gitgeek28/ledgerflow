"""Deterministic financial reconciliation: arithmetic, two-/three-way match, cumulative PO consumption.

All values are Decimal. Every check records actual, expected, delta and the tolerance applied, so an AP
analyst can verify the decision with a calculator.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder
from app.services.checks import CheckResult
from app.services.extraction.schema import ExtractedLine
from app.services.money import ZERO, fmt, pct_delta, q2, q3
from app.services.po_ledger import consumed_amount, consumed_by_line, received_by_line
from app.services.po_matching import LineMatch
from app.services.policy import PolicySettings

D0 = Decimal(0)


@dataclass
class Reconciliation:
    match_mode: str | None                     # TWO_WAY | THREE_WAY | None (no PO)
    checks: list[CheckResult] = field(default_factory=list)
    table: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"match_mode": self.match_mode, "table": self.table, "summary": self.summary}


def s(v) -> str | None:
    return None if v is None else str(v)


def arithmetic_checks(lines: list[ExtractedLine], subtotal: Decimal | None, tax_total: Decimal | None,
                      grand_total: Decimal | None, tol: Decimal, currency: str | None) -> list[CheckResult]:
    out: list[CheckResult] = []
    bad_lines = []
    for ln in lines:
        if ln.quantity is not None and ln.unit_price is not None and ln.line_subtotal is not None:
            expected = q2(ln.quantity * ln.unit_price)
            if abs(expected - ln.line_subtotal) > Decimal("0.01"):
                bad_lines.append((ln.line_number, expected, ln.line_subtotal))
    for n, expected, actual in bad_lines:
        out.append(CheckResult("TOTAL_ARITHMETIC_MISMATCH", "FAIL", f"Line {n}: quantity x rate = "
                               f"{fmt(expected)} but the line amount printed is {fmt(actual)}", subject=f"line {n}",
                               actual=fmt(actual), expected=fmt(expected), delta=fmt(actual - expected)))
    if subtotal is not None and lines and all(ln.line_subtotal is not None for ln in lines):
        lines_sum = sum((ln.line_subtotal for ln in lines), D0)
        delta = subtotal - lines_sum
        ok = abs(delta) <= tol
        out.append(CheckResult("TOTAL_ARITHMETIC_MISMATCH", "PASS" if ok else "FAIL",
                               f"Sum of {len(lines)} line amounts {fmt(lines_sum)} vs printed subtotal {fmt(subtotal)}",
                               subject="subtotal", actual=fmt(subtotal), expected=fmt(lines_sum), delta=fmt(delta),
                               threshold=f"± {fmt(tol)}"))
    if subtotal is not None and tax_total is not None and grand_total is not None:
        expected = subtotal + tax_total
        delta = grand_total - expected
        ok = abs(delta) <= tol
        out.append(CheckResult("TOTAL_ARITHMETIC_MISMATCH", "PASS" if ok else "FAIL",
                               f"Subtotal {fmt(subtotal)} + tax {fmt(tax_total)} = {fmt(expected)}; printed grand "
                               f"total {fmt(grand_total)}", subject="grand total", actual=fmt(grand_total),
                               expected=fmt(expected), delta=fmt(delta), threshold=f"± {fmt(tol)}"))
    elif grand_total is not None:
        out.append(CheckResult("TOTAL_ARITHMETIC_MISMATCH", "INDETERMINATE",
                               "Subtotal or tax not readable; grand total cannot be verified arithmetically",
                               subject="grand total", outcome="REVIEW"))
    return out


def reconcile(db: Session, *, po: PurchaseOrder | None, line_matches: list[LineMatch], lines: list[ExtractedLine],
              subtotal: Decimal | None, tax_total: Decimal | None, grand_total: Decimal | None,
              currency: str | None, invoice_date: date | None, policy: PolicySettings, invoice_id) -> Reconciliation:
    tol = policy.rounding_tolerance_abs
    rec = Reconciliation(match_mode=None)
    rec.checks.extend(arithmetic_checks(lines, subtotal, tax_total, grand_total, tol, currency))
    if po is None:
        rec.checks.append(CheckResult("PO_NOT_FOUND", "INDETERMINATE",
                                      "PO-dependent checks (price, quantity, receipt, balance) skipped: no PO matched",
                                      outcome="NONE", severity="INFO"))
        rec.summary = {"lines": len(lines)}
        return rec

    # Currency, validity
    if currency is None:
        rec.checks.append(CheckResult("CURRENCY_MISMATCH", "INDETERMINATE", "Invoice currency not printed",
                                      expected=po.currency, outcome="REVIEW", severity="REVIEW"))
    else:
        rec.checks.append(CheckResult("CURRENCY_MISMATCH", "PASS" if currency == po.currency else "FAIL",
                                      f"Invoice currency {currency}, PO currency {po.currency}", actual=currency,
                                      expected=po.currency))
    if invoice_date and invoice_date > po.valid_until:
        rec.checks.append(CheckResult("PO_EXPIRED", "FAIL", f"Invoice dated {invoice_date} after PO validity "
                                      f"{po.valid_until}", actual=str(invoice_date), expected=f"<= {po.valid_until}"))

    consumed = consumed_by_line(db, po.id, invoice_id)
    received, grns = received_by_line(db, po.id)
    three_way = po.po_type == "GOODS" and bool(grns)
    rec.match_mode = "THREE_WAY" if three_way else "TWO_WAY"
    if po.po_type == "GOODS" and not grns:
        rec.match_mode = "TWO_WAY"
        if policy.require_grn_for_goods:
            rec.checks.append(CheckResult("GRN_PENDING", "FAIL",
                                          f"{po.po_number} is a goods PO with no goods receipt posted yet; "
                                          "invoice held until goods are received", actual="no GRN",
                                          expected="posted GRN"))

    by_id = {str(pl.id): pl for pl in po.lines}
    by_inv = {ln.line_number: ln for ln in lines}
    expected_value = D0
    expected_tax = D0
    all_matched = True
    tax_known = True
    for lm in line_matches:
        il = by_inv[lm.invoice_line]
        subject = f"line {il.line_number}"
        if not lm.po_line_id:
            all_matched = False
            rec.checks.append(CheckResult("LINE_ITEM_UNMATCHED", "FAIL",
                                          f"Invoice line {il.line_number} '{il.description}' has no matching PO line "
                                          f"({lm.reason})", subject=subject, actual=il.description))
            rec.table.append({"invoice_line": il.line_number, "description": il.description, "matched": False,
                              "quantity": s(il.quantity), "unit_price": s(il.unit_price),
                              "line_subtotal": s(il.line_subtotal)})
            continue
        pl = by_id[lm.po_line_id]
        prev_qty, prev_amt = consumed[pl.id]
        qty = il.quantity
        row = {"invoice_line": il.line_number, "description": il.description, "matched": True,
               "po_line": pl.line_number, "po_description": pl.description, "match_score": lm.score,
               "unit": il.unit, "po_unit": pl.unit, "quantity": s(qty), "ordered": s(q3(pl.quantity_ordered)),
               "previously_invoiced": s(q3(prev_qty)), "unit_price": s(il.unit_price), "po_unit_price": s(pl.unit_price),
               "tax_rate": s(il.tax_rate), "po_tax_rate": s(pl.tax_rate), "line_subtotal": s(il.line_subtotal)}
        # Unit price
        if il.unit_price is not None:
            var = pct_delta(Decimal(il.unit_price), pl.unit_price)
            row["price_variance_pct"] = s(var)
            over = var is not None and var > policy.unit_price_variance_pct
            msg = (f"Unit price {fmt(il.unit_price)} vs PO {fmt(pl.unit_price)} ({var:+}%)" if var is not None
                   else "PO unit price is zero")
            if var is not None and var < 0:
                msg += "; billed below PO price"
            rec.checks.append(CheckResult("PRICE_VARIANCE_EXCEEDED", "FAIL" if over else "PASS", msg, subject=subject,
                                          actual=fmt(il.unit_price), expected=fmt(pl.unit_price),
                                          delta=f"{fmt(Decimal(il.unit_price) - pl.unit_price)} ({var:+}%)",
                                          threshold=f"+{policy.unit_price_variance_pct}%"))
        else:
            rec.checks.append(CheckResult("PRICE_VARIANCE_EXCEEDED", "INDETERMINATE",
                                          f"Line {il.line_number} unit price not readable", subject=subject))
        # Tax rate
        if il.tax_rate is not None:
            ok = Decimal(il.tax_rate) == pl.tax_rate
            rec.checks.append(CheckResult("TAX_MISMATCH", "PASS" if ok else "FAIL",
                                          f"GST rate {il.tax_rate}% vs PO {pl.tax_rate}%"
                                          + (" (rate taken from tax summary)" if il.tax_rate_source == "summary" else ""),
                                          subject=subject, actual=f"{il.tax_rate}%", expected=f"{pl.tax_rate}%"))
        else:
            tax_known = False
        # Quantity vs ordered (cumulative)
        if qty is not None:
            remaining = pl.quantity_ordered - prev_qty
            allowed = remaining * (1 + policy.quantity_variance_pct / 100)
            row["remaining_before"] = s(q3(remaining))
            exceeded = qty > allowed
            rec.checks.append(CheckResult(
                "QUANTITY_EXCEEDED", "FAIL" if exceeded else "PASS",
                f"Ordered {q3(pl.quantity_ordered).normalize():f}, previously invoiced {q3(prev_qty).normalize():f}, "
                f"remaining {q3(remaining).normalize():f}; this invoice {q3(qty).normalize():f}",
                subject=subject, actual=f"{q3(qty).normalize():f}", expected=f"<= {q3(remaining).normalize():f}",
                delta=f"{q3(qty - remaining).normalize():+f}" if exceeded else None,
                threshold=f"{policy.quantity_variance_pct}% over remaining",
                evidence={"po_line": pl.line_number, "ordered": str(pl.quantity_ordered),
                          "previously_invoiced": str(prev_qty)}))
            if three_way:
                rec_qty = received.get(pl.id, ZERO)
                eligible = rec_qty - prev_qty
                row["received"] = s(q3(rec_qty))
                row["received_not_invoiced"] = s(q3(eligible))
                over = qty > eligible * (1 + policy.quantity_variance_pct / 100)
                rec.checks.append(CheckResult(
                    "GRN_QUANTITY_MISMATCH", "FAIL" if over else "PASS",
                    f"Received {q3(rec_qty).normalize():f} on {', '.join(grns)}; previously invoiced "
                    f"{q3(prev_qty).normalize():f}; received-not-invoiced {q3(eligible).normalize():f}; this invoice "
                    f"{q3(qty).normalize():f}", subject=subject, actual=f"{q3(qty).normalize():f}",
                    expected=f"<= {q3(eligible).normalize():f}",
                    delta=f"{q3(qty - eligible).normalize():+f}" if over else None,
                    evidence={"grns": grns}))
            expected_value += q2(qty * pl.unit_price)
            line_base = il.line_subtotal if il.line_subtotal is not None else q2(qty * pl.unit_price)
            expected_tax += q2(line_base * pl.tax_rate / 100)
        rec.table.append(row)

    # Header-level comparisons against PO-priced values
    if subtotal is not None and all_matched and expected_value:
        delta = subtotal - expected_value
        over = delta > policy.invoice_total_variance_abs
        rec.checks.append(CheckResult("AMOUNT_VARIANCE_EXCEEDED", "FAIL" if over else "PASS",
                                      f"Invoice subtotal {fmt(subtotal)} vs PO-priced value of invoiced quantities "
                                      f"{fmt(expected_value)}", subject="subtotal", actual=fmt(subtotal),
                                      expected=fmt(expected_value), delta=fmt(delta),
                                      threshold=f"+{fmt(policy.invoice_total_variance_abs, currency)}"))
    if tax_total is not None and all_matched and expected_tax:
        delta = tax_total - expected_tax
        ok = abs(delta) <= tol
        rec.checks.append(CheckResult("TAX_MISMATCH", "PASS" if ok else "FAIL",
                                      f"Invoice tax {fmt(tax_total)} vs tax at PO rates on invoiced amounts "
                                      f"{fmt(expected_tax)}" + ("" if tax_known else " (per-line rates not printed)"),
                                      subject="tax total", actual=fmt(tax_total), expected=fmt(expected_tax),
                                      delta=fmt(delta), threshold=f"± {fmt(tol)}"))
    if subtotal is not None:
        prev_amount = consumed_amount(db, po.id, invoice_id)
        cumulative = prev_amount + subtotal
        limit = po.subtotal + policy.invoice_total_variance_abs
        over = cumulative > limit
        rec.checks.append(CheckResult("PO_BALANCE_EXCEEDED", "FAIL" if over else "PASS",
                                      f"PO value {fmt(po.subtotal)} (pre-tax); previously invoiced {fmt(prev_amount)}; "
                                      f"this invoice {fmt(subtotal)}; cumulative {fmt(cumulative)}",
                                      subject=po.po_number, actual=fmt(cumulative), expected=f"<= {fmt(po.subtotal)}",
                                      delta=fmt(cumulative - po.subtotal) if over else None,
                                      threshold=f"+{fmt(policy.invoice_total_variance_abs)}"))
        rec.summary["po_value"] = s(po.subtotal)
        rec.summary["previously_invoiced_value"] = s(prev_amount)
        rec.summary["remaining_value_after"] = s(po.subtotal - cumulative)
    rec.summary.update({"po_number": po.po_number, "po_type": po.po_type, "grns": grns,
                        "lines": len(lines), "lines_matched": sum(1 for lm in line_matches if lm.po_line_id),
                        "expected_value": s(expected_value)})
    return rec
