"""Evaluation harness: runs every catalogued fixture through the REAL pipeline on an isolated database and
compares outputs with the labelled ground truth. Writes docs/EVALUATION.md and data/eval/latest.json.

Usage:  uv run python -m app.seed.evaluate [--llm]
(Uses TEST_DATABASE_URL / ledgerflow_test so demo data is untouched. --llm enables the Ollama fallback.)
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from decimal import Decimal

if "--keep-env" not in sys.argv:
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://ledgerflow:ledgerflow@localhost:5432/ledgerflow_test")
    os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="ledgerflow-eval-")
    os.environ["LLM_PROVIDER"] = "ollama" if "--llm" in sys.argv else "none"
    os.environ["DEMO_STAGE_PACING_MS"] = "0"

import yaml  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import BACKEND_DIR, REPO_DIR  # noqa: E402
from app.db.models import Invoice, ProcessingRun, User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.seed.seed import reset, seed  # noqa: E402
from app.services.ingestion import ingest  # noqa: E402
from app.workers.runner import Worker  # noqa: E402

HEADER = ["invoice_number", "invoice_date", "due_date", "po_number", "currency", "subtotal", "tax_total",
          "grand_total", "vendor_tax_id"]


def pct(n, d):
    return f"{(100 * n / d):.1f}% ({n}/{d})" if d else "n/a (0)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--keep-env", action="store_true")
    parser.parse_args()  # flags are read from sys.argv before imports (see top of module)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    with SessionLocal() as db:
        reset(db)
        seed(db)
        db.commit()
    cat = yaml.safe_load((REPO_DIR / "data/fixtures/scenarios.yaml").read_text())
    order = [c for c in cat if c["group"] == "history"] + [c for c in cat if c["group"] == "demo"]
    worker = Worker("evaluate")
    rows = []
    started = time.time()
    for c in order:
        data = (REPO_DIR / "data/fixtures" / c["file"]).read_bytes()
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.role == "AP_ANALYST"))
            r = ingest(db, filename=c["file"].split("/")[-1], content_type="application/pdf", data=data, user=user)
            inv_id, dup = r.invoice.id, r.duplicate
        while worker.run_one():
            pass
        with SessionLocal() as db:
            inv = db.get(Invoice, inv_id)
            run = db.get(ProcessingRun, inv.latest_run_id)
            rows.append({"id": c["id"], "group": c["group"], "expect": c["expect"], "labelled": c.get("labelled"),
                         "vendor_code": c.get("vendor_code"), "duplicate_file": dup,
                         "status": inv.status, "codes": inv.reason_codes, "match_mode": inv.match_mode,
                         "vendor": inv.vendor.vendor_code if inv.vendor else None,
                         "po": inv.po.po_number if inv.po else None,
                         "fields": {k: (inv.extraction or {}).get("fields", {}).get(k, {}).get("value") for k in HEADER},
                         "lines": [{"quantity": str(ln.quantity) if ln.quantity is not None else None,
                                    "unit_price": str(ln.unit_price) if ln.unit_price is not None else None,
                                    "line_subtotal": str(ln.line_subtotal) if ln.line_subtotal is not None else None}
                                   for ln in inv.lines],
                         "duration_ms": run.duration_ms if (run and not dup) else None,
                         "run_status": run.status if run else None,
                         "ocr": any(p.get("method") == "ocr" for p in (inv.document_text or {}).get("pages", [])),
                         "extractor": run.extractor if run else None})
    wall = time.time() - started

    # ---------------------------------------------------------------- metrics
    m = {}
    labelled = [r for r in rows if r["labelled"] and not r["duplicate_file"]]
    parseable = [r for r in labelled if r["labelled"].get("rules_parseable", True)]
    fh = ft = 0
    per_field = {}
    for r in parseable:
        for k in HEADER:
            exp = r["labelled"]["vendor_gstin"] if k == "vendor_tax_id" else r["labelled"].get(k)
            got = r["fields"].get(k)
            if k in ("subtotal", "tax_total", "grand_total") and exp is not None and got is not None:
                ok = Decimal(got) == Decimal(exp)
            elif k == "invoice_number" and exp:
                ok = (got or "").upper() == exp.upper()
            else:
                ok = got == exp
            per_field.setdefault(k, [0, 0])
            per_field[k][0] += ok
            per_field[k][1] += 1
            fh += ok
            ft += 1
    m["header_field_accuracy"] = pct(fh, ft)
    lh = lt = 0
    for r in parseable:
        for exp, got in zip(r["labelled"]["lines"], r["lines"] + [None] * 100, strict=False):
            lt += 1
            if got and got["quantity"] is not None and Decimal(got["quantity"]) == Decimal(exp["quantity"]) and \
                    got["unit_price"] and Decimal(got["unit_price"]) == Decimal(exp["unit_price"]) and \
                    got["line_subtotal"] and Decimal(got["line_subtotal"]) == Decimal(exp["line_subtotal"]):
                lh += 1
    m["line_item_accuracy"] = pct(lh, lt)
    vend = [r for r in rows if r["labelled"] and not r["duplicate_file"]]
    m["vendor_resolution_accuracy"] = pct(sum(r["vendor"] == r["vendor_code"] for r in vend), len(vend))
    po_rows = [r for r in vend if r["labelled"].get("po_number") is not None or r["id"] == "S06"]
    m["po_matching_accuracy"] = pct(sum(r["po"] == r["labelled"].get("po_number") for r in po_rows), len(po_rows))
    positives = {"S02", "S03"}
    detected = {r["id"] for r in rows if r["duplicate_file"] or "INVOICE_DUPLICATE_SUSPECTED" in r["codes"]}
    tp = len(positives & detected)
    m["duplicate_precision"] = pct(tp, len(detected))
    m["duplicate_recall"] = pct(tp, len(positives))
    decided = [r for r in rows if not r["duplicate_file"]]
    m["final_decision_accuracy"] = pct(sum(r["status"] == r["expect"].get("status") for r in decided), len(decided))

    def codes_ok(r):
        e = r["expect"]
        return all(c in r["codes"] for c in e.get("codes", [])) and \
            (not e.get("codes_any") or bool(set(e["codes_any"]) & set(r["codes"])))
    m["reason_code_accuracy"] = pct(sum(codes_ok(r) for r in decided), len(decided))
    routed = [r for r in decided if r["expect"].get("status") != "FAILED"]
    m["human_review_routing_accuracy"] = pct(
        sum((r["status"] == "READY_FOR_APPROVAL") == (r["expect"]["status"] == "READY_FOR_APPROVAL") for r in routed),
        len(routed))
    completed = [r for r in decided if r["run_status"] == "COMPLETED"]
    m["end_to_end_completion"] = pct(len(completed), len(decided)) + " (S12 is a deliberate corrupt file)"
    durs = [r["duration_ms"] for r in decided if r["duration_ms"] is not None]
    text_d = [r["duration_ms"] for r in decided if r["duration_ms"] is not None and not r["ocr"]]
    ocr_d = [r["duration_ms"] for r in decided if r["duration_ms"] is not None and r["ocr"]]

    def p95(v):
        return sorted(v)[max(0, round(0.95 * (len(v) - 1)))] if v else None
    m["processing_ms_median_all"] = f"{statistics.median(durs):.0f} ms (n={len(durs)})" if durs else "n/a"
    m["processing_ms_p95_all"] = f"{p95(durs)} ms (n={len(durs)})" if durs else "n/a"
    m["processing_ms_median_text_pdfs"] = f"{statistics.median(text_d):.0f} ms (n={len(text_d)})" if text_d else "n/a"
    m["processing_ms_median_scanned_pdfs"] = f"{statistics.median(ocr_d):.0f} ms (n={len(ocr_d)})" if ocr_d else "n/a"

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    out_dir = REPO_DIR / "data/eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps({"generated_at": stamp, "llm": os.environ["LLM_PROVIDER"],
                                                     "metrics": m, "per_field": per_field, "rows": rows},
                                                    indent=2, default=str))
    table = "\n".join(f"| {k.replace('_', ' ').capitalize()} | {v} |" for k, v in m.items())
    fields = "\n".join(f"| `{k}` | {pct(v[0], v[1])} |" for k, v in per_field.items())
    scen = "\n".join(
        f"| {r['id']} | {r['expect'].get('status', 'duplicate file' if r['id'] == 'S02' else '-')} | "
        f"{'DUPLICATE_FILE (linked to original)' if r['duplicate_file'] else r['status']} | "
        f"{', '.join(r['codes'][:4]) or '-'} | {r['duration_ms'] if r['duration_ms'] is not None else '-'} | "
        f"{'✅' if (r['duplicate_file'] if r['id'] == 'S02' else (r['status'] == r['expect'].get('status') and codes_ok(r))) else '❌'} |"
        for r in rows)
    md = f"""# Evaluation

