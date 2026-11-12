# Policy reference

Generated from `backend/app/services/policy.py`, the single source of truth that the decision engine uses.
Defaults are an **illustrative demo policy**, not accounting advice. Settings are versioned: saving creates a new
version, and every run records the version it applied.

## Tolerances and settings (policy v1 defaults)

| Setting | Default | Effect |
|---|---|---|
| `unit_price_variance_pct` | 2.00 | Invoice unit price more than this % above the PO price -> PRICE_VARIANCE_EXCEEDED (review) |
| `invoice_total_variance_abs` | 500.00 | Subtotal more than this (INR) above PO-priced value of invoiced qty -> AMOUNT_VARIANCE_EXCEEDED; also slack on PO balance |
| `quantity_variance_pct` | 0.00 | Allowed over-billing vs remaining ordered/received quantity (0 = none) |
| `rounding_tolerance_abs` | 1.00 | Largest arithmetic difference treated as rounding (lines, subtotal, tax, total) |
| `critical_field_confidence` | 0.85 | Invoice number / date / total below this confidence -> LOW_EXTRACTION_CONFIDENCE |
| `po_candidate_min_score` | 0.90 | Without a PO reference, best candidate must score at least this to be auto-selected |
| `po_candidate_min_margin` | 0.08 | ...and beat the runner-up by this margin, else PO_AMBIGUOUS |
| `vendor_fuzzy_min_score` | 0.90 | Fuzzy name match must reach this similarity to resolve a vendor |
| `vendor_fuzzy_min_margin` | 0.06 | ...with this margin over the next vendor, else VENDOR_AMBIGUOUS |
| `line_match_min_similarity` | 0.60 | Invoice line needs at least this description similarity to match a PO line |
| `require_grn_for_goods` | True | Goods POs without a posted goods receipt -> GRN_PENDING (hold) |
| `near_duplicate_window_days` | 45 | Window for the near-duplicate (warning) rule |
| `near_duplicate_amount_pct` | 1.00 | Amount closeness for the near-duplicate rule |
| `manager_approval_above` | 250000.00 | Invoices above this value need an AP manager to approve |
| `blocked_vendor_outcome` | REJECT | Outcome for invoices from BLOCKED vendors (REJECT or HOLD); pending-onboarding vendors always HOLD |

## Reason codes

Severity: `INFO` < `WARNING` < `REVIEW` < `BLOCKER`. Outcome is what a failing check does to the decision.
Resolution says how a person can clear it (see [WORKFLOW.md](WORKFLOW.md)).

