# Data model

PostgreSQL 16, managed with Alembic (`backend/migrations`). Money is `NUMERIC(18,2)`, quantities `NUMERIC(18,3)`,
rates `NUMERIC(5,2)`. JSONB holds flexible evidence and stage outputs. Core entities are relational and indexed.

```
users ─┐
       ├─< invoices >── vendors ──< purchase_orders ──< po_lines ──< goods_receipt_lines >── goods_receipts
       │      │  │                        ▲                ▲
       │      │  └──< invoice_lines ──────┼── matched ─────┘
       │      │            └──< po_line_consumptions (RESERVED / APPROVED / RELEASED)
       │      ├──< processing_runs ──< run_events      (one row per stage event; SSE source)
       │      │          └──< invoice_checks           (one row per check, per run, with policy version)
       │      ├──< audit_events   (append-only, DB trigger blocks UPDATE/DELETE)
       │      └──< invoice_notes
       └─ policies (versioned; is_active marks the current version)      jobs (1:1 with runs; queue + lease)
```

| Table | Key columns | Notes |
|---|---|---|
| `vendors` | vendor_code, legal_name, aliases[], tax_id (GSTIN, unique), approved_status, bank_account_fingerprint, bank_account_last4, bank_ifsc, bank_details_version | Account numbers are stored only as an HMAC fingerprint + last four digits |
| `purchase_orders` / `po_lines` | po_number (unique), vendor_id, status, po_type (GOODS/SERVICES), validity, totals; per line: qty ordered, unit, unit price, tax rate | |
| `goods_receipts` / `goods_receipt_lines` | grn_number, po_id, received_date; qty received per PO line | Enables three-way match and partial receipts |
| `invoices` | reference (LF-001234), file_sha256 (**unique**: layer-1 duplicate guard), storage_key, status, priority, assignee, extracted header columns, `extraction` (field-level JSON with confidence + evidence), `field_overrides` (human corrections), decision summary, reason codes, duplicate_of | Index on (vendor_id, invoice_number_normalised) for business-key duplicates |
| `invoice_lines` | qty, unit, unit price, tax rate, subtotal, matched_po_line_id, match_score, extraction_confidence, evidence | |
| `po_line_consumptions` | po_line_id, invoice_line_id, quantity, amount, status | Partial unique index: one **active** reservation per invoice line; released rows kept as history |
| `processing_runs` | attempt (unique per invoice), trigger (UPLOAD/RETRY/REEVALUATION), start_stage, status, extractor, policy_id + version, decision, error_code, retryable, stage_outputs (JSONB), duration_ms, pacing_ms | |
| `run_events` | bigserial id (SSE cursor), stage, event_type, status, message, details, duration_ms, evidence_refs | Index (run_id, id) |
| `invoice_checks` | run_id, stage, code, subject, severity, status, outcome, actual/expected/delta/threshold, evidence, policy_version, accepted | |
| `audit_events` | actor_type (SYSTEM/USER), actor, action, reason_code, note, before/after JSON, occurred_at | Trigger `trg_audit_events_immutable` |
| `jobs` | run_id (unique), status, attempts, locked_by, lease_until | Claimed with `FOR UPDATE SKIP LOCKED` |
| `policies` | version (unique), settings JSON, change_note, is_active, created_by | |

Migrations: `0001` schema · `0002` append-only audit trigger · `0003` partial unique consumption index ·
`0004` invoice reference sequence.
