"""Price, size, and currency parsing keep the original."""

from __future__ import annotations

from decimal import Decimal

from searcher.normalization.currency import parse_price
from searcher.normalization.size import parse_size


def test_price_keeps_original_and_parses_amount() -> None:
    parsed = parse_price("¥128,000", "JPY")
    assert parsed.original == "¥128,000"
    assert parsed.currency == "JPY"
    assert parsed.amount == Decimal("128000")


def test_price_does_not_overwrite_currency() -> None:
    parsed = parse_price("$1,200.50")
    assert parsed.currency == "USD"
    assert parsed.amount == Decimal("1200.50")
    assert parsed.original == "$1,200.50"


def test_size_keeps_marked_size() -> None:
    parsed = parse_size("US 8 / EU 41")
    assert parsed.original == "US 8 / EU 41"
    assert "US" in parsed.marked
    assert parsed.assumptions is not None


def test_jp_cm_size() -> None:
    parsed = parse_size("26.5cm")
    assert parsed.system == "JP_CM"
    assert parsed.original == "26.5cm"
