"""Normalized text and OCR-term overlap. Listing text is untrusted data."""

from __future__ import annotations

import re

from searcher.reference.injection import looks_like_instruction

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "for",
        "to",
        "in",
        "on",
        "with",
        "by",
        "from",
        "this",
        "that",
        "new",
        "used",
        "sold",
        "size",
        "buy",
        "sale",
    }
)

REPLICA_PATTERNS = (
    re.compile(r"\breplicas?\b", re.I),
    re.compile(r"\breps?\b", re.I),
    re.compile(r"\b1\s*:\s*1\b"),
    re.compile(r"\bmirror\s+quality\b", re.I),
    re.compile(r"\baaa\s+quality\b", re.I),
    re.compile(r"\bunauthorized\b", re.I),
    re.compile(r"\bcounterfeit\b", re.I),
    re.compile(r"\bnot\s+authentic\b", re.I),
    re.compile(r"\breproduction\b", re.I),
    re.compile(r"\bstimulant\b", re.I),
    re.compile(r"\bfake\s+(shoes?|trainers?|sneakers?)\b", re.I),
)


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    # Instruction-like spans are data; they must not boost identity.
    kept = text
    if looks_like_instruction(text):
        kept = re.sub(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?[^.]*",
            " ",
            text,
            flags=re.I,
        )
        kept = re.sub(r"mark\s+this\s+(as\s+)?authentic[^.]*", " ", kept, flags=re.I)
    tokens = [tok for tok in _TOKEN.findall(kept.lower()) if tok not in _STOP and len(tok) > 1]
    expanded: list[str] = []
    for tok in tokens:
        expanded.append(tok)
        if len(tok) == 2 and tok.isdigit() and 0 <= int(tok) <= 30:
            expanded.append(f"20{tok}")
        if len(tok) == 4 and tok.startswith("20"):
            expanded.append(tok[2:])
    return expanded


def jaccard(a: list[str], b: list[str]) -> float:
    left, right = set(a), set(b)
    if not left and not right:
        return 0.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def containment(a: list[str], b: list[str]) -> float:
    """How much of the shorter set sits inside the longer one."""
    left, right = set(a), set(b)
    if not left or not right:
        return 0.0
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    return len(smaller & larger) / len(smaller)


def text_identity(query_terms: list[str], listing_terms: list[str]) -> float:
    jac = jaccard(query_terms, listing_terms)
    con = containment(query_terms, listing_terms)
    return max(0.0, min(1.0, 0.55 * jac + 0.45 * con))


def self_declared_replica(text: str | None) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in REPLICA_PATTERNS)
