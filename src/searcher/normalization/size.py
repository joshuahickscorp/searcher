"""§16.2 size parsing. Marked size stays prominent; conversions are annotated."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EU = re.compile(r"\b(?:EU|IT|FR|IT)\s*[-.]?\s*(\d{2}(?:\.5)?)\b", re.I)
_US = re.compile(r"\bUS\s*[-.]?\s*(\d{1,2}(?:\.5)?)\b", re.I)
_UK = re.compile(r"\bUK\s*[-.]?\s*(\d{1,2}(?:\.5)?)\b", re.I)
_CM = re.compile(r"\b(\d{2}(?:\.\d)?)\s*cm\b", re.I)
_MM = re.compile(r"\b(\d{3})\b")
_LETTER = re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|XXXL)\b", re.I)
_JP_NUM = re.compile(r"\bサイズ\s*([0-9]+|[SMLX]+)\b", re.I)


@dataclass(frozen=True, slots=True)
class ParsedSize:
    original: str
    marked: str
    system: str | None
    converted: str | None
    assumptions: str | None


def parse_size(original: str | None) -> ParsedSize:
    raw_original = original if original is not None else ""
    text = raw_original.strip()
    if not text:
        return ParsedSize(raw_original, raw_original, None, None, None)
    ordered: list[tuple[int, ParsedSize]] = []
    match = _US.search(text)
    if match:
        us = float(match.group(1))
        ordered.append(
            (
                match.start(),
                ParsedSize(
                    raw_original,
                    match.group(0),
                    "US",
                    f"EU {round(us + 33)}",
                    "approx US men's +33 = EU",
                ),
            )
        )
    match = _EU.search(text)
    if match:
        ordered.append((match.start(), ParsedSize(raw_original, match.group(0), "EU", None, None)))
    match = _UK.search(text)
    if match:
        uk = float(match.group(1))
        ordered.append(
            (
                match.start(),
                ParsedSize(
                    raw_original,
                    match.group(0),
                    "UK",
                    f"EU {round(uk + 34)}",
                    "approx UK men's +34 = EU",
                ),
            )
        )
    if ordered:
        ordered.sort(key=lambda item: item[0])
        return ordered[0][1]
    match = _CM.search(text)
    if match:
        return ParsedSize(raw_original, match.group(0), "JP_CM", None, None)
    match = _JP_NUM.search(text)
    if match:
        return ParsedSize(raw_original, match.group(0), "JP", None, None)
    match = _LETTER.search(text)
    if match:
        return ParsedSize(raw_original, match.group(1).upper(), "ALPHA", None, None)
    mm = _MM.search(text)
    if mm and "사이즈" in text:
        return ParsedSize(raw_original, mm.group(0), "KR_MM", None, None)
    return ParsedSize(raw_original, text, None, None, None)
