"""Typed API contracts. Money is serialised as decimal strings, never floats."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class UserOut(ORM):
    id: uuid.UUID
    email: str
    name: str
    title: str
    role: str


class LoginIn(BaseModel):
    email: str
    password: str


class LoginOut(BaseModel):
    user: UserOut
    token: str


class VendorRef(ORM):
    id: uuid.UUID
    vendor_code: str
    legal_name: str
    approved_status: str


class VendorOut(ORM):
    id: uuid.UUID
    vendor_code: str
    legal_name: str
    display_name: str
    aliases: list[str]
    tax_id_masked: str | None
    state_code: str | None
    city: str
    category: str
    approved_status: str
    status_reason: str | None
    currency: str
    payment_terms_days: int
    bank_name: str | None
    bank_account_last4: str | None
    bank_ifsc: str | None
    bank_details_version: int
    bank_details_updated_at: datetime | None
    open_po_count: int = 0
    invoice_count: int = 0
    open_invoice_value: Decimal = Decimal(0)


class POLineOut(ORM):
    id: uuid.UUID
    line_number: int
    item_code: str | None
    description: str
    quantity_ordered: Decimal
    unit: str
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    line_total: Decimal
    quantity_received: Decimal | None = None
    quantity_invoiced: Decimal = Decimal(0)
    quantity_remaining: Decimal | None = None


class GRNOut(BaseModel):
    grn_number: str
    received_date: date
    received_by: str
    warehouse: str
    lines: list[dict]


class POOut(ORM):
    id: uuid.UUID
    po_number: str
    vendor: VendorRef
    status: str
    po_type: str
    currency: str
    po_date: date
    valid_until: date
    description: str
    requester: str
    cost_centre: str
    subtotal: Decimal
    tax_total: Decimal
    total_amount: Decimal
    invoiced_value: Decimal = Decimal(0)
    remaining_value: Decimal = Decimal(0)
    grn_count: int = 0


class PODetail(POOut):
    lines: list[POLineOut]
    goods_receipts: list[GRNOut]
    invoices: list[dict]


class CheckOut(ORM):
    id: int
    stage: str
    code: str
    name: str
    subject: str | None
    severity: str
    status: str
    outcome: str
    message: str
    actual: str | None
    expected: str | None
    delta: str | None
    threshold: str | None
    evidence: dict | None
    policy_version: int
    accepted: bool
    resolution: str | None = None


class InvoiceLineOut(ORM):
    id: uuid.UUID
    line_number: int
    description: str | None
    quantity: Decimal | None
    unit: str | None
    unit_price: Decimal | None
    tax_rate: Decimal | None
    line_subtotal: Decimal | None
    line_total: Decimal | None
    matched_po_line_id: uuid.UUID | None
    match_score: Decimal | None
    extraction_confidence: Decimal | None
    evidence: dict | None


class InvoiceListItem(ORM):
    id: uuid.UUID
    reference: str
    original_filename: str
    status: str
    priority: str
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    currency: str | None
    grand_total: Decimal | None
    vendor: VendorRef | None
    vendor_name_raw: str | None
    po_number: str | None
    reason_codes: list[str]
    next_action: str | None
    match_mode: str | None
    assignee: UserOut | None
    created_at: datetime
    decided_at: datetime | None
    decided_by: str
    age_hours: float | None = None


class RunOut(ORM):
    id: uuid.UUID
    invoice_id: uuid.UUID
    attempt: int
    trigger: str
    start_stage: str
    status: str
    current_stage: str | None
    extractor: str | None
    policy_version: int | None
    decision: str | None
    reason_codes: list[str]
    error_code: str | None
    error_message: str | None
    retryable: bool | None
    pacing_ms: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    invoice_reference: str | None = None
    invoice_filename: str | None = None
    vendor_name: str | None = None
    triggered_by: str | None = None


class RunDetail(RunOut):
    stage_outputs: dict


class RunEventOut(ORM):
    id: int
    run_id: uuid.UUID
    stage: str | None
    event_type: str
    status: str
    message: str
    details: dict | None
    evidence_refs: list | None
    duration_ms: int | None
    occurred_at: datetime


class AuditOut(ORM):
    id: int
    invoice_id: uuid.UUID | None
    run_id: uuid.UUID | None
    entity_type: str
    entity_id: str | None
    entity_label: str | None
    actor_type: str
    actor_name: str
    action: str
    reason_code: str | None
    note: str | None
    before: dict | None
    after: dict | None
    occurred_at: datetime


class NoteOut(ORM):
    id: uuid.UUID
    body: str
    created_at: datetime
    author: UserOut


class InvoiceDetail(InvoiceListItem):
    file_size: int
    page_count: int | None
    file_sha256: str
    subtotal: Decimal | None
    tax_total: Decimal | None
    po_reference_raw: str | None
    po_id: uuid.UUID | None
    vendor_tax_id_masked: str | None
    bank_account_last4: str | None
    decision_summary: str | None
    extraction: dict | None
    extraction_method: str | None
    field_overrides: dict
    accepted_exceptions: dict
    po_selected_by_human: bool
    duplicate_of: dict | None
    info_request_draft: str | None
    document_text: dict | None
    lines: list[InvoiceLineOut]
    checks: list[CheckOut]
    latest_run: RunDetail | None
    runs: list[RunOut]
    notes: list[NoteOut]
    uploaded_by: str | None
    duplicate_submissions: list[dict]
    permissions: dict


class ReviewActionIn(BaseModel):
    action: Literal["CORRECT_FIELD", "CONFIRM_FIELD", "MARK_UNREADABLE", "SELECT_PO", "SELECT_VENDOR",
                    "RE_EVALUATE", "REQUEST_INFO", "HOLD", "REJECT", "MARK_READY", "APPROVE", "CANCEL"]
    reason: str | None = Field(None, max_length=1000)
    note: str | None = Field(None, max_length=2000)
    field: str | None = None
    value: str | None = Field(None, max_length=200)
    po_id: uuid.UUID | None = None
    vendor_id: uuid.UUID | None = None


class ReviewActionOut(BaseModel):
    invoice_id: uuid.UUID
    status: str
    run_id: uuid.UUID | None
    draft: str | None
    message: str


class NoteIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class AssignIn(BaseModel):
    assignee_id: uuid.UUID | None


class UploadResult(BaseModel):
    filename: str
    outcome: Literal["CREATED", "DUPLICATE_FILE", "REJECTED"]
    invoice_id: uuid.UUID | None = None
    reference: str | None = None
    run_id: uuid.UUID | None = None
    message: str
    error_code: str | None = None


class BatchResult(BaseModel):
    batch_id: uuid.UUID
    results: list[UploadResult]


class PolicyOut(ORM):
    id: uuid.UUID
    version: int
    name: str
    settings: dict[str, Any]
    change_note: str | None
    is_active: bool
    effective_from: datetime
    created_at: datetime
    created_by: str | None = None
    runs_using: int = 0


class PolicyIn(BaseModel):
    settings: dict[str, Any]
    change_note: str = Field(..., min_length=3, max_length=500)
