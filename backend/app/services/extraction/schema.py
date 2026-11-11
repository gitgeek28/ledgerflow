"""Typed extraction contract. Every field carries value + raw text + confidence + evidence + method."""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Evidence(BaseModel):
    page: int
    snippet: str = Field(max_length=300)
    bbox: list[float] | None = None


class ExtractedField(BaseModel):
    value: str | None = None          # normalised value as string (Decimal/date serialised as text)
    raw: str | None = None            # text as printed
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    method: str | None = None         # label | label-below | pattern | layout | derived | llm-verified
    evidence: Evidence | None = None
    notes: list[str] = Field(default_factory=list)

    @property
    def present(self) -> bool:
        return self.value is not None


class ExtractedLine(BaseModel):
    line_number: int
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_rate_source: str | None = None   # column | summary (single rate in tax summary) | None
    line_subtotal: Decimal | None = None
    line_total: Decimal | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    arithmetic_consistent: bool | None = None
    evidence: Evidence | None = None


HEADER_FIELDS = ["invoice_number", "invoice_date", "due_date", "po_number", "currency", "vendor_name",
                 "vendor_tax_id", "subtotal", "tax_total", "grand_total", "bank_account", "bank_ifsc"]
CRITICAL_FIELDS = ["invoice_number", "invoice_date", "grand_total"]


class ExtractionIssue(BaseModel):
    field: str
    code: str
    message: str


class ExtractionResult(BaseModel):
    fields: dict[str, ExtractedField]
    lines: list[ExtractedLine]
    issues: list[ExtractionIssue] = Field(default_factory=list)
    extractor: str
    llm: dict | None = None

    @field_validator("fields")
    @classmethod
    def _all_fields(cls, v: dict[str, ExtractedField]) -> dict[str, ExtractedField]:
        for name in HEADER_FIELDS:
            v.setdefault(name, ExtractedField())
        return v

    def get(self, name: str) -> str | None:
        f = self.fields.get(name)
        return f.value if f else None

    def decimal(self, name: str) -> Decimal | None:
        v = self.get(name)
        return Decimal(v) if v is not None else None

    def date(self, name: str) -> date | None:
        v = self.get(name)
        return date.fromisoformat(v) if v else None
