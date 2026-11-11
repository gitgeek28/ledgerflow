"""Normalisation helpers for vendor names, descriptions, and invoice numbers."""
import re

LEGAL_SUFFIXES = [
    "private limited", "pvt ltd", "pvt. ltd.", "pvt. ltd", "pvt ltd.", "p ltd", "limited", "ltd", "ltd.",
    "llp", "inc", "incorporated", "corporation", "corp", "co", "company", "and co", "& co",
]
ABBREVIATIONS = {
    "pcs": "piece", "pc": "piece", "nos": "unit", "no": "unit", "ea": "each", "qty": "quantity",
    "mtr": "metre", "mtrs": "metre", "m": "metre", "kg": "kilogram", "kgs": "kilogram", "ltr": "litre",
    "hrs": "hour", "hr": "hour", "mo": "month", "mth": "month", "yr": "year", "svc": "service",
    "maint": "maintenance", "lic": "licence", "license": "licence", "licenses": "licence",
    "licences": "licence", "subs": "subscription", "dia": "diameter", "assy": "assembly", "w/": "with",
    "galv": "galvanised", "galvanized": "galvanised", "ss": "stainless steel", "ms": "mild steel",
    "amc": "annual maintenance contract", "hsn": "", "sac": "",
}
UNIT_ALIASES = {
    "each": "EA", "ea": "EA", "nos": "EA", "no": "EA", "pcs": "EA", "pc": "EA", "piece": "EA", "pieces": "EA",
    "unit": "EA", "units": "EA", "set": "SET", "sets": "SET", "kg": "KG", "kgs": "KG", "mtr": "M", "m": "M",
    "metre": "M", "meter": "M", "ltr": "L", "l": "L", "litre": "L", "hr": "HR", "hrs": "HR", "hour": "HR",
    "hours": "HR", "month": "MO", "months": "MO", "mo": "MO", "lot": "LOT", "box": "BOX", "boxes": "BOX",
    "licence": "EA", "license": "EA", "user": "EA", "users": "EA", "day": "DAY", "days": "DAY",
}


def normalise_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for suffix in sorted(LEGAL_SUFFIXES, key=len, reverse=True):
            suf = re.sub(r"[^a-z0-9 ]+", " ", suffix).strip()
            suf = re.sub(r"\s+", " ", suf)
            if s.endswith(" " + suf):
                s = s[: -len(suf) - 1].strip()
                changed = True
    return s


def normalise_description(text: str | None) -> str:
    if not text:
        return ""
    s = text.lower()
    s = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", s)
    s = re.sub(r"[^a-z0-9x./ ]+", " ", s)
    tokens = []
    for tok in s.split():
        tok = tok.strip("./")
        if not tok:
            continue
        mapped = ABBREVIATIONS.get(tok, tok)
        if mapped:
            tokens.append(mapped)
    return " ".join(tokens)


def normalise_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    key = unit.strip().lower().rstrip(".")
    return UNIT_ALIASES.get(key, key.upper())


def normalise_invoice_number(number: str | None) -> str | None:
    if not number:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", number).upper()
    return s or None


def normalise_po_number(number: str | None) -> str | None:
    if not number:
        return None
    digits = re.sub(r"[^A-Za-z0-9]", "", number).upper()
    return digits or None
