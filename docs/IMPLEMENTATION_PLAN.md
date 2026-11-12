# LedgerFlow — PS-1 Invoice Processing: Build Plan

## Implementation status

| Milestone | Status | Verified by |
|---|---|---|
| M0 Setup (repo, uv, Next.js, Postgres, Alembic, health) | Done | `make dev`, `/api/health/ready` |
| M1 Data model + seed | Done | migrations 0001–0004, `make demo-load` |
| M2 Synthetic fixtures + scenario catalogue | Done | 26 PDFs, `data/fixtures/scenarios.yaml` |
| M3 Intake, storage, job queue, worker, events, SSE, OCR | Done | integration tests (SSE resume, lease recovery) |
| M4 Field extraction (rules + verified local LLM) | Done | unit tests, mocked-LLM tests, manual Ollama run |
| M5 Vendor, PO, line matching | Done | unit + scenario tests |
| M6 Reconciliation, duplicates, policy, decision, reservation | Done | unit + concurrency test |
| M7 Review actions, audit, retry, info-request draft, report | Done | API integration tests, Playwright |
| M8 Read APIs, dashboard, CSV export, policy versions | Done | integration tests |
| M9 Frontend (all screens, light default + dark mode) | Done | typecheck, lint, production build, Playwright |
| M10 Evaluation + E2E | Done | `make evaluate`, `make test-e2e` |
| M11 Docs + packaging | Done (container images not built locally) | `docker compose config` |


## Context
Zamp ASA case study, PS-1 (invoice → reasoned decision, everything in between visible). The guide (source of truth) requires: a process that **actually runs on real PDF inputs**, a **live run view** (each stage as it executes), a **dashboard** (history/status/outputs across runs), 2–4 non-trivial edge cases, and a live-runnable link + 5-min demo. `ledgerflow_claude_code_build_spec.md` is the detailed product/engineering spec (P0 + as much P1 as possible, scenarios S01–S12).

User decisions (confirmed):
- **Extraction (all free, no paid APIs):** hybrid — PyMuPDF text layer + Tesseract OCR + deterministic layout-aware parser (primary); **local Llama 3.2 3B via Ollama** (already downloaded) as an optional, schema-validated, evidence-verified fallback for missing critical fields + plain-English decision summary. App fully works with Ollama off; every run records which extractor was used.
- **Deployment:** finish + verify locally today; ship Dockerfiles, docker-compose and a Render blueprint (deploy-ready).
- **GitHub:** private repo `gitgeek28/ledgerflow`. Repo-local git config: `user.name=Devanshi`, `user.email=155298674+gitgeek28@users.noreply.github.com`; repo-local credential helper using `gh auth token -u gitgeek28` (does not change the active gh account). Built-for name in docs: Devanshi. No other personal identity anywhere (no absolute home paths in committed files; dedicated `ledgerflow` Postgres role).
- **UI:** light theme default (per spec §10) + dark-mode toggle.

## Environment (inspected)
macOS arm64, 8 GB RAM, ~7.7 GB free disk. Postgres 16 + Redis running via Homebrew; Python 3.12 + uv; Node 20.19; Ollama 0.24 with llama3.2 + llama3.1 pulled; poppler present; **Tesseract missing → `brew install tesseract`**; Docker/colima stopped (not needed locally). No paid LLM keys (not wanted).

