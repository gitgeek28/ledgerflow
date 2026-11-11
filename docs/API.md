# API

Interactive OpenAPI docs: **http://localhost:3000/api/docs** (proxied) or http://localhost:8000/api/docs.

Authentication: `POST /api/auth/login` sets an HttpOnly session cookie and also returns a bearer token for scripts.
Errors use one envelope: `{"error": {"code", "message", "details", "request_id"}}`. Every response carries an
`X-Request-ID` header. Lists return `{items, total, page, page_size}`. Money is serialised as decimal strings.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/health/ready` | Liveness; readiness (DB, storage, OCR engine, LLM, queue, policy version) |
| POST | `/api/auth/login` · `/logout` · GET `/me` · `/demo-users` | Demo auth |
| POST | `/api/invoices` | Upload one PDF (multipart `file`) → `CREATED` with run id, or `DUPLICATE_FILE` linked to the original |
| POST | `/api/invoices/batch` | Up to 25 files (`files`); per-file outcome |
| GET | `/api/invoices` | Search/filter (`q`, `status`, `vendor_id`, `priority`, `date_from/to`, `min/max_amount`), sort, paginate |
| GET | `/api/invoices/export.csv` | Decisions export |
| GET | `/api/invoices/{id}` | Full investigation payload (fields, evidence, lines, checks, runs, notes, permissions) |
| GET | `/api/invoices/{id}/document` · `/checks` · `/audit` · `/events` · `/report` | Original PDF, checks, audit trail, all events, printable decision report |
| POST | `/api/invoices/{id}/review-actions` | `CORRECT_FIELD`, `CONFIRM_FIELD`, `MARK_UNREADABLE`, `SELECT_PO`, `SELECT_VENDOR`, `RE_EVALUATE`, `REQUEST_INFO`, `HOLD`, `REJECT`, `MARK_READY`, `APPROVE`, `CANCEL` |
| POST | `/api/invoices/{id}/notes` · `/assign` | Internal notes; assignment |
| GET | `/api/runs` · `/api/runs/{id}` · `/api/runs/{id}/events?after=` | Runs and persisted events |
| GET | `/api/runs/{id}/events/stream` | **SSE**; honours `Last-Event-ID` / `after`; ends with `event: end` |
| POST | `/api/runs/{id}/retry` | Safe retry (latest failed, retryable, none in progress) |
| GET | `/api/review-queue?view=open|mine|approval|hold` | Prioritised queue |
| GET | `/api/vendors` · `/{id}` · `/api/purchase-orders` · `/{id}` | Reference data with consumption and receipts |
| GET | `/api/audit` · `/api/audit/actions` · `/api/audit/export.csv` | Audit log |
| GET/POST | `/api/policies` · GET `/current` · `/reason-codes` | Versioned policy (POST: manager only) |
| GET | `/api/dashboard/summary?days=` | KPIs with definitions, series, breakdown, attention queue |
| GET | `/api/samples` · `/api/samples/{id}/file` | Synthetic sample PDFs for demos |

## Example

```bash
B=http://localhost:3000/api
curl -s -c jar -X POST $B/auth/login -H 'content-type: application/json' \
  -d '{"email":"aisha.rao@kestrel.example","password":"ledgerflow-demo"}' >/dev/null
RUN=$(curl -s -b jar -F "file=@data/fixtures/pdfs/S09_VSS-26-27-0412.pdf;type=application/pdf" $B/invoices | jq -r .run_id)
curl -N -b jar $B/runs/$RUN/events/stream          # watch stages arrive
curl -s -b jar $B/runs/$RUN | jq '.decision, .reason_codes'
# → "NEEDS_REVIEW"  ["PRICE_VARIANCE_EXCEEDED", "AMOUNT_VARIANCE_EXCEEDED", "PO_BALANCE_EXCEEDED"]
```
