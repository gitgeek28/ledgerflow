"""Exact decimal money handling. Floats are never used for currency."""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
ZERO = Decimal("0")
CURRENCY_DECIMALS = {"INR": 2, "USD": 2, "EUR": 2}

_AMOUNT_RE = re.compile(r"^-?\d+(\.\d+)?$")


def D(value) -> Decimal:
    """Construct a Decimal from str/int/Decimal. Floats are rejected to avoid binary rounding errors."""
    if isinstance(value, float):
        raise TypeError("Floats are not permitted for money; pass a string or Decimal")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q2(value: Decimal) -> Decimal:
    return D(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def q3(value: Decimal) -> Decimal:
    return D(value).quantize(THREE_PLACES, rounding=ROUND_HALF_UP)


def parse_amount(raw: str | None) -> Decimal | None:
    """Parse a printed amount such as 'Rs. 1,18,000.00', 'INR 59,000', '(1,200.50)'. Returns None if invalid."""
    if raw is None:
        return None
    s = raw.strip()
    negative = s.startswith("(") and s.endswith(")")
    s = re.sub(r"(?i)\b(inr|rs\.?|usd|eur)\b", "", s)
    s = s.replace("₹", "").replace(",", "").replace(" ", "").strip("()").strip()
    if s.endswith("-"):
        negative, s = True, s[:-1]
    if not _AMOUNT_RE.match(s):
        return None
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_quantity(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    s = raw.replace(",", "").strip()
    if not _AMOUNT_RE.match(s):
        return None
    return Decimal(s)


def pct_delta(actual: Decimal, expected: Decimal) -> Decimal | None:
    """Percentage variance of actual vs expected, rounded to 2dp. None when expected is zero."""
    if expected == ZERO:
        return None
    return ((actual - expected) / expected * Decimal(100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt(value: Decimal | None, currency: str | None = None) -> str | None:
    if value is None:
        return None
    s = f"{q2(value):,.2f}"
    return f"{currency} {s}" if currency else s