## Architecture (modular monolith)
```
ledgerflow/                      (new git repo inside zamp-ai/; Zamp PDF NOT committed)
  backend/  FastAPI · SQLAlchemy 2 (psycopg3) · Alembic · Pydantic v2 · PyMuPDF · pytesseract · rapidfuzz · httpx(Ollama) · structlog · pytest
    app/api/routes/{invoices,runs,vendors,purchase_orders,reviews,audit,policies,dashboard,auth,health}.py
    app/core/{config,logging,security,errors}.py
    app/db/{base,session}.py, app/db/models/*, migrations/ (Alembic)
    app/schemas/*
    app/services/{storage,ingestion,extraction,vendor_resolution,po_matching,reconciliation,
                  duplicate_detection,policy_engine,decision_engine,workflow,audit,review,reporting,money}
    app/workers/runner.py        DB-backed job queue (jobs table, SELECT … FOR UPDATE SKIP LOCKED, lease + heartbeat, stale-lease reclaim on restart)
    app/seed/                    reference data + demo users + policy v1
    tests/{unit,integration,e2e}
  frontend/ Next.js 15 (App Router) · TS · Tailwind v4 · Radix primitives (custom shadcn-style kit) · TanStack Query/Table · RHF + Zod · react-pdf · Recharts · lucide · next-themes · sonner · Geist fonts
  data/fixtures/  generated scenario PDFs + scenarios.yaml (expected values/checks/status)
  scripts/        generate_fixtures.py, evaluate.py, reset_demo.sh
  docs/           10 docs from spec §14 + IMPLEMENTATION_PLAN.md
  demo/           runbook.md, scenario-index.md
  Makefile, docker-compose.yml, render.yaml, .env.example, README.md
```
Key design choices:
- **Workflow = persisted state machine.** Stages: RECEIVED → FILE_VALIDATION → TEXT_EXTRACTION → FIELD_EXTRACTION → VENDOR_RESOLUTION → PO_MATCHING → FINANCIAL_RECONCILIATION → DUPLICATE_CHECK → RISK_AND_POLICY_CHECKS → DECISION. Each stage writes STAGE_STARTED/STAGE_COMPLETED/STAGE_FAILED events (duration, structured details, evidence refs, redacted errors). Run stores attempt, extractor, policy version, final decision.
- **Live view:** SSE `/api/runs/{id}/events/stream` tails `run_events` by id; honours `Last-Event-ID` / `?after=` so reconnect neither loses nor duplicates; frontend falls back to polling. No artificial delays by default; optional `DEMO_STAGE_PACING_MS` (default 0) is documented, excluded from recorded durations, and shown as a label in the UI when on.
- **Money:** `Decimal` everywhere, `Numeric(18,2)` amounts, `Numeric(18,3)` qty, ROUND_HALF_UP at 2dp, explicit rounding tolerance from policy. Original extracted text stored separately from normalised values.
- **Extraction contract:** `DocumentExtractor.extract() -> ExtractionResult` with per-field `{value, raw, confidence, evidence{page, snippet, bbox}, method}`. Confidence is *derived*, not invented: text-layer label match → rule confidence; OCR → Tesseract word confidences of the value tokens. Ollama output validated by Pydantic and **every value must be found in the source text** or it's discarded; prompt states document text is untrusted data. Missing → `null` + extraction issue.
- **Vendor resolution:** GSTIN (with real checksum validation) → vendor code → normalised legal name/alias → fuzzy (candidate-only, margin rule) + address/state corroboration → else AMBIGUOUS.
- **PO matching:** exact ref + vendor; else rank vendor's open POs (description, amount, date, currency, line structure); auto-select only if score ≥ 0.90 and margin ≥ 0.08 and no contradiction.
- **Reconciliation:** arithmetic (Σlines = subtotal, subtotal+tax = total), tax per line, 2-way vs 3-way (labelled honestly), unit-price variance %, qty vs remaining ordered/received, cumulative consumption via `po_line_consumptions` (unique per invoice×line, reserved under `SELECT … FOR UPDATE` on the PO at the decision boundary; released on reject/cancel).
- **Duplicates:** L1 SHA-256 at upload (no new invoice; linked + audited on original), L2 business key (vendor+norm invoice no+currency+total) → ON_HOLD, L3 near-duplicate (transparent similarity rule) → warning with candidate.
- **Checks** carry code, severity (INFO/WARNING/REVIEW/BLOCKER), status (PASS/FAIL/INDETERMINATE), message, actual, expected/threshold, evidence, policy version. **Decision matrix** (no weighted score): REJECTED > ON_HOLD > NEEDS_REVIEW > READY_FOR_APPROVAL; FAILED only for technical failure (retryable vs non-retryable classification). Manager approval → APPROVED (explicitly not payment).
- **Human review:** confirm/correct field, mark unreadable, select PO candidate, request info (draft message, never sent), hold, reject (mandatory reason), mark ready (only if no blockers), manager override (reason + audited), assign, note. Each: permission + transition validation → persist → immutable audit event (before/after) → re-run deterministic stages from VENDOR_RESOLUTION onward as a new run attempt.
- **Demo auth:** seeded fictional users (AP Analyst, AP Manager, Auditor), login → HMAC-signed token; roles enforced server-side; clearly documented as demo auth, not enterprise RBAC.
- **Policy:** versioned rows; settings screen saves a new version; each run pins its version. Defaults per spec §7.4, labelled "sample policy".

