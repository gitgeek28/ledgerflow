"""Ordered, explainable vendor resolution: tax ID -> vendor code -> exact name/alias -> fuzzy (candidates only)."""
import re
from dataclasses import dataclass, field
from decimal import Decimal

from rapidfuzz import fuzz

from app.db.models import Vendor
from app.services.checks import CheckResult
from app.services.identifiers import is_valid_gstin, mask_tax_id
from app.services.policy import PolicySettings
from app.services.text_norm import normalise_name


@dataclass
class VendorResolution:
    status: str                        # RESOLVED | AMBIGUOUS | NOT_FOUND | CONFLICT
    vendor: Vendor | None = None
    method: str | None = None
    score: float | None = None
    candidates: list[dict] = field(default_factory=list)
    supporting: list[str] = field(default_factory=list)
    conflicting: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"status": self.status, "vendor_id": str(self.vendor.id) if self.vendor else None,
                "vendor_code": self.vendor.vendor_code if self.vendor else None,
                "vendor_name": self.vendor.legal_name if self.vendor else None, "method": self.method,
                "score": self.score, "candidates": self.candidates, "supporting": self.supporting,
                "conflicting": self.conflicting}


def name_similarity(a: str, b: str) -> float:
    na, nb = normalise_name(a), normalise_name(b)
    if not na or not nb:
        return 0.0
    return round(max(fuzz.token_sort_ratio(na, nb), fuzz.ratio(na, nb)) / 100.0, 4)


def best_name_score(name: str, vendor: Vendor) -> float:
    return max([name_similarity(name, vendor.legal_name), name_similarity(name, vendor.display_name)]
               + [name_similarity(name, a) for a in (vendor.aliases or [])])


def resolve_vendor(vendors: list[Vendor], *, tax_id: str | None, name: str | None, document_text: str,
                   policy: PolicySettings, override_vendor_id: str | None = None) -> VendorResolution:
    by_id = {str(v.id): v for v in vendors}
    if override_vendor_id and override_vendor_id in by_id:
        v = by_id[override_vendor_id]
        return VendorResolution("RESOLVED", v, "human-selected", 1.0,
                                supporting=["Vendor selected by a reviewer"])

    supporting, conflicting = [], []
    gstin_valid = is_valid_gstin(tax_id)
    # 1. Exact tax identifier
    if tax_id and gstin_valid:
        match = next((v for v in vendors if v.tax_id == tax_id), None)
        if match:
            supporting.append(f"GSTIN {mask_tax_id(tax_id)} matches vendor master exactly")
            if name:
                sim = best_name_score(name, match)
                if sim >= 0.75:
                    supporting.append(f"Printed name corroborates ({sim:.2f} similarity)")
                else:
                    conflicting.append(f"Printed name '{name}' differs from master '{match.legal_name}' "
                                       f"({sim:.2f})")
            if tax_id[:2] == (match.state_code or tax_id[:2]):
                supporting.append(f"GSTIN state code {tax_id[:2]} matches registered state")
            return VendorResolution("RESOLVED", match, "tax-id", 1.0, supporting=supporting,
                                    conflicting=conflicting)
        supporting.append(f"GSTIN {mask_tax_id(tax_id)} is valid but not in the vendor master")
    elif tax_id:
        conflicting.append(f"Printed GSTIN {mask_tax_id(tax_id)} fails checksum; not used for matching")

    # 2. Vendor code printed on the document
    code_match = re.search(r"\bV-\d{4}\b", document_text or "")
    if code_match:
        v = next((x for x in vendors if x.vendor_code == code_match.group(0)), None)
        if v:
            return VendorResolution("RESOLVED", v, "vendor-code", 1.0,
                                    supporting=[f"Vendor code {v.vendor_code} printed on invoice"])

    if not name:
        return VendorResolution("NOT_FOUND", supporting=supporting, conflicting=conflicting + [
            "No supplier name or usable tax ID on the invoice"])

    # 3/4. Exact normalised name or alias, then fuzzy candidates
    scored = sorted(((best_name_score(name, v), v) for v in vendors), key=lambda x: x[0], reverse=True)
    candidates = [{"vendor_id": str(v.id), "vendor_code": v.vendor_code, "name": v.legal_name,
                   "score": s, "status": v.approved_status} for s, v in scored[:3] if s >= 0.6]
    top_score, top = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    exact = normalise_name(name) in {normalise_name(x) for x in [top.legal_name, top.display_name, *top.aliases]}

    if tax_id and gstin_valid and top.tax_id and top.tax_id != tax_id and top_score >= 0.75:
        conflicting.append(f"Name resembles {top.legal_name} but its GSTIN differs from the invoice's")
        return VendorResolution("CONFLICT", None, "name", top_score, candidates, supporting, conflicting)
    margin = Decimal(str(top_score - second))
    if exact and margin >= policy.vendor_fuzzy_min_margin:
        supporting.append(f"Normalised name '{normalise_name(name)}' equals master/alias")
        return VendorResolution("RESOLVED", top, "name-exact", top_score, candidates, supporting, conflicting)
    if Decimal(str(top_score)) >= policy.vendor_fuzzy_min_score and margin >= policy.vendor_fuzzy_min_margin:
        supporting.append(f"Fuzzy name match {top_score:.2f}, margin {float(margin):.2f} over next candidate")
        return VendorResolution("RESOLVED", top, "name-fuzzy", top_score, candidates, supporting, conflicting)
    if top_score >= 0.75:
        conflicting.append(f"Top candidates too close to choose safely (margin {float(margin):.2f})"
                           if margin < policy.vendor_fuzzy_min_margin else
                           f"Best similarity {top_score:.2f} below threshold {policy.vendor_fuzzy_min_score}")
        return VendorResolution("AMBIGUOUS", None, "name-fuzzy", top_score, candidates, supporting, conflicting)
    return VendorResolution("NOT_FOUND", None, None, top_score, candidates, supporting,
                            conflicting + [f"No vendor name above 0.75 similarity (best {top_score:.2f})"])


def vendor_checks(res: VendorResolution) -> list[CheckResult]:
    ev = {"candidates": res.candidates, "supporting": res.supporting, "conflicting": res.conflicting}
    if res.status == "RESOLVED":
        return [CheckResult("VENDOR_NOT_FOUND", "PASS",
                            f"Vendor resolved to {res.vendor.vendor_code} {res.vendor.legal_name} ({res.method})",
                            actual=res.vendor.vendor_code, evidence=ev)]
    if res.status in ("AMBIGUOUS", "CONFLICT"):
        return [CheckResult("VENDOR_AMBIGUOUS", "FAIL",
                            "Vendor could not be determined safely: " + "; ".join(res.conflicting),
                            actual=", ".join(c["vendor_code"] for c in res.candidates[:3]) or None, evidence=ev)]
    return [CheckResult("VENDOR_NOT_FOUND", "FAIL", "No matching vendor in master data. " +
                        "; ".join(res.conflicting), evidence=ev)]
