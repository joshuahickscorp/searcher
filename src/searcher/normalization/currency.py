"""§16.3 currency. Original amount and code are never overwritten."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "円": "JPY",
    "₩": "KRW",
    "₹": "INR",
}
_CODE = re.compile(r"\b(USD|EUR|GBP|JPY|KRW|CNY|AUD|CAD|CHF|SEK|NOK|DKK|HKD|TWD|SGD)\b", re.I)
_AMOUNT = re.compile(
    r"(?<!\w)(?:USD|EUR|GBP|JPY|KRW|CNY|\$|€|£|¥|₩)?\s*"
    r"([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{1,2})|[0-9]+(?:[.,][0-9]{1,2})?)"
)


@dataclass(frozen=True, slots=True)
class ParsedPrice:
    original: str
    amount: Decimal | None
    currency: str | None


def parse_price(original: str | None, currency_hint: str | None = None) -> ParsedPrice:
    text = (original or "").strip()
    if not text and not currency_hint:
        return ParsedPrice("", None, None)
    currency = None
    if currency_hint:
        currency = currency_hint.upper()
    else:
        for symbol, code in _SYMBOLS.items():
            if symbol in text:
                currency = code
                break
        if currency is None:
            match = _CODE.search(text)
            if match:
                currency = match.group(1).upper()
    amount = None
    found = _AMOUNT.search(text)
    if found:
        raw = found.group(1)
        if currency in {"JPY", "KRW", "CNY"} or "¥" in text or "円" in text or "₩" in text:
            digits = re.sub(r"[^\d]", "", text)
            raw = digits or raw.replace(",", "").replace(".", "")
        elif "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif raw.count(",") == 1 and len(raw.split(",")[1]) in {1, 2}:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            amount = None
    return ParsedPrice(text or (currency_hint or ""), amount, currency)
