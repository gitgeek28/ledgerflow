# Security and trust boundaries

## Untrusted input

- **Files**: extension, MIME type, size (20 MB default) and `%PDF-` signature are checked before storage. Bytes are
  stored under a random server-generated key (`YYYY/MM/<uuid>.pdf`); the client filename is sanitised and kept only
  as metadata. Storage paths are resolved and confined to the storage root (no traversal). Filesystem paths are
  never returned. Parsing happens in the worker, and an unreadable file becomes a technical failure.
- **Document text** is data. The local-LLM prompt states that the document is untrusted and that instructions inside
  it must be ignored. Output is constrained by a JSON schema and validated with Pydantic. **Every value must be found
  in the document text** (verbatim for text; same amount, date or currency for typed values) or it is discarded.
  The model never overrides a rule-extracted value and never touches arithmetic, matching or decisions.
- **OCR output** carries its real confidence; low confidence on a critical field routes to a person.

## Sensitive data

- Bank account numbers are reduced to a keyed HMAC fingerprint plus the last four digits before persistence. Digit
  runs of 8+ are masked in stored evidence snippets and document text. Comparisons with the vendor master use
  fingerprints only.
- GSTINs are masked in vendor views (they are printed on the invoice itself, which reviewers can see).
- A bank-detail difference is never written back to the vendor master; it raises a high-priority security
  escalation, and the generated vendor email tells the vendor *not* to send bank details by email.
- Logs are structured JSON with request IDs. Invoice contents and secrets are not logged; unexpected errors record
  the exception class, not document text.

## Access control

- Demo authentication: seeded users and a shared demo password; a session token signed with `SECRET_KEY` in an
  HttpOnly, SameSite=Lax cookie (Secure in production via `COOKIE_SECURE`). This is explicitly **not** enterprise
  identity.
- Roles are enforced on the server for every state-changing endpoint: auditors are read-only; overrides, cancel,
  policy changes and approvals above the threshold are manager-only. The person who accepted exceptions cannot
  approve the same invoice.
- Requests are same-origin through the Next.js proxy, so SameSite cookies prevent cross-site form posts. CORS is
  restricted to configured local origins.

## Integrity

- The audit table is append-only, enforced by a PostgreSQL trigger.
- Review actions lock the invoice row; PO consumption is reserved under a row lock on the PO; business-key duplicate
  checks run under a per-vendor advisory lock; the file hash is a unique constraint.
- Secrets come only from the environment (`backend/.env`, not committed); `.env.example` documents them.
