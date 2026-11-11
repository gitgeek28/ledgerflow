# Five-minute demo runbook

**Before the call (5 min)**
1. `make dev` (or have API, worker and web running) and `ollama serve` if you want to show the LLM fallback.
2. `make demo-load`: resets and builds history (12 invoices through the real pipeline; 4 approved by the manager).
3. Optional, so the audience can follow each stage: start the API and worker with `DEMO_STAGE_PACING_MS=600`.
   The UI labels the pacing, and recorded durations exclude it.
4. Sign in as **Aisha Rao (AP Analyst)** in one window and **Vikram Iyer (AP Manager)** in a private window.
5. Keep **Upload invoices** open. Every sample button uploads the real PDF through the same intake endpoint.

| Time | Do | Say |
|---|---|---|
| 0:00–0:25 | **Overview** | "LedgerFlow takes an invoice from PDF to a decision AP can defend, not just extraction. Every number here is computed from runs in the database: 12 invoices so far, touchless rate, value at risk, exception breakdown." |
| 0:25–1:40 | Upload **S01** → live run opens | Narrate the stages as they arrive: "embedded text, 12 of 12 fields, vendor resolved by GSTIN with checksum, PO-450101 by reference, three-way match against GRN-780101, no duplicate, approved vendor, bank details match the verified master → *ready for approval*. It's ₹3.3L, above the ₹2.5L threshold, so it still needs a manager." Click **Review evidence**, then click the crosshair beside *Grand total* to highlight it on the PDF. |
| 1:40–2:35 | Upload **S09** | "Licences billed at ₹43,500 against a PO price of ₹42,000: +3.57% against a 2% tolerance." Open **Reconciliation**: expected, actual, delta, tolerance. "It doesn't approve and it doesn't silently fix the number. It routes to review with the arithmetic shown. The higher price also exhausts the PO value, so that's a blocker only a manager can override." |
| 2:35–3:20 | Upload **S02** (same file as S01), then **S03** | "Identical bytes: caught by hash, no second invoice, the re-submission is logged on the original. S03 is the same invoice re-sent as a 'reminder' in a different layout with the number formatted MOS-2026-0457. The hash differs, but vendor + normalised number + currency + total match, so it's held. Not called fraud, just held." Optionally **S08**: "an otherwise perfect invoice asking for payment to a new bank account. High-priority security escalation; the vendor master is never updated from an invoice." |
| 3:20–4:20 | On **S09** as the analyst: **Mark ready** → blocked ("manager override required"). As the manager: **Mark ready** with the reason "Rate revision agreed; PO amendment raised", then try **Approve** → blocked by separation of duties. Open **Activity & audit** | "Human actions are first-class: reasons are mandatory, roles are enforced on the server, and the person who accepts an exception can't also approve. The audit trail distinguishes system decisions from human actions, and the database rejects any edit to it." Alternatively, on **S06** select a PO candidate and watch the re-evaluation run. |
| 4:20–5:00 | Open **Policies** and the docs/EVALUATION page | "Deterministic code decides; the free local Llama model only proposes values on unfamiliar layouts, and they're kept only if found in the document. Measured on 26 synthetic submissions; that is not production accuracy. The next step is evaluating on real labelled invoices and syncing POs and GRNs from the ERP." |

**If something goes wrong live:** the run view falls back to polling if streaming drops, and every result is
persisted, so open **Processing runs** to show the completed run. `S12` deliberately shows the technical-failure
path (not retryable, never "rejected").