> Generated by `make evaluate` (`python -m app.seed.evaluate`) on {stamp}. Local LLM fallback:
> **{os.environ['LLM_PROVIDER']}**. Wall time {wall:.1f}s. Numbers below are measured, not estimated.

## Method

Every document in `data/fixtures/scenarios.yaml` ({len(rows)} submissions: {len([r for r in rows if r['group'] == 'history'])}
history invoices, then the demo scenarios) is uploaded through the real intake service into an isolated database
(`ledgerflow_test`), processed by the real worker, and compared with labelled ground truth produced by the same
generator that rendered the PDFs. Prerequisites (an original before its duplicate, a first split invoice before the
second) are satisfied by the processing order.

## Important limitation

This is a **synthetic** set of {len(rows)} documents in 4 layouts that the rule-based extractor was developed
against. A 100% figure here demonstrates that the pipeline, matching and decision logic behave as specified on the
designed scenarios; it is **not** evidence of production extraction accuracy on unseen vendor layouts. A production
evaluation would need a few hundred real, labelled invoices across vendors, measured per field, with the LLM
fallback enabled and disabled.

## Results

| Metric | Result (denominator) |
|---|---|
{table}

### Header field accuracy by field (rules-parseable documents only, n={len(parseable)})

| Field | Exact match |
|---|---|
{fields}

`S15` (free-form letter) is excluded from field accuracy by design: it has no labels or table and exists to show the
fail-closed path and the verified LLM fallback.

## Per scenario

| Scenario | Expected | Actual | Reason codes (first 4) | Processing ms | Pass |
|---|---|---|---|---|---|
{scen}

Definitions: *processing ms* is the sum of stage execution time recorded by the engine (queue wait excluded).
*Human-review routing* treats READY_FOR_APPROVAL as "no human needed" and every other status as "human needed".
*Duplicate precision/recall* are over {len(rows)} submissions with 2 true duplicates (S02 exact file, S03 business key).
"""
    (REPO_DIR / "docs/EVALUATION.md").write_text(md)
    print(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
