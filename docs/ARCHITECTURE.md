# Architecture

A modular monolith: one FastAPI service, one worker process, one PostgreSQL database, one Next.js web app.
No queue broker, no microservices; for this scope that is the correct default.

```
 Browser ──HTTP/SSE──▶ Next.js (web :3000) ──/api/* proxy──▶ FastAPI (api :8000) ──▶ PostgreSQL
                                                                   │                      ▲
                                                         jobs table │                      │ events, checks,
                                                                   ▼                      │ audit, decisions
                                                            Worker process(es) ───────────┘
                                                             │  PyMuPDF · Tesseract · rules extractor
                                                             │  (optional) Ollama local LLM
                                                             ▼
                                                     Document storage (local FS behind an interface)
```

## Deployment

Vercel (Next.js) → `/api/*` rewrite → Render (FastAPI + embedded worker, Docker with Tesseract) → Neon Postgres.
PDFs are stored in Postgres (`STORAGE_BACKEND=db`) because the free Render disk is ephemeral. The app uses Neon's
pooled endpoint with server-side prepared statements disabled; Alembic uses the direct endpoint
(`DATABASE_URL_UNPOOLED`).

## Request and processing flow

1. `POST /api/invoices` validates the file, computes SHA-256 and checks the unique hash (an exact duplicate is linked
   and audited; no new invoice is created). Otherwise it stores the bytes under a server key, creates `invoice`,
   `processing_run` (attempt 1) and a `jobs` row, and writes the RECEIVED event, all in one transaction.
2. A worker claims the job: `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED)` with a time-bound lease.
   Multiple workers are safe. A worker that dies leaves a lease that expires; the job is reclaimed and the run resumes
   (`RUN_RESUMED` event). Stages are idempotent: each overwrites its own outputs and checks for that run.
3. The engine executes stages in order. For each stage it writes `STAGE_STARTED`, runs the handler, then persists
   checks, structured outputs and `STAGE_COMPLETED` with the measured duration, and commits. The live view tails
   these rows over **Server-Sent Events**. The stream resumes from `Last-Event-ID`, so reconnects neither lose nor
   duplicate events, and the client falls back to polling.
4. The decision stage applies the decision matrix. If the result is ready for approval, it reserves PO-line quantity
   and value under `SELECT … FOR UPDATE` on the PO row, so two invoices can't consume the same balance (covered by
   an integration test).
5. Human actions call `POST /api/invoices/{id}/review-actions`. Each one locks the invoice row, checks role and
   state transition, persists the change and appends an audit event. When data changed, it enqueues a
   **re-evaluation run** that starts at vendor resolution and appears in the live view like any other run.

## Key design choices

| Choice | Why |
|---|---|
| Deterministic rules decide; the LLM only reads | Money, matching and approval must be reproducible and testable. The LLM is confined to "what is printed where", and its answers must be found in the document |
| Rule-based extractor first, local LLM fallback | Free, fast (~30 ms per text PDF), explainable, and identical in a live demo every time. Llama 3.2 3B via Ollama handles layouts the rules don't know, at about 5 s per call on a laptop |
| Real OCR confidence | Tesseract's per-word confidence drives review routing; amounts that cross-validate arithmetically are raised to 0.95, because independent misreads that still reconcile are very unlikely |
| Decimal everywhere, money as strings over the API | No binary floating-point for currency, end to end. The UI only formats |
| DB-backed job queue | One less moving part than Celery/Redis, transactional with the data, and observable via SQL |
| Persisted events for the live view | The UI shows only what the backend wrote, so the timeline can't be faked and survives restarts |
| Policy versions are immutable rows | Each run records the policy version it used, so past decisions stay explainable after settings change |
| Append-only audit enforced by a DB trigger | Not just a convention: `UPDATE`/`DELETE` on `audit_events` raise an error |
| Next.js proxies `/api/*` | Same-origin cookies, no CORS in the browser, SSE streams through unchanged |

## Code map

```
backend/app/
  api/routes/        invoices, runs (+SSE), reference (vendors/POs), queue, audit, policies, dashboard, samples, auth, health
  core/              config, logging (structlog JSON + request IDs), error envelope, demo auth
  db/models/         SQLAlchemy models; migrations/ holds Alembic revisions
  services/
    extraction/      document.py (PyMuPDF + Tesseract), rules.py (parser), llm.py (Ollama + verification), schema.py
    vendor_resolution.py · po_matching.py · reconciliation.py · po_ledger.py · reservation.py
    duplicates.py · risk.py · decision.py · policy.py (settings + reason-code catalogue) · checks.py
    workflow/        engine.py (stage runner, failure semantics), stages.py (handlers), events.py
    ingestion.py · review.py (human actions) · audit.py · storage.py · reporting.py · money.py · identifiers.py
  workers/runner.py  job claiming, leases, heartbeat
  seed/              reference data, scenario catalogue, PDF generator, demo loader, evaluation harness
frontend/src/
  app/(app)/         overview, invoices (list, new, [id]), runs ([id] live view), review, purchase-orders, vendors, audit, policies
  components/        ui kit, status badges, run timeline, PDF viewer with evidence highlight, investigation panels
  lib/               typed API client + TanStack Query hooks, SSE hook, formatters
```

## Technology

FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL 16 · PyMuPDF · Tesseract 5 (pytesseract) · RapidFuzz ·
structlog · Ollama (optional) · Next.js 15 · React 19 · Tailwind CSS 4 · Radix UI · TanStack Query · react-pdf
(pdf.js 4.8) · Recharts · Playwright · pytest.
