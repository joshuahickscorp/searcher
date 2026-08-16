"""Normalized text and OCR-term overlap. Listing text is untrusted data."""

from __future__ import annotations

import re
import unicodedata

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

# A listing that says it is not the genuine article, in any of the ways sellers
# actually say it. Matched against NFKC-normalised, casefolded text so fullwidth
# and width-variant forms cannot slip through.
#
# Bias: a missed replica is published as Real and is the expensive error, while a
# genuine listing wrongly called a replica is still shown, on the replica list,
# with its reason. So an ambiguous phrase belongs here. The exceptions are words
# that legitimately describe materials - faux and fake fur, leather, suede - which
# say nothing about whether the item is the one being searched for.
_MATERIALS = r"(?:fur|furs|leather|suede|shearling|pearl|pearls|flower|flowers|plants?)"

REPLICA_PATTERNS = (
    re.compile(r"\breplicas?\b"),
    re.compile(r"\breps?\b"),
    re.compile(r"\brepsneakers?\b"),
    re.compile(r"\b1\s*[:：]\s*1\b"),
    re.compile(r"\bmirror\s+(?:quality|batch)\b"),
    re.compile(r"\baaa\+?\s*(?:quality|batch)?\b"),
    re.compile(r"\bunauthorized\b"),
    re.compile(r"\bcounterfeit\b"),
    re.compile(r"\bnot\s+(?:authentic|genuine|real|original)\b"),
    re.compile(r"\breproduction\b"),
    re.compile(r"\bstimulant\b"),
    re.compile(r"\bsuper\s?fakes?\b"),
    # "fake" on its own, except where it describes a material.
    re.compile(rf"\bfakes?\b(?!\s+{_MATERIALS})"),
    re.compile(rf"\bfaux\b(?!\s+{_MATERIALS})"),
    re.compile(r"\bdupes?\b"),
    re.compile(r"\bhomage\b"),
    re.compile(r"\binspired\s+by\b"),
    re.compile(r"\bknock[\s-]?off\b"),
    re.compile(r"\bbootleg\b"),
    re.compile(r"\bclone\b"),
    # Factory and batch slang used by replica sellers.
    re.compile(r"\bpk\s*god\b"),
    re.compile(r"\b(?:ua|lc|og|gd|hk|dt|lj|bk)\s+batch\b"),
    re.compile(r"\bbatch\s+quality\b"),
    re.compile(r"\bfactory\s+(?:batch|quality|version)\b"),
    re.compile(r"\bretail\s+version\b"),
    # Japanese and Chinese sellers state it plainly.
    re.compile(r"レプリカ"),
    re.compile(r"スーパーコピー"),
    re.compile(r"コピー品"),
    re.compile(r"偽物"),
    re.compile(r"模造"),
    re.compile(r"復刻版"),
    re.compile(r"高仿"),
    re.compile(r"复刻"),
    re.compile(r"仿品"),
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


def normalize_for_replica(text: str) -> str:
    """NFKC-fold so fullwidth and compatibility forms match the same pattern.

    A listing reading "1：1" with a fullwidth colon is the same claim as "1:1";
    without this it was not detected and the candidate reached Real.
    """
    return unicodedata.normalize("NFKC", text).casefold()


def self_declared_replica(text: str | None) -> bool:
    if not text:
        return False
    folded = normalize_for_replica(text)
    return any(pattern.search(folded) for pattern in REPLICA_PATTERNS)