## Fictional dataset
Buyer: fictional Indian mid-size manufacturer (INR). 18 vendors (mix approved / pending onboarding / blocked, valid-checksum fictional GSTINs, masked bank fingerprints + version), ~35 POs (goods + services), ~12 GRNs incl. partial receipts. Fixture PDFs generated with reportlab in 3–4 distinct vendor layouts, incl. multi-page line tables, scanned (rasterised + noise) and corrupt files, all watermarked "SYNTHETIC DEMO DOCUMENT". Dashboard history comes from processing a background batch through the **real pipeline** (`make demo-load`), not inserted results.

Scenarios S01–S12 per spec §12, each with expected extraction/checks/status in `scenarios.yaml`. Demo focus: S01 happy path, S09 price variance, S02/S03 duplicates, S08 bank-detail change (+ S06 ambiguous PO).

## Milestones (each: implement → tests → run → exercise via API/UI → fix → commit)
- **M0 Setup** — install tesseract; repo + git identity + private GitHub repo; uv backend, Next frontend, Makefile, .env.example, Postgres role/db, Alembic, `/api/health` + readiness (db, tesseract, ollama status).
- **M1 Data model + seed** — all entities from spec §5.1 + jobs, consumptions, checks, review actions, audit, policies, users; indexes; seed/reset command.
- **M2 Fixtures** — PDF generator + scenario catalogue.
- **M3 Intake → text** — upload/batch (ext, MIME, size, `%PDF` magic, server storage key), storage abstraction, job queue + worker, workflow engine, events, SSE, PyMuPDF + OCR fallback, retry/idempotency.
- **M4 Field extraction** — deterministic parser, Ollama provider, evidence verification, schema validation.
- **M5 Vendor + PO + line matching.**
- **M6 Reconciliation, duplicates, policy, decision, PO reservation** — heavy unit tests (money, tolerance boundaries, GSTIN, ranking, consumption, decision matrix, transitions).
- **M7 Review, audit, retry** — actions, re-evaluation, vendor info-request draft, decision report.
- **M8 Read APIs** — dashboard summary/activity (real aggregates, documented KPI defs), lists with search/filter/sort/pagination, CSV export, policies.
- **M9 Frontend** — app shell (sidebar: Overview, Invoices, Processing runs, Review queue, Purchase orders, Vendors, Audit log, Policies), light default + dark toggle, login; dashboard, intake (drag-drop, batch), invoice list, live run timeline, invoice investigation (PDF pane with page nav/zoom + extracted fields w/ confidence/evidence + recon table expected/actual/delta/tolerance/result + checks + decision + review controls + audit), review queue, POs/vendors detail, audit log w/ export, policy editor. Loading/empty/error/retry states throughout. (May parallelise screens via forked subagents once API contract is fixed.)
- **M10 Evaluation + E2E** — `scripts/evaluate.py` runs all fixtures through the real pipeline, measures accuracy/routing/latency (median, p95) with denominators → `docs/EVALUATION.md`; pytest integration (DB, SSE reconnect, retry idempotency, review audit); API-level e2e; Playwright smoke if disk/time allow.
- **M11 Docs + packaging** — README, 10 docs, demo runbook, scenario index, Dockerfiles, docker-compose, render.yaml; final clean-setup check; push.

Priority if time runs short (spec §16): upload → happy path → live timeline → financial exception → duplicates → review/audit → dashboard polish → remaining edge cases/docs.

## Verification
- `make test` (unit + integration + e2e pytest), `npm run typecheck && npm run lint && npm run build` in frontend.
- `make dev` → backend :8000, worker, frontend :3000; upload S01 via UI, watch SSE timeline, confirm READY_FOR_APPROVAL with evidence; run S09/S02/S03/S08/S06/S07/S12 and confirm statuses match `scenarios.yaml`; perform a review action and confirm audit entry; restart services and confirm history persists; toggle dark mode.
- `make evaluate` produces measured metrics; final report lists what was verified vs incomplete.
