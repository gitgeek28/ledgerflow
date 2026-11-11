"""Masking for sensitive values before they are persisted in evidence, events or logs."""
import re

LONG_DIGITS = re.compile(r"\b(\d{8,20})\b")


def mask_digits(text: str | None) -> str | None:
    """Mask contiguous digit runs of 8+ (bank accounts, phone numbers) keeping the last four."""
    if text is None:
        return None
    return LONG_DIGITS.sub(lambda m: "••••" + m.group(1)[-4:], text)
