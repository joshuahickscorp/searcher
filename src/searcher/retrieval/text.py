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

# Separators a seller can put inside a negating phrase. The ASCII hyphen was
# covered and the en-dash was not, so "non–authentic" published as Real after
# "non-authentic" had been fixed. Written once and reused.
_SEP = r"[\s._\-\u2010-\u2015\u2212]"
# Ways of saying "is not", including contractions the hedge pattern missed.
_NEG = r"(?:not|isn'?t|ain'?t|aint|wasn'?t|aren'?t|isnt|arent)"
# Hedges that sit between the negation and the word it negates.
_HEDGE = (
    r"(?:\d{1,3}\s*%|100|fully|entirely|completely|totally|quite|exactly|"
    r"truly|really|strictly|guaranteed)"
)


REPLICA_PATTERNS = (
    re.compile(r"\breplicas?\b"),
    re.compile(r"\breps?\b"),
    re.compile(r"\brepsneakers?\b"),
    re.compile(r"\b1\s*[:：]\s*1\b"),
    re.compile(r"\bmirror\s+(?:quality|batch)\b"),
    re.compile(r"\baaa\+?\s*(?:quality|batch)?\b"),
    # Sellers separate the negating prefix however they like, so the separator
    # is a class rather than a list of spellings: un-authorized, un authorized,
    # un_authorized.
    # The negating prefix is a class. "un-authorized" was fixed and
    # "non-authentic" then published as Real, which is the same defect with a
    # different prefix.
    re.compile(rf"\b(?:un|non){_SEP}?authori[sz]ed\b"),
    re.compile(rf"\b(?:un|non){_SEP}?authentic\b"),
    re.compile(rf"\b(?:un|non){_SEP}?genuine\b"),
    re.compile(rf"\b(?:un|non){_SEP}?original\b"),
    re.compile(rf"\b(?:un|non){_SEP}?authentic\b"),
    # The "in-" prefix takes no separator, deliberately. "inauthentic" is one
    # word and is the claim; "in original box" is three words and is the
    # opposite claim, extremely common, and would be caught by the same pattern
    # if a separator were allowed. The prefix is also not applied to "original"
    # for that reason - "inoriginal" is not a word, so there is nothing to gain
    # and a very common phrase to lose.
    re.compile(r"\bin(?:authentic|genuine)\b"),
    re.compile(r"\bcounterfeit\b"),
    # "not 100% authentic" and "not fully genuine" are the same claim as "not
    # authentic". Requiring the words to be adjacent missed every hedged form.
    re.compile(
        rf"\b{_NEG}{_SEP}+(?:{_HEDGE}{_SEP}+)?"
        rf"(?:authentic|genuine|real|original|legit)\b"
    ),
    # Replica marketplaces and the slang sellers use to name them. A listing
    # that says where it came from is declaring what it is, and none of these
    # words is a morphological variant of "replica" - the earlier work closed
    # separators, letter substitutes and negating prefixes, which is a different
    # class entirely. An independent grade found these still publishing as Real
    # after that work was described as closing the class.
    #
    # Each is a proper noun or a fixed phrase in this trade, not an ordinary
    # English word: "yupoo" and "weidian" are hosting and marketplace names,
    # "LJR" and "godtier" name replica tiers, "batch" and "factory" are only
    # quality grades when attached to goods. `_SEP` lets the spaced, hyphenated
    # and dashed forms match without admitting the bare words.
    re.compile(r"\b(?:dhgate|weidian|yupoo|pandabuy|taobao)\b"),
    re.compile(r"\bljr\b"),
    re.compile(r"\bgod{_SEP}?tier\b".replace("{_SEP}", _SEP)),
    re.compile(r"\blook{_SEP}?alike\b".replace("{_SEP}", _SEP)),
    re.compile(rf"\bfactory{_SEP}+(?:pair|batch|shoes?|version)\b"),
    re.compile(rf"\b(?:og|ok|lc|uc|gp|ps){_SEP}+batch\b"),
    re.compile(rf"\bbatch{_SEP}+(?:shoes?|pair|version|quality)\b"),
    re.compile(rf"\b(?:taobao|weidian|1688){_SEP}+agent\b"),
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
    # Latin-extended look-alikes. "replıca" with a Turkish dotless i published
    # as Real: NFKC leaves U+0131 alone because it is a letter in its own
    # right, so nothing folded it and no pattern matched.
    "ı": "i", "İ": "i", "ł": "l", "ø": "o", "đ": "d", "ƒ": "f", "ĸ": "k",
    "ѐ": "e", "ё": "e", "ї": "i", "ǐ": "i", "ì": "i", "í": "i", "î": "i",
    # Greek. "replιca" with a Greek iota published as Real after the Cyrillic
    # and Latin-extended sets were added one script at a time. Adding scripts
    # by hand is how this keeps recurring, so the confusable set below is
    # derived from Unicode names instead of extended again by hand.
    "ι": "i", "ε": "e", "κ": "k", "μ": "u", "σ": "o", "χ": "x", "γ": "y",
    "η": "n", "θ": "o", "λ": "l",
})


