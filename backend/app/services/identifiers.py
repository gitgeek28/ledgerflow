"""Indian GSTIN validation (format + mod-36 checksum), IFSC format, bank-account fingerprinting."""
import hashlib
import hmac
import re

from app.core.config import get_settings

GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        value = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return _CHARS[(36 - total % 36) % 36]


def is_valid_gstin(gstin: str | None) -> bool:
    if not gstin or len(gstin) != 15 or not GSTIN_RE.fullmatch(gstin):
        return False
    return gstin_check_char(gstin[:14]) == gstin[14]


def make_gstin(state_code: str, pan: str, entity: str = "1") -> str:
    base = f"{state_code}{pan}{entity}Z"
    return base + gstin_check_char(base)


def normalise_account(account: str) -> str:
    return re.sub(r"\D", "", account or "")


def bank_fingerprint(account: str) -> str:
    """Keyed hash of the account number so it never needs to be stored or compared in clear.
    IFSC (a public branch code) is stored and compared separately, so an unreadable IFSC cannot cause a false
    mismatch on its own."""
    msg = normalise_account(account).encode()
    return hmac.new(get_settings().secret_key.encode(), msg, hashlib.sha256).hexdigest()


def mask_tax_id(tax_id: str | None) -> str | None:
    if not tax_id:
        return None
    return tax_id[:2] + "•" * (len(tax_id) - 6) + tax_id[-4:]
