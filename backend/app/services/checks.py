"""A single machine-readable check result. Severity/outcome default from the reason-code catalogue."""
from dataclasses import dataclass, field

from app.services.policy import CATALOGUE


@dataclass
class CheckResult:
    code: str
    status: str                      # PASS | FAIL | INDETERMINATE
    message: str
    subject: str | None = None
    actual: str | None = None
    expected: str | None = None
    delta: str | None = None
    threshold: str | None = None
    evidence: dict = field(default_factory=dict)
    severity: str | None = None
    outcome: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        meta = CATALOGUE.get(self.code)
        self.name = self.name or (meta.title if meta else self.code.replace("_", " ").title())
        if self.status == "PASS":
            self.severity = self.severity or "INFO"
            self.outcome = "NONE"
        else:
            self.severity = self.severity or (meta.severity if meta else "REVIEW")
            self.outcome = self.outcome or (meta.outcome if meta else "REVIEW")

    @property
    def failing(self) -> bool:
        return self.status != "PASS" and self.outcome != "NONE"

    def to_json(self) -> dict:
        return {k: getattr(self, k) for k in ("code", "name", "status", "severity", "outcome", "message", "subject",
                                              "actual", "expected", "delta", "threshold", "evidence")}
