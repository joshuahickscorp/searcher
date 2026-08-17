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
    # Copy, when a seller qualifies it. Bare "copy" is left alone: a listing can
    # legitimately mention a copy of a receipt or a copyright notice.
    re.compile(r"\b(?:1st|first|super|high[\s-]?quality|best|exact|aaa)[\s-]*cop(?:y|ies)\b"),
    # "copy of the original" means a replica - unless what was copied is
    # paperwork, where it is provenance in the seller's favour.
    re.compile(
        r"\bcop(?:y|ies)\s+(?:of\s+)?(?:the\s+)?(?:original|retail|authentic)\b"
        r"(?!\s+(?:receipt|invoice|tag|tags|card|certificate|papers|box|documentation))"
    ),
    # Negated authenticity, however it is phrased.
    re.compile(r"\b(?:not|isn'?t|ain'?t|aint)\s+(?:the\s+)?(?:an?\s+)?"
               r"(?:authentic|genuine|real|orig(?:inal)?)\b"),
    re.compile(r"\bnot\s+the\s+real\s+(?:thing|deal|one|pair)\b"),
    # The same claim in other languages.
    re.compile(r"\breplika\b"),
    re.compile(r"\br[ée]plique\b"),
    re.compile(r"\bimitazione\b"),
    re.compile(rf"\bimitations?\b(?!\s+{_MATERIALS})"),
    # Factory and batch slang beyond the named batches.
    re.compile(r"\b(?:god|pk|ua|lc|og)\s*factory\b"),
    re.compile(r"\bfrom\s+the\s+factory\b"),
    re.compile(r"\b(?:ua|pk|lc|og|gd|hk|dt|lj|bk)\s+quality\b"),
    re.compile(r"\bbest\s+batch\b"),
    re.compile(r"\brepfam\b"),
    re.compile(r"\bsame\s+as\s+retail\b"),
    # One-to-one, spelled every way sellers spell it.
    re.compile(r"\b1\s*[/\-]\s*1\b"),
    re.compile(r"\bone\s+to\s+one\b"),
    re.compile(r"\bmirror\b"),
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


_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def normalize_for_replica(text: str) -> str:
    """NFKC-fold so fullwidth and compatibility forms match the same pattern.

    A listing reading "1：1" with a fullwidth colon is the same claim as "1:1";
    without this it was not detected and the candidate reached Real. Zero-width
    characters go too: "re\u200bplica" is the same word to a reader and a
    different string to a regex.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).casefold()
    return re.sub(r"\s+", " ", folded)


def _despaced(text: str) -> str:
    """The same text with every space removed.

    Sellers write "r e p l i c a" and "counter feit" precisely because a word
    list does not see them. Only unambiguous words are matched this way.
    """
    return re.sub(r"[\s._-]+", "", text)


_DESPACED_PATTERNS = (
    re.compile(r"replica"),
    re.compile(r"counterfeit"),
    re.compile(r"superfake"),
    re.compile(r"repfam"),
    re.compile(r"\breplika\b"),
)


def self_declared_replica(text: str | None) -> bool:
    if not text:
        return False
    folded = normalize_for_replica(text)
    if any(pattern.search(folded) for pattern in REPLICA_PATTERNS):
        return True
    squashed = _despaced(folded)
    return any(pattern.search(squashed) for pattern in _DESPACED_PATTERNS)
