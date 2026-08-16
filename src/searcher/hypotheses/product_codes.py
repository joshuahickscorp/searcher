"""§12.4 product-code promotion. Size codes stay size codes."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SIZE_EXACT = re.compile(
    r"^(?:"
    r"eu\s*([3-5]\d(?:\.\d)?)|"
    r"us\s*([4-9]|1[0-6])(?:\.\d)?|"
    r"uk\s*([3-9]|1[0-5])(?:\.\d)?|"
    r"([3-5]\d(?:\.\d)?)|"
    r"(2[2-9](?:\.\d)?|3[0-2](?:\.\d)?)\s*cm|"
    r"(2[2-9]\d|3\d{2})\s*mm"
    r")$",
    re.I,
)
_PUNCT = re.compile(r"[\s\-\._/]+")


@dataclass(frozen=True, slots=True)
class CodeReading:
    raw: str
    normalized: str
    is_size: bool
    promotable: bool
    reason: str


def normalize_product_code(raw: str) -> str:
    return _PUNCT.sub("", raw).upper()


def is_size_code(raw: str) -> bool:
    compact = re.sub(r"\s+", " ", raw.strip().lower())
    if _SIZE_EXACT.match(compact.replace(" ", "")):
        return True
    if _SIZE_EXACT.match(compact):
        return True
    # Bare two-digit 35–50 is a size unless mixed with letters.
    return bool(re.fullmatch(r"[3-5]\d", compact))


def assess_code(
    raw: str,
    *,
    region_level_ocr: bool,
    structured_source: bool,
    consistent_across_candidates: bool,
    alternative_readings: list[str] | None = None,
) -> CodeReading:
    del alternative_readings
    normalized = normalize_product_code(raw)
    if not normalized:
        return CodeReading(raw, "", False, False, "empty")
    if is_size_code(raw) or is_size_code(normalized):
        return CodeReading(raw, normalized, True, False, "size_code")
    if not (region_level_ocr or structured_source):
        return CodeReading(raw, normalized, False, False, "needs_region_or_structured_source")
    if not consistent_across_candidates and not region_level_ocr:
        return CodeReading(raw, normalized, False, False, "inconsistent")
    if len(normalized) < 4:
        return CodeReading(raw, normalized, False, False, "too_short")
    return CodeReading(raw, normalized, False, True, "ok")
