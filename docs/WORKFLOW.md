# Workflow

## Stages

| # | Stage | Work performed | Can fail technically? |
|---|---|---|---|
| 0 | RECEIVED | File stored, hash recorded (written at intake) | — |
| 1 | FILE_VALIDATION | Open with MuPDF; reject encrypted, empty, >50 pages, unparseable | Yes, non-retryable (`PDF_*`) |
| 2 | TEXT_EXTRACTION | Text layer per page; pages with <40 visible characters are OCR'd at 300 dpi | Yes, `OCR_UNAVAILABLE` retryable |
| 3 | FIELD_EXTRACTION | Rule parser; local LLM fallback only if a critical field or the supplier identity is missing; schema validation; bank account reduced to fingerprint + last 4 | — |
| 4 | VENDOR_RESOLUTION | Tax ID → vendor code → exact name/alias → fuzzy with margin → ambiguous/conflict | — |
| 5 | PO_MATCHING | Reference, or ranked open POs for the vendor; one-to-one line matching | — |
| 6 | FINANCIAL_RECONCILIATION | Arithmetic; price, amount and tax vs PO; cumulative quantity vs ordered and received; PO balance | — |
| 7 | DUPLICATE_CHECK | Business key under an advisory lock; near-duplicate rule | — |
| 8 | RISK_AND_POLICY_CHECKS | Vendor status, remittance change, confidence, dates, approval threshold | — |
| 9 | DECISION | Decision matrix; PO reservation under a row lock | — |

Re-evaluation runs (after a human correction, PO/vendor selection or "re-run checks") start at stage 4 and reuse
the persisted extraction. The live view marks stages 1–3 as reused.

## Statuses

| Status | Meaning | Typical next step |
|---|---|---|
| PROCESSING | A run is queued or executing | Watch the live run |
| READY_FOR_APPROVAL | All mandatory checks passed (or a person accepted the exceptions); PO balance reserved | Second person approves |
| NEEDS_REVIEW | A person must investigate or exercise judgement | Correct, select, accept with reason, or reject |
| ON_HOLD | Waiting on information or a dependency (GRN, onboarding, vendor reply, duplicate confirmation) | Release when resolved |
| REJECTED | A defined policy violation (e.g. blocked vendor) or a reviewer's rejection | None; the record stays |
| APPROVED | Authorised for a payment run (LedgerFlow does not pay) | — |
| FAILED | Technical failure prevented a reliable decision; not a business outcome | Retry if retryable, else request a new file |
| CANCELLED | Withdrawn by an AP manager | — |

## Decision rules

Each failing check carries an **outcome**: `REJECT`, `HOLD`, `REVIEW` or `NONE` (informational). The decision is
the most severe outcome present:

```
any REJECT  → REJECTED
any HOLD    → ON_HOLD
any REVIEW  → NEEDS_REVIEW
otherwise   → READY_FOR_APPROVAL
```

There is no weighted risk score. `INDETERMINATE` checks fail closed with their catalogue outcome. Informational
items, such as manager approval required or a near-duplicate warning, are shown but don't block. The summary leads
with root causes (unit price before total value) and quotes actual vs expected.

## Exception handling and human resolution

Every reason code has a **resolution** type (see the [policy reference](POLICY_REFERENCE.md)):

| Resolution | Who | How |
|---|---|---|
| ACCEPT | Analyst or manager | "Mark ready" with a mandatory reason (e.g. a price revision agreed with the buyer) |
| CORRECT | Analyst or manager | Fix the data: correct or confirm a field, mark it unreadable, select a PO or vendor. A re-evaluation run follows |
| OVERRIDE | AP manager only | Mark ready with a recorded override reason; audited as `OVERRIDE_AND_MARK_READY` |
| NONE | — | Wait for the dependency (e.g. goods receipt), then "re-run checks" |

Further rules:
- Approval needs a manager above ₹2.5L (policy setting).
- The person who accepted exceptions cannot also approve (separation of duties).
- Reject, hold and cancel require a reason.
- "Request info" drafts a vendor email from the open exceptions and places the invoice on hold. It never sends
  anything. For bank-detail changes it explicitly tells the vendor not to send bank details by email.

## Retry and idempotency

- The exact file hash is unique in the database, so concurrent identical uploads resolve to one invoice.
- Retrying is allowed only for the latest run, only if it `FAILED`, only if the failure is retryable, and only when
  no run is in progress. Each retry is a new attempt with a link to the previous run.
- Business failures (a rejected vendor, a duplicate) are never retried as if they were infrastructure errors.
- A worker crash is recovered by lease expiry. After `JOB_MAX_ATTEMPTS` (3) interrupted attempts, the run fails
  with `WORKER_RETRIES_EXHAUSTED` (retryable).
