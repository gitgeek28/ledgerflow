// Mirrors backend/app/schemas/api.py. Money and quantities are decimal strings - never parsed into floats
// for arithmetic; they are only formatted for display.
export type Money = string;

export type InvoiceStatus =
  | "PROCESSING" | "READY_FOR_APPROVAL" | "NEEDS_REVIEW" | "ON_HOLD" | "REJECTED" | "APPROVED" | "FAILED"
  | "CANCELLED";
export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
export type Role = "AP_ANALYST" | "AP_MANAGER" | "AUDITOR";

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface User { id: string; email: string; name: string; title: string; role: Role }
export interface VendorRef { id: string; vendor_code: string; legal_name: string; approved_status: string }

export interface Vendor {
  id: string; vendor_code: string; legal_name: string; display_name: string; aliases: string[];
  tax_id_masked: string | null; state_code: string | null; city: string; category: string; approved_status: string;
  status_reason: string | null; currency: string; payment_terms_days: number; bank_name: string | null;
  bank_account_last4: string | null; bank_ifsc: string | null; bank_details_version: number;
  bank_details_updated_at: string | null; open_po_count: number; invoice_count: number; open_invoice_value: Money;
}

export interface PurchaseOrder {
  id: string; po_number: string; vendor: VendorRef; status: string; po_type: string; currency: string;
  po_date: string; valid_until: string; description: string; requester: string; cost_centre: string;
  subtotal: Money; tax_total: Money; total_amount: Money; invoiced_value: Money; remaining_value: Money;
  grn_count: number;
}
export interface POLine {
  id: string; line_number: number; item_code: string | null; description: string; quantity_ordered: string;
  unit: string; unit_price: Money; tax_rate: string; line_subtotal: Money; line_total: Money;
  quantity_received: string | null; quantity_invoiced: string; quantity_remaining: string | null;
}
export interface PODetail extends PurchaseOrder {
  lines: POLine[];
  goods_receipts: { grn_number: string; received_date: string; received_by: string; warehouse: string;
    lines: { po_line: number; quantity_received: string }[] }[];
  invoices: { id: string; reference: string; invoice_number: string | null; status: InvoiceStatus;
    amount_consumed: Money; consumption: string }[];
}

export interface Check {
  id: number; stage: string; code: string; name: string; subject: string | null; severity: string;
  status: "PASS" | "FAIL" | "INDETERMINATE"; outcome: "NONE" | "REVIEW" | "HOLD" | "REJECT"; message: string;
  actual: string | null; expected: string | null; delta: string | null; threshold: string | null;
  evidence: Record<string, unknown> | null; policy_version: number; accepted: boolean; resolution: string | null;
}

export interface InvoiceLine {
  id: string; line_number: number; description: string | null; quantity: string | null; unit: string | null;
  unit_price: Money | null; tax_rate: string | null; line_subtotal: Money | null; line_total: Money | null;
  matched_po_line_id: string | null; match_score: string | null; extraction_confidence: string | null;
  evidence: Evidence | null;
}

export interface Evidence { page: number; snippet: string; bbox?: number[] | null }
export interface ExtractedField {
  value: string | null; raw: string | null; confidence: number; method: string | null; evidence: Evidence | null;
  notes: string[];
}

export interface InvoiceListItem {
  id: string; reference: string; original_filename: string; status: InvoiceStatus; priority: string;
  invoice_number: string | null; invoice_date: string | null; due_date: string | null; currency: string | null;
  grand_total: Money | null; vendor: VendorRef | null; vendor_name_raw: string | null; po_number: string | null;
  reason_codes: string[]; next_action: string | null; match_mode: string | null; assignee: User | null;
  created_at: string; decided_at: string | null; decided_by: string; age_hours: number | null;
}

