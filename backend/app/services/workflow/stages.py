"""Stage handlers. Each one does real work, mutates the invoice, and returns a StageOutcome describing it."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Invoice, InvoiceLine, ProcessingRun, Vendor
from app.services.checks import CheckResult
from app.services.decision import decide
from app.services.duplicates import check_duplicates
from app.services.extraction.document import DocumentText, load_document, validate_pdf
from app.services.extraction.llm import fill_missing_with_llm
from app.services.extraction.rules import RuleBasedExtractor
from app.services.extraction.schema import CRITICAL_FIELDS, ExtractedField, ExtractionIssue, ExtractionResult
from app.services.identifiers import bank_fingerprint, mask_tax_id
from app.services.money import fmt
from app.services.po_ledger import release_reservations
from app.services.po_matching import POMatch, match_po, po_checks
from app.services.policy import PolicySettings
from app.services.reconciliation import Reconciliation, reconcile
from app.services.redaction import mask_digits
from app.services.reservation import reserve
from app.services.risk import risk_checks
from app.services.storage import get_storage
from app.services.text_norm import normalise_invoice_number
from app.services.vendor_resolution import VendorResolution, resolve_vendor, vendor_checks


@dataclass
class StageOutcome:
    message: str
    status: str = "SUCCESS"          # SUCCESS | WARNING
    details: dict = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)


@dataclass
class RunContext:
    db: Session
    run: ProcessingRun
    invoice: Invoice
    policy: PolicySettings
    policy_version: int
    doc: DocumentText | None = None
    extraction: ExtractionResult | None = None        # effective (overrides applied)
    vendor_res: VendorResolution | None = None
    po_match: POMatch | None = None
    recon: Reconciliation | None = None
    checks: list[CheckResult] = field(default_factory=list)
    flags: dict = field(default_factory=dict)


def apply_overrides(raw: ExtractionResult, overrides: dict) -> ExtractionResult:
    eff = raw.model_copy(deep=True)
    for name, ov in (overrides or {}).items():
        if name not in eff.fields:
            continue
        if ov.get("unreadable"):
            eff.fields[name] = ExtractedField(value=None, method="human", confidence=0.0,
                                              notes=[f"Marked unreadable by {ov.get('by')}"])
        else:
            eff.fields[name] = ExtractedField(value=ov.get("value"), raw=ov.get("value"), method="human",
                                              confidence=1.0, notes=[f"Confirmed/corrected by {ov.get('by')}"])
    return eff


def _effective_extraction(ctx: RunContext) -> ExtractionResult:
    if ctx.extraction is None:
        ctx.extraction = apply_overrides(ExtractionResult.model_validate(ctx.invoice.extraction),
                                         ctx.invoice.field_overrides)
    return ctx.extraction


def _sync_header(inv: Invoice, ex: ExtractionResult) -> None:
    def dec(name):
        v = ex.get(name)
        return Decimal(v) if v is not None else None
    inv.invoice_number = ex.get("invoice_number")
    inv.invoice_number_normalised = normalise_invoice_number(inv.invoice_number)
    inv.invoice_date = ex.date("invoice_date")
    inv.due_date = ex.date("due_date")
    inv.po_reference_raw = ex.get("po_number")
    inv.currency = ex.get("currency")
    inv.subtotal, inv.tax_total, inv.grand_total = dec("subtotal"), dec("tax_total"), dec("grand_total")
    inv.vendor_name_raw = ex.get("vendor_name")
    inv.vendor_tax_id_raw = ex.get("vendor_tax_id")


# ------------------------------------------------------------------------------------------------- stages
def file_validation(ctx: RunContext) -> StageOutcome:
    with get_storage().local_path(ctx.invoice.storage_key) as path:
        info = validate_pdf(str(path))
    ctx.invoice.page_count = info["page_count"]
    kb = ctx.invoice.file_size / 1024
    return StageOutcome(
        f"Valid PDF: {info['page_count']} page(s), {kb:.1f} KB, SHA-256 {ctx.invoice.file_sha256[:12]}…"
        + (" (structure repaired on open)" if info["is_repaired"] else ""),
        "WARNING" if info["is_repaired"] else "SUCCESS", details=info)


def text_extraction(ctx: RunContext) -> StageOutcome:
    with get_storage().local_path(ctx.invoice.storage_key) as path:
        doc = load_document(str(path))
    ctx.doc = doc
    stored = doc.to_json()
    for page in stored["pages"]:
        page["lines"] = [mask_digits(line) for line in page["lines"]]
    ctx.invoice.document_text = stored
    parts = []
    text_pages = [p for p in doc.pages if p.method == "text"]
    ocr_pages = [p for p in doc.pages if p.method == "ocr"]
    if text_pages:
        parts.append(f"{len(text_pages)} page(s) from the embedded text layer "
                     f"({sum(len(p.words) for p in text_pages)} words)")
    if ocr_pages:
        confs = [p.mean_conf for p in ocr_pages if p.mean_conf is not None]
        mean = sum(confs) / len(confs) if confs else 0
        parts.append(f"{len(ocr_pages)} image-only page(s) via Tesseract OCR (mean word confidence {mean:.2f})")
    details = {"pages": [{"page": p.number, "method": p.method, "words": len(p.words), "lines": len(p.lines),
                          "mean_confidence": p.mean_conf, "duration_ms": p.duration_ms} for p in doc.pages]}
    return StageOutcome("Read " + " and ".join(parts), "WARNING" if ocr_pages else "SUCCESS", details=details)


def field_extraction(ctx: RunContext) -> StageOutcome:
    threshold = float(ctx.policy.critical_field_confidence)
    result = RuleBasedExtractor(threshold).extract(ctx.doc)
    critical_missing = [f for f in CRITICAL_FIELDS if not result.fields[f].present]
    identity_missing = not result.fields["vendor_name"].present and not result.fields["vendor_tax_id"].present
    llm_report = None
    if critical_missing or identity_missing:
        llm_report = fill_missing_with_llm(ctx.doc, result, threshold)
        if llm_report.get("accepted"):
            result.extractor += f" + {llm_report['model']} (verified fallback)"
        result.issues = [i for i in result.issues if not (i.code == "CRITICAL_FIELD_MISSING"
                                                          and result.fields[i.field].present)]
        for name in llm_report.get("accepted", []):
            f = result.fields[name]
            if name in CRITICAL_FIELDS and f.confidence < threshold:
                result.issues.append(ExtractionIssue(field=name, code="LOW_EXTRACTION_CONFIDENCE",
                                                     message=f"{name} from local model at {f.confidence:.2f}"))
    result.llm = llm_report

    # Remittance details: keep only a keyed fingerprint + last four digits; never persist the full account.
    account = result.get("bank_account")
    inv = ctx.invoice
    inv.bank_account_fingerprint = bank_fingerprint(account) if account else None
    inv.bank_account_last4 = account[-4:] if account else None
    bank = result.fields["bank_account"]
    if bank.present:
        bank.value, bank.raw = "••••" + account[-4:], "••••" + account[-4:]
        if bank.evidence:
            bank.evidence.snippet = mask_digits(bank.evidence.snippet)
    for f in result.fields.values():
        if f.evidence:
            f.evidence.snippet = mask_digits(f.evidence.snippet)
    inv.extraction = result.model_dump(mode="json")
    inv.extraction_method = result.extractor[:80]
    ctx.run.extractor = result.extractor[:120]

    eff = apply_overrides(result, inv.field_overrides)
    ctx.extraction = eff
    _sync_header(inv, eff)
    ctx.db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).delete()
    for ln in result.lines:
        ctx.db.add(InvoiceLine(invoice_id=inv.id, line_number=ln.line_number, description=ln.description,
                               quantity=ln.quantity, unit=ln.unit, unit_price=ln.unit_price, tax_rate=ln.tax_rate,
                               line_subtotal=ln.line_subtotal, line_total=ln.line_total,
                               extraction_confidence=Decimal(str(ln.confidence)),
                               evidence=ln.evidence.model_dump() if ln.evidence else None))
    ctx.db.flush()
    found = sum(1 for k, f in result.fields.items() if f.present)
    issues = [i.model_dump() for i in result.issues]
    llm_note = ""
    if llm_report:
        acc = llm_report.get("accepted") or []
        llm_note = (f"; local model ({llm_report['model']}) {llm_report['status']}"
                    + (f", accepted {', '.join(acc)}" if acc else ", no verified values"))
    msg = (f"Extracted {found} of {len(result.fields)} header fields and {len(result.lines)} line item(s) with "
           f"{result.extractor}{llm_note}; {len(issues)} issue(s)")
    details = {"extractor": result.extractor, "issues": issues, "llm": llm_report,
               "fields": {k: {"value": f.value, "confidence": f.confidence, "method": f.method}
                          for k, f in result.fields.items()},
               "line_count": len(result.lines)}
    return StageOutcome(msg, "WARNING" if issues else "SUCCESS", details=details)


def vendor_resolution(ctx: RunContext) -> StageOutcome:
    ex = _effective_extraction(ctx)
    vendors = ctx.db.scalars(select(Vendor)).all()
    override = (ctx.invoice.field_overrides or {}).get("vendor_id", {}).get("value")
    doc_text = "\n".join("\n".join(p["lines"]) for p in (ctx.invoice.document_text or {}).get("pages", []))
    res = resolve_vendor(vendors, tax_id=ex.get("vendor_tax_id"), name=ex.get("vendor_name"),
                         document_text=doc_text, policy=ctx.policy, override_vendor_id=override)
    ctx.vendor_res = res
    ctx.invoice.vendor_id = res.vendor.id if res.vendor else None
    checks = vendor_checks(res)
    if res.status == "RESOLVED":
        v = res.vendor
        msg = f"Vendor {v.vendor_code} {v.legal_name} resolved by {res.method}"
        if res.supporting:
            msg += f"; {res.supporting[0]}"
        return StageOutcome(msg, "WARNING" if res.conflicting else "SUCCESS", details=res.to_json(),
                            evidence_refs=[f"vendor:{v.vendor_code}"], checks=checks)
    return StageOutcome(f"Vendor {res.status.lower().replace('_', ' ')}: " + "; ".join(res.conflicting or []),
                        "WARNING", details=res.to_json(), checks=checks)


def po_matching(ctx: RunContext) -> StageOutcome:
    ex = _effective_extraction(ctx)
    inv = ctx.invoice
    vendor = ctx.vendor_res.vendor if ctx.vendor_res else (ctx.db.get(Vendor, inv.vendor_id) if inv.vendor_id else None)
    m = match_po(ctx.db, vendor=vendor, po_reference=ex.get("po_number"), inv_lines=ex.lines,
                 invoice_date=ex.date("invoice_date"), currency=ex.get("currency"), subtotal=ex.decimal("subtotal"),
                 policy=ctx.policy, invoice_id=inv.id, human_po_id=inv.po_id if inv.po_selected_by_human else None)
    ctx.po_match = m
    inv.po_id = m.po.id if m.po and m.status in ("MATCHED",) else (inv.po_id if inv.po_selected_by_human else None)
    by_no = {lm.invoice_line: lm for lm in m.line_matches}
    for line in ctx.db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)):
        lm = by_no.get(line.line_number)
        line.matched_po_line_id = lm.po_line_id if lm and lm.po_line_id else None
        line.match_score = Decimal(str(lm.score)) if lm and lm.po_line_id else None
    checks = po_checks(m)
    if m.status == "MATCHED":
        matched = sum(1 for lm in m.line_matches if lm.po_line_id)
        msg = (f"{m.po.po_number} matched by {m.method}; {matched} of {len(m.line_matches)} invoice lines matched "
               "one-to-one to PO lines")
        status = "SUCCESS" if matched == len(m.line_matches) and m.po.status == "OPEN" else "WARNING"
        return StageOutcome(msg, status, details=m.to_json(), evidence_refs=[f"po:{m.po.po_number}"], checks=checks)
    return StageOutcome(f"PO {m.status.lower().replace('_', ' ')}: " + " ".join(m.notes), "WARNING",
                        details=m.to_json(), checks=checks)


def financial_reconciliation(ctx: RunContext) -> StageOutcome:
    ex = _effective_extraction(ctx)
    inv = ctx.invoice
    m = ctx.po_match
    po = m.po if m and m.status == "MATCHED" else None
    rec = reconcile(ctx.db, po=po, line_matches=m.line_matches if po else [], lines=ex.lines,
                    subtotal=ex.decimal("subtotal"), tax_total=ex.decimal("tax_total"),
                    grand_total=ex.decimal("grand_total"), currency=ex.get("currency"),
                    invoice_date=ex.date("invoice_date"), policy=ctx.policy, invoice_id=inv.id)
    ctx.recon = rec
    inv.match_mode = rec.match_mode
    passed = sum(1 for c in rec.checks if c.status == "PASS")
    failed = [c for c in rec.checks if c.failing]
    mode = {"THREE_WAY": "Three-way match", "TWO_WAY": "Two-way match"}.get(rec.match_mode, "Arithmetic only")
    msg = f"{mode}: {passed} check(s) passed, {len(failed)} exception(s)"
    if failed:
        msg += " - " + ", ".join(dict.fromkeys(c.code for c in failed))
    refs = [f"grn:{g}" for g in rec.summary.get("grns", [])]
    return StageOutcome(msg, "WARNING" if failed else "SUCCESS", details=rec.to_json(), evidence_refs=refs,
                        checks=rec.checks)


def duplicate_check(ctx: RunContext) -> StageOutcome:
    checks, report = check_duplicates(ctx.db, ctx.invoice, ctx.policy)
    dup = next((c for c in checks if c.code == "INVOICE_DUPLICATE_SUSPECTED" and c.status == "FAIL"), None)
    ctx.invoice.duplicate_of_id = dup.evidence.get("duplicate_of") if dup else None
    if dup:
        return StageOutcome(f"Duplicate suspected: matches {dup.evidence['duplicate_reference']} on vendor, invoice "
                            "number, currency and amount", "WARNING", details=report, checks=checks,
                            evidence_refs=[f"invoice:{dup.evidence['duplicate_reference']}"])
    near = report.get("similar") or []
    msg = ("No duplicate: business key is unique" + (f"; {len(near)} similar invoice(s) flagged for awareness"
                                                     if near else ""))
    return StageOutcome(msg, "WARNING" if near else "SUCCESS", details=report, checks=checks)


def risk_and_policy(ctx: RunContext) -> StageOutcome:
    ex = _effective_extraction(ctx)
    inv = ctx.invoice
    vendor = ctx.db.get(Vendor, inv.vendor_id) if inv.vendor_id else None
    bank = None
    if inv.bank_account_fingerprint:
        bank = {"fingerprint": inv.bank_account_fingerprint, "last4": inv.bank_account_last4,
                "ifsc": ex.get("bank_ifsc")}
    checks, flags = risk_checks(ex, vendor, ctx.policy, date.today(), bank)
    ctx.flags.update(flags)
    failed = [c for c in checks if c.failing]
    msg = "Vendor status, remittance details, extraction confidence and dates checked"
    if failed:
        msg += ": " + ", ".join(dict.fromkeys(c.code for c in failed))
    if flags.get("security_escalation"):
        msg += " (security escalation)"
    return StageOutcome(msg, "WARNING" if failed else "SUCCESS", checks=checks,
                        details={"flags": flags, "vendor_status": vendor.approved_status if vendor else None,
                                 "vendor_tax_id": mask_tax_id(ex.get("vendor_tax_id"))})


def decision(ctx: RunContext) -> StageOutcome:
    inv = ctx.invoice
    vendor = ctx.db.get(Vendor, inv.vendor_id) if inv.vendor_id else None
    po_number = ctx.po_match.po.po_number if ctx.po_match and ctx.po_match.po else None
    requires_manager = any(c.code == "MANAGER_APPROVAL_REQUIRED" for c in ctx.checks)
    security = ctx.flags.get("security_escalation", False)

    def _decide(checks):
        return decide(checks, match_mode=inv.match_mode, po_number=po_number,
                      vendor_name=vendor.legal_name if vendor else inv.vendor_name_raw, grand_total=inv.grand_total,
                      currency=inv.currency, requires_manager=requires_manager, security=security)
    d = _decide(ctx.checks)
    extra: list[CheckResult] = []
    reservation = {"reserved": False}
    if d.status == "READY_FOR_APPROVAL":
        violations = reserve(ctx.db, inv)
        if violations:
            extra.append(CheckResult("QUANTITY_EXCEEDED", "FAIL", "PO balance changed concurrently: "
                                     + "; ".join(violations), subject="reservation"))
            d = _decide(ctx.checks + extra)
        else:
            reservation = {"reserved": True, "po": po_number}
    else:
        release_reservations(ctx.db, inv.id)
    inv.status = d.status
    inv.reason_codes = d.reason_codes
    inv.priority = d.priority
    inv.decision_summary = d.summary
    inv.next_action = d.next_action
    inv.decided_by = "SYSTEM"
    inv.decided_at = utcnow()
    ctx.run.decision = d.status
    ctx.run.reason_codes = d.reason_codes
    value = fmt(inv.grand_total, inv.currency) if inv.grand_total is not None else "-"
    return StageOutcome(f"{d.status.replace('_', ' ').title()}: {d.summary}",
                        "SUCCESS" if d.status == "READY_FOR_APPROVAL" else "WARNING",
                        details={"status": d.status, "reason_codes": d.reason_codes, "priority": d.priority,
                                 "next_action": d.next_action, "value": value, "reservation": reservation,
                                 "requires_manager_approval": requires_manager}, checks=extra)


HANDLERS = {
    "FILE_VALIDATION": file_validation,
    "TEXT_EXTRACTION": text_extraction,
    "FIELD_EXTRACTION": field_extraction,
    "VENDOR_RESOLUTION": vendor_resolution,
    "PO_MATCHING": po_matching,
    "FINANCIAL_RECONCILIATION": financial_reconciliation,
    "DUPLICATE_CHECK": duplicate_check,
    "RISK_AND_POLICY_CHECKS": risk_and_policy,
    "DECISION": decision,
}