| Code | Title | Severity | Outcome on failure | Resolution | Meaning |
|---|---|---|---|---|---|
| `FILE_INVALID` | File invalid or unreadable | BLOCKER | NONE | NONE | The uploaded file could not be opened as a PDF. This is a technical failure, not a business rejection. |
| `FILE_DUPLICATE` | Exact file already received | INFO | NONE | NONE | Identical bytes (SHA-256) were uploaded before; the submission is linked to the original invoice. |
| `INVOICE_DUPLICATE_SUSPECTED` | Duplicate invoice suspected | BLOCKER | HOLD | OVERRIDE | Same vendor, invoice number, currency and amount as an existing invoice. Held so it cannot be paid twice. |
| `INVOICE_NEAR_DUPLICATE` | Similar invoice exists | WARNING | NONE | ACCEPT | A prior invoice is similar (amount/date/lines) but not conclusively the same. Shown for awareness. |
| `VENDOR_NOT_FOUND` | Vendor not in master data | BLOCKER | REVIEW | CORRECT | No approved-vendor record matched the supplier identity on the invoice. |
| `VENDOR_AMBIGUOUS` | Vendor ambiguous | BLOCKER | REVIEW | CORRECT | More than one vendor record is a plausible match; a person must choose. |
| `VENDOR_NOT_APPROVED` | Vendor not approved | BLOCKER | REJECT | OVERRIDE | The vendor exists but is blocked or still in onboarding; invoices cannot proceed to approval. |
| `VENDOR_BANK_DETAILS_CHANGED` | Remittance details differ from vendor master | BLOCKER | REVIEW | OVERRIDE | Bank details on the invoice do not match the verified vendor master. Possible payment diversion — verify with the vendor through a known contact before paying. Vendor master is never updated from an invoice. |
| `TAX_ID_INVALID` | Supplier GSTIN invalid | REVIEW | REVIEW | ACCEPT | The GSTIN printed on the invoice fails the format or checksum test. |
| `CRITICAL_FIELD_MISSING` | Critical field missing | BLOCKER | REVIEW | CORRECT | A field required to make a decision (invoice number, date, total, supplier identity) could not be read. |
| `LOW_EXTRACTION_CONFIDENCE` | Low extraction confidence | REVIEW | REVIEW | CORRECT | A critical field was read below the configured confidence threshold; a person should confirm it. |
| `PO_NOT_FOUND` | Purchase order not found | BLOCKER | REVIEW | CORRECT | The referenced PO does not exist for this vendor, or no eligible PO could be identified. |
| `PO_AMBIGUOUS` | Purchase order ambiguous | BLOCKER | REVIEW | CORRECT | Several open POs are plausible and the ranking margin is too small to auto-select. |
| `PO_CLOSED` | Purchase order closed | BLOCKER | REVIEW | OVERRIDE | The matched PO is closed or cancelled. |
| `PO_VENDOR_MISMATCH` | PO belongs to a different vendor | BLOCKER | REVIEW | CORRECT | The referenced PO exists but is issued to a different vendor. |
| `CURRENCY_MISMATCH` | Currency mismatch | BLOCKER | REVIEW | OVERRIDE | Invoice currency differs from PO currency. No FX conversion is performed. |
| `LINE_ITEM_UNMATCHED` | Line item not on PO | REVIEW | REVIEW | ACCEPT | An invoice line could not be matched one-to-one to a PO line. |
| `PRICE_VARIANCE_EXCEEDED` | Unit price variance above tolerance | REVIEW | REVIEW | ACCEPT | Invoiced unit price exceeds the PO price by more than the configured tolerance. |
| `AMOUNT_VARIANCE_EXCEEDED` | Invoice amount variance above tolerance | REVIEW | REVIEW | ACCEPT | Invoice subtotal differs from the PO-priced value of the invoiced quantities by more than tolerance. |
| `TAX_MISMATCH` | Tax mismatch | REVIEW | REVIEW | ACCEPT | Tax rate or tax amount differs from the PO or from the invoice's own line arithmetic. |
| `TOTAL_ARITHMETIC_MISMATCH` | Totals do not add up | BLOCKER | REVIEW | CORRECT | Line amounts, subtotal, tax and grand total on the invoice do not reconcile. Request a corrected invoice. |
| `QUANTITY_EXCEEDED` | Quantity exceeds PO remaining | BLOCKER | REVIEW | OVERRIDE | Cumulative invoiced quantity would exceed the quantity ordered on the PO line. |
| `GRN_QUANTITY_MISMATCH` | Invoiced more than received | BLOCKER | REVIEW | OVERRIDE | Cumulative invoiced quantity exceeds the quantity received on goods receipts (three-way match). |
| `GRN_PENDING` | Goods receipt pending | REVIEW | HOLD | NONE | Goods PO with no goods receipt recorded yet. Held until receipt is posted. |
| `PO_BALANCE_EXCEEDED` | PO value exhausted | BLOCKER | REVIEW | OVERRIDE | Cumulative invoiced value would exceed the PO value plus tolerance. |
| `PO_EXPIRED` | PO validity lapsed | WARNING | NONE | ACCEPT | The invoice is dated after the PO's validity date. |
| `DATE_INVALID` | Invoice date implausible | REVIEW | REVIEW | CORRECT | The invoice date is in the future or the due date precedes the invoice date. |
| `MANUAL_REVIEW_REQUIRED` | Manual review required | REVIEW | REVIEW | ACCEPT | A reviewer has requested manual review. |
| `MANAGER_APPROVAL_REQUIRED` | Manager approval required | INFO | NONE | NONE | Invoice value exceeds the threshold that requires AP manager approval. |

Every check row stores: code, stage, subject (e.g. `line 2`), severity, status (`PASS` / `FAIL` / `INDETERMINATE`),
outcome, explanation, actual, expected, delta, tolerance, evidence and policy version.

## Status semantics

- **Rejection**: a defined policy violation or invalid transaction (e.g. blocked vendor), or a reviewer's reasoned
  rejection.
- **Hold**: waiting for information or a dependency (goods receipt, onboarding, vendor reply, duplicate confirmation).
- **Review**: a person must investigate or exercise judgement.
- **Ready for approval**: automated checks passed or exceptions were accepted with reasons; a second person still
  approves.
- **Failed**: a technical problem prevented a reliable decision. It is never presented as a business rejection.

A suspected duplicate or a bank-detail change is labelled as such, never as fraud.

