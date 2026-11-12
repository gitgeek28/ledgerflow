# LedgerFlow — Intelligent Accounts Payable Operations

LedgerFlow takes a vendor invoice PDF and produces an AP decision you can explain. It extracts the
financial data with evidence, resolves the vendor and purchase order, and reconciles amounts and quantities
against the PO and goods receipts, including split invoices that consume the same PO over time. It detects
duplicates and policy exceptions and routes anything uncertain to a person. Every stage runs for real and is
persisted, so the run can be watched live and reconstructed later.

Built by **Devanshi** for the AI Solutions Analyst case study, problem statement **PS-1 (Finance / AP: invoice
processing, from PDF to decision)**. All companies, documents and records are synthetic. This is an independent
case-study build, not a product of any company.

## Live demo

**https://ledgerflow-mauve.vercel.app**: sign in as any demo user with password `ledgerflow-demo`.

| Part | Hosting |
|---|---|
| Web app (Next.js) | Vercel; `/api/*` is proxied to the backend so the session cookie stays first-party |
| API + background worker (FastAPI, Tesseract OCR) | Render free web service, Docker, Singapore; worker runs in-process |
| Database + stored PDFs | Neon Postgres (Singapore), pooled connection for the app, direct connection for migrations |

The free Render instance sleeps after 15 minutes idle: open the site about a minute before a demo so the first
request isn't a cold start. The local Llama fallback is not available on the hosted tier (`LLM_PROVIDER=none`);
rules + OCR handle all catalogued scenarios.

## What it does

| Stage | What actually happens |
|---|---|
| Intake | PDF validation (extension, MIME, size, `%PDF` signature), SHA-256 exact-duplicate guard, server-generated storage key |
| Text extraction | PyMuPDF text layer; Tesseract OCR for image-only pages, keeping real per-word confidence |
| Field extraction | Layout-aware rule parser (labels, stacked labels, totals block, line-item table by column geometry); optional **free local LLM** (Llama 3.2 via Ollama) fallback whose answers are kept only if found in the document |
| Vendor resolution | GSTIN (with checksum) → vendor code → exact name/alias → fuzzy candidates with a margin rule → ambiguous |
| PO matching | Explicit reference, or ranked candidates with a transparent score; auto-select only with a clear margin |
| Reconciliation | Decimal arithmetic, unit price/amount/tax tolerances, cumulative quantity against ordered **and received** (three-way when a GRN exists), PO value balance |
| Duplicates | Exact file hash, business key (vendor + number + currency + total), near-duplicate warning |
| Risk & policy | Vendor status, remittance bank-detail change (security escalation), extraction confidence, dates, approval thresholds |
| Decision | Deterministic matrix — `REJECTED` > `ON_HOLD` > `NEEDS_REVIEW` > `READY_FOR_APPROVAL`; technical failures are `FAILED`, never a business rejection |
| Human review | Correct/confirm fields, select PO/vendor (re-runs checks), accept exceptions with reasons, manager overrides, two-person approval, vendor info-request drafts (never sent), notes, assignment |

## Quick start (local)

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+, PostgreSQL 16, Tesseract
(`brew install tesseract` / `apt-get install tesseract-ocr`). Optional: [Ollama](https://ollama.com) with
`ollama pull llama3.2` for the local LLM fallback.

```bash
make setup        # backend (uv sync) + frontend (npm install)
make db           # create role 'ledgerflow' and databases ledgerflow / ledgerflow_test (local superuser psql)
make migrate      # Alembic migrations
make demo-load    # reset + seed reference data + run 12 history invoices through the real pipeline
make dev          # API :8000, worker, web :3000
```

Open **http://localhost:3000** and sign in as a demo user (password `ledgerflow-demo`):

| User | Role | Can |
|---|---|---|
| Aisha Rao / Rohan Desai | AP Analyst | upload, review, correct, accept review-level exceptions, hold, reject, request info |
| Vikram Iyer | AP Manager | everything above + override blockers, approve above threshold, cancel, edit policy |
| Meera Joshi | Internal Auditor | read-only |

Then open **Upload invoices** and use the *Sample invoices* panel, or drop files from `data/fixtures/pdfs/`.
The five-minute script is in [`demo/runbook.md`](demo/runbook.md).

Docker alternative (not exercised on the build machine, see Limitations): `docker compose up --build`.

## Commands

| Command | Purpose |
|---|---|
| `make test` | 100 backend unit + integration tests against `ledgerflow_test` |
| `make test-e2e` | Playwright browser tests (needs `make dev`; resets demo data) |
| `make lint` | ruff + eslint + TypeScript |
| `make evaluate` | Measured evaluation over the scenario catalogue → [`docs/EVALUATION.md`](docs/EVALUATION.md) |
| `make evaluate-llm` | Same with the Ollama fallback enabled |
| `make fixtures` | Regenerate the synthetic PDFs and `data/fixtures/scenarios.yaml` |
| `make reset` | Delete all data and reseed reference data |

Optional environment variables are documented in [`backend/.env.example`](backend/.env.example). The most useful
for a live audience is `DEMO_STAGE_PACING_MS=600`. It adds a labelled pause between stages so people can follow
the timeline. The pause is shown in the UI and excluded from recorded durations.

## Documentation

- [Product overview](docs/PRODUCT_OVERVIEW.md): users, problem, scope, assumptions
- [Architecture](docs/ARCHITECTURE.md): components, data flow, design choices
- [Workflow](docs/WORKFLOW.md): stages, states, decision rules, exception handling
- [Data model](docs/DATA_MODEL.md)
- [Policy reference](docs/POLICY_REFERENCE.md): reason codes, tolerances, status semantics
- [Evaluation](docs/EVALUATION.md): method and measured results
- [API](docs/API.md)
- [Security](docs/SECURITY.md)
- [Limitations and roadmap](docs/LIMITATIONS_AND_ROADMAP.md)
- [Demo runbook](demo/runbook.md) · [Scenario index](demo/scenario-index.md) · [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

## Repository layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, services, worker, seed + evaluation, tests
frontend/   Next.js 15 app (App Router, Tailwind 4, TanStack Query, react-pdf, Recharts), Playwright e2e
data/       fixtures/ (synthetic invoice PDFs + scenarios.yaml), eval/ (latest measured results)
docs/       product, architecture, workflow, data model, policy, evaluation, API, security, limitations
demo/       five-minute runbook and scenario index
scripts/    dev launcher, DB bootstrap, evaluation wrapper
```
