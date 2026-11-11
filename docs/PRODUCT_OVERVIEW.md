# Product overview

## The problem (PS-1)

A mid-size company receives hundreds of vendor invoices a month as PDFs. An AP analyst opens each one, finds the PO,
checks whether the numbers line up and decides what to do. The documents are messy: different layouts, some scanned,
itemised or bundled lines, tax embedded or separate, PO references explicit or missing, and sometimes the invoice
number, date or total isn't there at all. Procurement has its own rules: approved vendors, PO amounts, tolerances,
duplicate rules. Vendors split one PO across several invoices. Amounts are close but not exact. The decision has to be
explainable.

## What LedgerFlow is

An AP operations workbench that turns an invoice PDF into a **reasoned, auditable decision**, with every step in
between visible. It is built around the AP analyst's day: an intake screen, a live run view, an investigation screen
with the document beside the evidence, a prioritised review queue, and a dashboard for the AP manager.

The guiding idea: **an invoice is not valid just because OCR read it correctly.** Extraction is the first of nine
stages. Most of the value is in matching, cumulative reconciliation, duplicate and fraud-adjacent checks, and getting
uncertain cases to a person with the evidence already assembled.

## Users

| User | Jobs |
|---|---|
| AP analyst | Upload single or batch; watch processing; inspect fields with evidence; resolve exceptions (correct fields, choose PO, accept variances with reasons); draft vendor queries; hold or reject |
| AP manager | Monitor volume, value at risk and touchless rate; override blockers with recorded reasons; approve high-value invoices; version the policy |
| Auditor | Reconstruct any decision: original PDF, extracted evidence, matched records, policy version, system vs human actions, timestamps |

## Scope delivered

All P0 items in the build spec and most P1 items: batch upload, multi-PO candidate ranking, split-invoice
consumption, bank-detail change escalation, policy versioning, CSV exports, measured evaluation report, safe retries,
assignment and notes, and a printable decision report. P2 items (email ingestion, ERP integration, payments, live FX)
are out of scope by design.

## Edge cases (the guide asks for 2–4; 12 are built, 4–5 are featured in the demo)

| | Edge case | Why it matters |
|---|---|---|
| S09 | Unit price 3.57% above PO (tolerance 2%) | Most common AP exception; the system shows expected, actual, delta and tolerance and routes to review rather than approving |
| S02 / S03 | Same invoice re-sent: identical file, and a re-formatted copy with different bytes and number formatting | Duplicate payment is the classic AP loss; the hash catches the first, the business key catches the second |
| S08 | Clean invoice asking for payment to a different bank account | Payment-diversion fraud pattern: escalated as high priority, vendor master never auto-updated |
| S06 | No PO reference and two equally plausible POs | Shows the system refusing to guess when similarity can't separate candidates |
| S04 / S05 | Second split invoice within balance vs. one that over-bills ordered and received quantities | Cumulative consumption across invoices, three-way match |
| S07 / S14 | Poor scan vs clean scan | Real OCR confidence drives review; nothing is guessed |
| S10, S11, S12, S13, S15 | Totals don't add up; blocked vendor; corrupt file; 26-line two-page invoice; free-form letter | Arithmetic evidence; policy rejection vs technical failure; multi-page tables; fail-closed + verified LLM fallback |

## Assumptions (made deliberately, per the guide's FAQ)

- Fictional buyer **Kestrel Components Pvt Ltd** (Pune, India), currency INR, Indian GST (CGST+SGST intra-state,
  IGST inter-state). Currency is still an explicit field; no FX conversion is attempted.
- Tolerances are an illustrative demo policy (2% unit price, ₹500 amount, 0% quantity, confidence 0.85, PO
  auto-select 0.90 with a 0.08 margin), configurable and versioned. They are not accounting advice.
- Goods POs require a goods receipt before payment (three-way match); services POs use two-way matching.
- PO balance is consumed only when an invoice reaches *ready for approval* or *approved*. Invoices in review don't
  reserve balance, so a stuck invoice can't block legitimate ones.
- "Approval" authorises inclusion in a payment run. LedgerFlow never executes payments.
- Demo authentication (seeded users and a shared password) stands in for SSO. Roles are enforced server-side.
- Extraction must be free to run: no paid APIs. The default path is deterministic; the local LLM is optional.