export interface Run {
  id: string; invoice_id: string; attempt: number; trigger: string; start_stage: string; status: RunStatus;
  current_stage: string | null; extractor: string | null; policy_version: number | null; decision: string | null;
  reason_codes: string[]; error_code: string | null; error_message: string | null; retryable: boolean | null;
  pacing_ms: number; created_at: string; started_at: string | null; finished_at: string | null;
  duration_ms: number | null; invoice_reference: string | null; invoice_filename: string | null;
  vendor_name: string | null; triggered_by: string | null;
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface RunDetail extends Run { stage_outputs: Record<string, any> }

export interface RunEvent {
  id: number; run_id: string; stage: string | null; event_type: string; status: string; message: string;
  details: Record<string, unknown> | null; evidence_refs: string[] | null; duration_ms: number | null;
  occurred_at: string;
}

export interface AuditEvent {
  id: number; invoice_id: string | null; run_id: string | null; entity_type: string; entity_id: string | null;
  entity_label: string | null; actor_type: "SYSTEM" | "USER"; actor_name: string; action: string;
  reason_code: string | null; note: string | null; before: Record<string, unknown> | null;
  after: Record<string, unknown> | null; occurred_at: string;
}

export interface Note { id: string; body: string; created_at: string; author: User }

export interface InvoiceDetail extends InvoiceListItem {
  file_size: number; page_count: number | null; file_sha256: string; subtotal: Money | null; tax_total: Money | null;
  po_reference_raw: string | null; po_id: string | null; vendor_tax_id_masked: string | null;
  bank_account_last4: string | null; decision_summary: string | null;
  extraction: { fields: Record<string, ExtractedField>; lines: unknown[]; issues: { field: string; code: string;
    message: string }[]; extractor: string; llm: Record<string, unknown> | null } | null;
  extraction_method: string | null; field_overrides: Record<string, { value: string | null; by: string; at: string;
    reason: string | null; unreadable?: boolean; confirmed?: boolean }>;
  accepted_exceptions: Record<string, unknown>; po_selected_by_human: boolean;
  duplicate_of: { id: string; reference: string; status: InvoiceStatus } | null; info_request_draft: string | null;
  document_text: { pages: { page: number; method: string; mean_confidence: number | null; lines: string[] }[] } | null;
  lines: InvoiceLine[]; checks: Check[]; latest_run: RunDetail | null; runs: Run[]; notes: Note[];
  uploaded_by: string | null; duplicate_submissions: { at: string; by: string; filename: string }[];
  permissions: { can_act: boolean; is_manager: boolean };
}

export interface UploadResult {
  filename: string; outcome: "CREATED" | "DUPLICATE_FILE" | "REJECTED"; invoice_id: string | null;
  reference: string | null; run_id: string | null; message: string; error_code: string | null;
}

export interface Policy {
  id: string; version: number; name: string; settings: Record<string, string | number | boolean>;
  change_note: string | null; is_active: boolean; effective_from: string; created_at: string;
  created_by: string | null; runs_using: number;
}
export interface ReasonCode { code: string; title: string; severity: string; outcome: string; resolution: string;
  description: string }

export interface Sample { id: string; title: string; group: string; description: string; filename: string;
  expected_status: string | null; expected_codes: string[]; prerequisites: string[] }

export interface DashboardSummary {
  period_days: number; generated_at: string;
  kpis: { received: number; total_value: Money; currency: string; ready_for_approval: number; approved: number;
    needs_review: number; on_hold: number; rejected: number; failed: number; processing: number;
    touchless_rate: number | null; exception_rate: number | null; decided_first_pass: number;
    processing_ms_median: number | null; processing_ms_p95: number | null; end_to_end_ms_median: number | null;
    technical_failures: number; value_at_risk: Money };
  status_counts: Record<string, number>; status_value: Record<string, Money>;
  exception_breakdown: { code: string; count: number }[];
  series: { date: string; received: number; value: Money; ready_or_approved: number; exceptions: number }[];
  recent_runs: Run[]; attention: InvoiceListItem[]; queue: { queued: number; running: number };
  definitions: Record<string, string>;
}

export interface Readiness {
  status: string; database: boolean; storage: boolean; ocr: { available: boolean; engine?: string } | null;
  llm: { provider: string; reachable?: boolean; model?: string; model_available?: boolean } | null;
  queue: { queued: number; running: number; oldest_queued_seconds: number | null } | null;
  policy_version: number | null; demo_stage_pacing_ms: number; embedded_worker: boolean;
}
