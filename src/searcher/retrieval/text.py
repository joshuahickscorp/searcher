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
               r"(?:authentic|genuine|real|legit|orig(?:inal)?)\b"),
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
    re.compile(r"\b(?:best|god|retail|top|clean)\s+batch\b"),
    re.compile(r"\bdups?\b"),
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

# Cyrillic and Greek letters that render as Latin ones. A seller writing
# "repliсa" with a Cyrillic es is making the same claim to a reader and a
# different string to a matcher.
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y",
    "і": "i", "ѕ": "s", "ԁ": "d", "ӏ": "l", "һ": "h", "ν": "v", "ο": "o",
    "α": "a", "ρ": "p", "τ": "t", "ϲ": "c", "ｅ": "e",
})

# Digit-for-letter substitutions, applied only to the despaced pass below so a
# meaningful "1:1" is never mangled.
_LEET_BASE: dict[str, str | int | None] = {
    "0": "o", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s", "7": "t",
}
_LEET_L = str.maketrans({**_LEET_BASE, "1": "l"})
_LEET_I = str.maketrans({**_LEET_BASE, "1": "i"})
# Kept for the despaced pass, which only needs one reading.
_LEET = _LEET_L

_AMBIGUOUS = "1"
_MAX_AMBIGUOUS = 3


def _word_variants(word: str) -> list[str]:
    """Readings of one word where digits may stand in for letters."""
    from itertools import product

    if _AMBIGUOUS not in word:
        return [word]
    if word.count(_AMBIGUOUS) > _MAX_AMBIGUOUS:
        return [word.replace(_AMBIGUOUS, "l"), word.replace(_AMBIGUOUS, "i")]
    out: list[str] = []
    slots = word.count(_AMBIGUOUS)
    for choice in product("li", repeat=slots):
        chars, index = [], 0
        for ch in word:
            if ch == _AMBIGUOUS:
                chars.append(choice[index])
                index += 1
            else:
                chars.append(ch)
        out.append("".join(chars))
    return out


def _leet_variants(folded: str) -> list[str]:
    """Readings of a string where digits may stand in for letters.

    Enumerated per word rather than across the whole text. The bound exists to
    stop a long run of ambiguous digits becoming expensive, but counting them
    document-wide made detection depend on how much text came with the word:
    "rep11ca" alone carries two and is read correctly, while the same title
    joined to its own description carries four, blew the bound, and fell back
    to the two uniform readings - neither of which is "replica". Publication
    joins title and description, so every replica title was doubled and the
    effective bound was half of what it looked like. A word is what the
    substitution is applied to, so a word is what gets enumerated.
    """
    base = folded.translate(str.maketrans(_LEET_BASE))
    if _AMBIGUOUS not in base:
        return [base] if base != folded else []
    per_word = [_word_variants(word) for word in base.split(" ")]
    out: list[str] = []
    # Each word's readings, substituted back one word at a time. The whole
    # cross-product across words is not needed: the patterns match a single
    # replica term, so it is enough that each word can be read on its own.
    for position, readings in enumerate(per_word):
        for reading in readings:
            words = [choices[0] for choices in per_word]
            words[position] = reading
            out.append(" ".join(words))
    return out


def normalize_for_replica(text: str) -> str:
    """NFKC-fold so fullwidth and compatibility forms match the same pattern.

    A listing reading "1：1" with a fullwidth colon is the same claim as "1:1";
    without this it was not detected and the candidate reached Real. Zero-width
    characters go too: "re\u200bplica" is the same word to a reader and a
    different string to a regex.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).casefold()
    folded = folded.translate(_HOMOGLYPHS)
    return re.sub(r"\s+", " ", folded)


def _despaced(text: str) -> str:
    """The same text with every space removed.

    Sellers write "r e p l i c a" and "counter feit" precisely because a word
    list does not see them. Only unambiguous words are matched this way.
    """
    return re.sub(r"[\s._-]+", "", text).translate(_LEET)


_DESPACED_PATTERNS = (
    re.compile(r"replica"),
    re.compile(r"counterfeit"),
    re.compile(r"superfake"),
    re.compile(r"repfam"),
    re.compile(r"\breplika\b"),
)

# Letters a digit can stand for, written into the pattern instead of enumerated
# around it. Enumerating readings is exponential in the number of ambiguous
# digits, so it needed a bound, and the bound was a silent miss: "rep11ca"
# joined to its own description carries four of them, blew the bound, and fell
# back to two uniform readings - neither of which spells the word. A character
# class has no such limit and does not care how long the text is.
_DIGIT_FOR_LETTER = {"l": "[l1]", "i": "[i1]", "e": "[e3]", "o": "[o0]", "a": "[a4]", "s": "[s5]"}


def _tolerant(word: str) -> re.Pattern[str]:
    return re.compile("".join(_DIGIT_FOR_LETTER.get(ch, re.escape(ch)) for ch in word))


_DESPACED_TOLERANT = tuple(
    _tolerant(word) for word in ("replica", "counterfeit", "superfake", "repfam", "replika")
)


def self_declared_replica(text: str | None) -> bool:
    if not text:
        return False
    folded = normalize_for_replica(text)
    if any(pattern.search(folded) for pattern in REPLICA_PATTERNS):
        return True
    # Digit-for-letter substitution, on the spaced text as well as the squashed
    # one. Only the despaced pass mapped it before, so a single substitution was
    # caught while "r3pl1ca" - two of them - published as Possibly Real.
    # A digit can stand for more than one letter, and a word can mix readings:
    # "r3pl1ca" is replica only if 1 reads as i, while "rep11ca" needs one l and
    # one i. Enumerate the readings of the ambiguous digit, bounded so a long
    # string of them cannot become expensive.
    for variant in _leet_variants(folded):
        if any(pattern.search(variant) for pattern in REPLICA_PATTERNS):
            return True
    squashed = _despaced(folded)
    if any(pattern.search(squashed) for pattern in _DESPACED_PATTERNS):
        return True
    # The obfuscations compose. Spacing a word out and substituting digits into
    # it are each handled above, but "r e p 1 1 c a" is both at once: spacing
    # puts every character in its own word so the per-word pass sees no word to
    # read, and _despaced resolves the ambiguous digit to l on its way through,
    # so "replica" was never among the readings tried. Despace without deciding
    # what the digit means, then read it both ways.
    bare = re.sub(r"[\s._-]+", "", folded)
    return any(pattern.search(bare) for pattern in _DESPACED_TOLERANT)
