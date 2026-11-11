# Limitations and roadmap

## Honest limitations

- **Synthetic evaluation.** The 100% results in [EVALUATION.md](EVALUATION.md) cover 26 synthetic submissions in
  4 layouts the rule extractor was built against. They show the pipeline behaves as designed, not that it would
  reach that accuracy on real vendors' invoices. Unseen layouts will mostly route to review. That is safe, but it
  lowers the touchless rate.
- **Local LLM is optional and modest.** Llama 3.2 3B on a laptop takes about 5 s per call (about 27 s on a cold
  start). It only fills missing header fields and cannot read line-item tables. Its output varies between runs,
  which is why it is verified and never trusted directly.
- **OCR** is Tesseract with English data only. Handwriting, stamps over figures and very low-resolution scans will
  produce missing or low-confidence fields; they are routed to review, not guessed. Single-digit table cells are a
  known Tesseract weakness.
- **One-to-one line matching.** Bundled lines (one invoice line covering several PO lines) are reported as
  unmatched for review rather than allocated automatically.
- **Single currency in practice.** Currency is checked but there is no FX conversion; a mismatch goes to review.
- **Demo auth** with a shared password, no SSO/MFA, coarse roles.
- **Storage** is the local filesystem behind an interface. On free hosting tiers it is ephemeral.
- **Deployment artefacts** (Dockerfiles, `docker-compose.yml`, `render.yaml`) are written and `docker compose
  config` validates, but the images were not built or deployed on the build machine (no container runtime was
  running). The verified path is the local setup in the README.
- No email ingestion, ERP integration or payment execution (out of scope by design).

## Next production steps

1. **Real-document evaluation**: label a few hundred real invoices; measure per-field accuracy and touchless rate
   with and without the LLM fallback; tune thresholds from data.
2. **Stronger extraction for unseen layouts**: a document-layout model (e.g. Docling or PaddleOCR table structure)
   for line items, and a larger local or hosted model behind the same verification boundary.
3. **Learning from reviewers**: store corrections per vendor and promote stable ones into vendor-specific
   templates, with each promotion an audited, versioned change.
4. **Integrations**: mailbox ingestion; ERP/PO and GRN sync instead of seeded master data; export approved
   invoices to the payment run.
5. **Identity and governance**: SSO, fine-grained permissions, approval limits per user, maker-checker on vendor
   bank changes.
6. **Operations**: object storage, metrics and alerting on queue age and failure rates, horizontal workers.