def _derived_confusables() -> dict[int, str]:
    """Letters from other scripts whose Unicode name says which Latin letter
    they imitate.

    Three separate Real leaks came from extending a hand-written homoglyph
    table one script at a time: Cyrillic, then Turkish dotless i, then Greek
    iota. Enumerating scripts by hand loses to an attacker who reads the same
    Unicode charts. This walks the letters instead and keeps the ones whose
    name marks them a look-alike of a single Latin letter.
    """
    import unicodedata

    table: dict[int, str] = {}
    for block_start, block_end in ((0x0370, 0x03FF), (0x0400, 0x04FF), (0x0100, 0x024F)):
        for code in range(block_start, block_end + 1):
            ch = chr(code)
            if not ch.isalpha():
                continue
            try:
                name = unicodedata.name(ch)
            except ValueError:
                continue
            decomposed = unicodedata.normalize("NFKD", ch)
            base = "".join(c for c in decomposed if not unicodedata.combining(c))
            if len(base) == 1 and base.isascii() and base.isalpha():
                table[code] = base.lower()
                continue
            # "GREEK SMALL LETTER IOTA" and friends: take the final word when it
            # names a single Latin letter directly.
            words = name.split()
            if words and len(words[-1]) == 1 and words[-1].isascii() and words[-1].isalpha():
                table[code] = words[-1].lower()
    return table


_HOMOGLYPHS = {**_derived_confusables(), **_HOMOGLYPHS}

# Digit-for-letter substitutions, applied only to the despaced pass below so a
# meaningful "1:1" is never mangled.
_LEET_BASE: dict[str, str | int | None] = {
    "0": "o", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s", "7": "t",
}
_LEET_L = str.maketrans({**_LEET_BASE, "1": "l"})
_LEET_I = str.maketrans({**_LEET_BASE, "1": "i"})
# Kept for the despaced pass, which only needs one reading.
_LEET = _LEET_L

# Characters that stand in for a letter rather than separating two of them.
# "1" reads as l or i; so do "!" and "|", and "r3pl!ca" escaped five rounds
# because the separator pass stripped the "!" and destroyed the word instead of
# reading it. A character can substitute for a letter or divide two letters, and
# which one it is cannot be decided by the character alone - so both readings
# are tried.
_AMBIGUOUS_CHARS = "1!|"
_AMBIGUOUS = "1"
_MAX_AMBIGUOUS = 3


def _word_variants(word: str) -> list[str]:
    """Readings of one word where digits may stand in for letters."""
    from itertools import product

    slots = sum(word.count(ch) for ch in _AMBIGUOUS_CHARS)
    if not slots:
        return [word]
    if slots > _MAX_AMBIGUOUS:
        table_l = str.maketrans(dict.fromkeys(_AMBIGUOUS_CHARS, "l"))
        table_i = str.maketrans(dict.fromkeys(_AMBIGUOUS_CHARS, "i"))
        return [word.translate(table_l), word.translate(table_i)]
    out: list[str] = []
    for choice in product("li", repeat=slots):
        chars, index = [], 0
        for ch in word:
            if ch in _AMBIGUOUS_CHARS:
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
    if not any(ch in base for ch in _AMBIGUOUS_CHARS):
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


# Confusables whose Latin look-alike differs between cases. Greek capital nu
# reads as N and Greek small nu reads as v; one table cannot hold both once the
# text has been casefolded, so these are applied before the fold.
_CASED_HOMOGLYPHS = str.maketrans({
    "\u039d": "N", "\u0392": "B", "\u0397": "H", "\u03a1": "P", "\u03a4": "T",
    "\u03a5": "Y", "\u03a7": "X", "\u039c": "M", "\u039a": "K", "\u0399": "I",
    "\u0396": "Z", "\u0395": "E", "\u039f": "O", "\u0391": "A",
})


def normalize_for_replica(text: str) -> str:
    """NFKC-fold so fullwidth and compatibility forms match the same pattern.

    A listing reading "1：1" with a fullwidth colon is the same claim as "1:1";
    without this it was not detected and the candidate reached Real. Zero-width
    characters go too: "re\u200bplica" is the same word to a reader and a
    different string to a regex.
    """
    normalized = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    # Case-sensitive confusables first. A Greek capital nu imitates Latin N
    # while a Greek small nu imitates v, so casefolding before folding turns
    # "ΝOT AUTHENTIC" into "vot authentic" and the claim escapes. Fold the
    # letters whose look-alike depends on case while the case still exists.
    normalized = normalized.translate(_CASED_HOMOGLYPHS)
    folded = normalized.casefold().translate(_HOMOGLYPHS)
    return re.sub(r"\s+", " ", folded)


def _despaced(text: str) -> str:
    """The same text with every space removed.

    Sellers write "r e p l i c a" and "counter feit" precisely because a word
    list does not see them. Only unambiguous words are matched this way.

    Every non-alphanumeric run is a separator here, not just space, dot,
    underscore and hyphen. Restricting it to those four let the same trick
    through under a different character: "re-plica" was caught while "re–plica"
    with an en dash, "re/plica" with a slash and "r3pl!ca" with an exclamation
    all published as Real. Naming the characters one at a time is how this class
    has escaped five review rounds; naming the complement closes it.
    """
    return re.sub(r"[^0-9a-z]+", "", text).translate(_LEET)


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
