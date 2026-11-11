# Scenario index

Generated from `data/fixtures/scenarios.yaml` (`make fixtures`). Each PDF is in `data/fixtures/pdfs/`. The
`expect` columns are asserted by `backend/tests/integration/test_scenarios.py` and measured by `make evaluate`.
History invoices (H01–H12) give the dashboard real history and set up prerequisites; `make demo-load` processes them.

| ID | Title | PDF | Prerequisites | Expected status | Expected reason codes | Why |
|---|---|---|---|---|---|---|
| H01 | Welding gases, October | `H01_KIG-26-27-1043.pdf` | - | READY_FOR_APPROVAL | - |  |
| H02 | Hydraulics overhaul, partial delivery | `H02_SH-2026-0612.pdf` | - | READY_FOR_APPROVAL | - |  |
| H03 | Spare pumps invoiced before receipt | `H03_SH-2026-0688.pdf` | - | ON_HOLD | GRN_PENDING |  |
| H04 | Canteen services, October | `H04_LCS-1026.pdf` | - | READY_FOR_APPROVAL | - |  |
| H05 | Lean advisory, 4 days | `H05_TNC-INV-2026-118.pdf` | - | READY_FOR_APPROVAL | - |  |
| H06 | Office consumables (original of S03) | `H06_MOS-2026-0457.pdf` | - | READY_FOR_APPROVAL | - |  |
| H07 | Steel, first split invoice (S04a) | `H07_SGS-26-27-1187.pdf` | - | READY_FOR_APPROVAL | - |  |
| H08 | Fasteners, first invoice (S05a) | `H08_IF-26-3301.pdf` | - | READY_FOR_APPROVAL | - |  |
| H09 | PPE from vendor still in onboarding | `H09_ASE-2026-077.pdf` | - | ON_HOLD | VENDOR_NOT_APPROVED |  |
| H10 | Housekeeping, October | `H10_OFM-2026-10-221.pdf` | - | READY_FOR_APPROVAL | - |  |
| H11 | Anchor bolts, price within tolerance | `H11_IFS-2026-0419.pdf` | - | READY_FOR_APPROVAL | - |  |
| H12 | Invoice against a closed PO | `H12_BEPL-26-27-0371.pdf` | - | NEEDS_REVIEW | PO_CLOSED |  |
| S01 | Clean invoice, three-way match | `S01_PBI-2026-0981.pdf` | - | READY_FOR_APPROVAL | - | Approved vendor, exact PO reference, quantities fully received (GRN-780101), prices and 18% IGST match the PO. |
| S03 | Same invoice re-sent in a different format | `Meridian_reminder_MOS-2026-0457.pdf` | H06 | ON_HOLD | INVOICE_DUPLICATE_SUSPECTED | Vendor re-sends invoice MOS/2026/0457 as a 'reminder' with a different layout and number formatting. Bytes differ, so the file hash does not match; the business key does. |
| S04 | Second split invoice within PO balance | `S04_SGS-26-27-1214.pdf` | H07 | READY_FOR_APPROVAL | - | PO-450110 ordered 400 angles and 120 plates. H07 already invoiced 250 + 80. This invoice bills the remaining 150 + 40, all received across two GRNs. |
| S05 | Cumulative quantity exceeds PO and receipts | `S05_IF-26-3388.pdf` | H08 | NEEDS_REVIEW | QUANTITY_EXCEEDED, GRN_QUANTITY_MISMATCH | 5,000 bolts ordered and received; 3,000 already invoiced (H08). This invoice claims 2,500 more: 500 over the ordered and received quantity. |
| S06 | No PO reference, two plausible POs | `S06_CL-2026-7781.pdf` | - | NEEDS_REVIEW | PO_AMBIGUOUS | Freight invoice without a PO number. Two open POs (PO-450130, PO-450131) have identical lanes and rates, so ranking cannot separate them. |
| S07 | Poor-quality scan | `S07_SPI-1311-26.pdf` | - | NEEDS_REVIEW | LOW_EXTRACTION_CONFIDENCE, CRITICAL_FIELD_MISSING | Image-only scan with smudging over the header. OCR must be used and the critical fields come back with low confidence; the system must not guess. |
| S08 | Remittance bank details changed | `S08_NCS-INV-26-1104.pdf` | - | NEEDS_REVIEW | VENDOR_BANK_DETAILS_CHANGED | Monthly cloud invoice that is otherwise perfect, but asks for payment into a different bank account than the verified vendor master. |
| S09 | Unit price above tolerance | `S09_VSS-26-27-0412.pdf` | - | NEEDS_REVIEW | PRICE_VARIANCE_EXCEEDED | Licences billed at 43,500 against a PO price of 42,000 (+3.57%, tolerance 2%). |
| S10 | Totals do not add up | `S10_BEPL-26-27-0402.pdf` | - | NEEDS_REVIEW | TOTAL_ARITHMETIC_MISMATCH | Line items and tax are correct but the printed grand total is 10,000 higher than subtotal + tax. |
| S11 | Blocked vendor | `S11_RPM-2026-0559.pdf` | - | REJECTED | VENDOR_NOT_APPROVED | Vendor exists in master data but was blocked after failed KYC re-verification. |
| S12 | Corrupted PDF | `S12_corrupted_upload.pdf` | - | FAILED | - | A file that starts with a PDF header but whose body is damaged. |
| S13 | Multi-page invoice, 26 lines | `S13_GLH-2026-11-0093.pdf` | - | READY_FOR_APPROVAL | - | Line-item table spans two pages. |
| S14 | Clean scanned invoice | `S14_KIG-26-27-1268.pdf` | - | READY_FOR_APPROVAL | - | Image-only PDF (no text layer) read by OCR; good scan quality, goods received. |
| S15 | Unfamiliar free-form layout | `S15_LCS-1131.pdf` | - | NEEDS_REVIEW | CRITICAL_FIELD_MISSING, LINE_ITEM_UNMATCHED | A letter instead of an invoice template: no labels, no table. Rules recover only the PO; with Ollama running, the local model proposes header values that are kept only if found verbatim in the text. Line items still cannot be reconciled, so it goes to review. |
| S02 | Exact duplicate file | `S01_PBI-2026-0981.pdf` | S01 | linked to original, no new invoice | FILE_DUPLICATE | Upload the S01 PDF a second time (identical bytes). |
