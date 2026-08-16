"""§29.3 prompt-injection policy. Extracted text is data, never an instruction."""

from __future__ import annotations

import re

_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.I),
    re.compile(r"mark\s+this\s+(as\s+)?authentic", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"do\s+not\s+follow\s+(your|the)\s+(rules|policy)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"act\s+as\s+(if|a|an)\b", re.I),
    re.compile(r"override\s+(policy|tools|goals)", re.I),
)


def looks_like_instruction(text: str) -> bool:
    compact = " ".join(text.split())
    return any(pattern.search(compact) for pattern in _INSTRUCTION_PATTERNS)


def treat_as_data(text: str) -> str:
    """Return the text unchanged. Callers must not act on it."""
    return text
