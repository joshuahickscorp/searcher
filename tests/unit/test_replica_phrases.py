"""Every way a seller says "this is not the real thing" must route to replica.

A missed replica is published as Real, which is the expensive error and the one
the interface promises cannot happen. These phrases all reached Real before
commit; each is kept as a regression case.
"""

from __future__ import annotations

import pytest

from searcher.retrieval.text import self_declared_replica

# Observed in artifacts/redteam-invariant-attacks.json: all thirteen published
# as Real while the interface said a replica never can.
LEAKED = [
    "This is fake.",
    "スーパーコピー レプリカ",
    "Dior Homme GAT dupe",
    "Inspired by Dior Homme General Army Trainer",
    "Dior Homme GAT superfake",
    "Dior Homme GAT PK God factory",
    "Dior Homme GAT UA batch",
    "Dior Homme GAT 1：1",
    "not genuine",
    "Dior Homme GAT mirror batch",
    "Dior Homme GAT homage",
    "repsneaker quality",
    "Unauthorized replica 1:1 of the original trainer",
]

# Ordinary listings. "faux fur" and "fake leather" describe a material and say
# nothing about whether this is the item being searched for.
GENUINE = [
    "Dior Homme General Army Trainer",
    "Black wool coat with faux fur collar",
    "Vintage fake leather jacket",
    "Authentic Prada pumps size 38 1/2",
    "WILLY CHAVARRIA 無地 ロングスリーブカットソー",
    "Comme des Garcons SHIRT x Supreme loop collar shirt",
]


@pytest.mark.parametrize("text", LEAKED)
def test_seller_declaring_a_replica_is_detected(text: str) -> None:
    assert self_declared_replica(text) is True


@pytest.mark.parametrize("text", GENUINE)
def test_ordinary_listing_is_not_called_a_replica(text: str) -> None:
    assert self_declared_replica(text) is False


def test_fullwidth_and_case_are_folded_before_matching() -> None:
    assert self_declared_replica("ＲＥＰＬＩＣＡ") is True
    assert self_declared_replica("Mirror Quality") is True

# Found by an independent adversarial pass after the first thirteen were fixed:
# every one of these reached Possibly Real with perfect match scores. They are
# the same claim in other words - qualified copies, factory and batch slang,
# negated authenticity, other languages, and deliberate obfuscation with
# zero-width characters or spaced-out letters.
LEAKED_ROUND_TWO = [
    '1st copy',
    'first copy',
    'super copy',
    'super-copy',
    'god factory',
    'not the authentic piece',
    "isn't authentic",
    "ain't genuine",
    'not the real thing',
    'replika',
    'réplique',
    'imitazione',
    'imitation',
    're\u200bplica',
    'r e p l i c a',
    '1/1 pair',
    '1-1 quality',
    'one to one',
    'same as retail',
    'best batch',
    'repfam',
    'high quality copy',
    'mirror',
    'from the factory',
    'not orig',
    "this isn't the authentic pair",
    'counter feit',
    'super  copy',
    'UA quality',
    'PK factory',
]


@pytest.mark.parametrize("text", LEAKED_ROUND_TWO)
def test_second_round_of_seller_phrasings_is_detected(text: str) -> None:
    assert self_declared_replica(text) is True


def test_paperwork_copies_are_provenance_not_replicas() -> None:
    """"Copy of the original receipt" is evidence for the seller, not against."""
    assert self_declared_replica("Copy of the original receipt included") is False
    assert self_declared_replica("comes with copy of the original invoice") is False


# Round 4 found this: a single digit substitution was caught while two were not,
# because only one reading of "1" was tried and a word can mix readings.
OBFUSCATED = ["r3pl1ca", "rep11ca", "r3p1ica", "5uperfake", "fak3", "c0unterfeit"]

# Ordinary listings that contain digits and must not be dragged in with them.
DIGITS_BUT_ORDINARY = [
    "Nike Air Max 1 size 10",
    "Levi 501 jeans W32",
    "Model 111 watch",
    "Room 101 print",
]


@pytest.mark.parametrize("text", OBFUSCATED)
def test_digit_substitution_is_read_both_ways(text: str) -> None:
    assert self_declared_replica(text) is True


@pytest.mark.parametrize("text", DIGITS_BUT_ORDINARY)
def test_a_number_in_a_title_is_not_an_obfuscation(text: str) -> None:
    assert self_declared_replica(text) is False


def test_round_five_replica_attacks_are_detected() -> None:
    """Obfuscations that reached Real in the round-5 independent grade.

    Each of these published as Real at commit 4fae9f7. They are three distinct
    holes, not one: a Turkish dotless i that NFKC leaves alone because it is a
    letter in its own right; a hedge between "not" and the word it negates; and
    a separator inside a negating prefix. The last two were generalised to a
    separator class after my own attack found `un_authorized` and
    `not-authentic` still passing.
    """
    from searcher.retrieval.text import self_declared_replica

    attacks = (
        "replıca",
        "not 100% authentic",
        "un-authorized",
        "un_authorized",
        "un authorized",
        "not-authentic",
        "not fully authentic",
        "not entirely genuine",
        "not really legit",
        "r3plıca",
        "Replıca",
    )
    missed = [text for text in attacks if not self_declared_replica(text)]
    assert missed == [], f"replica language reached Real undetected: {missed}"


def test_legitimate_authenticity_language_is_not_a_replica_claim() -> None:
    """The negations above must not swallow a seller asserting authenticity."""
    from searcher.retrieval.text import self_declared_replica

    clean = (
        "100% authentic",
        "authentic Nike Air Max 1",
        "genuine leather",
        "authorized retailer",
        "fully authorized dealer",
        "real leather bag",
        "not a scratch on it",
        "Levi 501",
    )
    wrong = [text for text in clean if self_declared_replica(text)]
    assert wrong == [], f"legitimate listing text called a replica: {wrong}"


def test_round_six_replica_attacks_are_detected() -> None:
    """Obfuscations that reached Real in the round-6 independent grade.

    Both are the classes round 5 exposed, with different members: a Greek iota
    where Cyrillic and Turkish look-alikes had been added by hand, and a "non-"
    prefix where "un-" had been fixed. Extending a hand-written table one
    script at a time loses to an attacker reading the same Unicode charts, so
    the confusable set is now derived from Unicode names and the negating
    prefix is a class.

    `ΝOT AUTHENTIC` is the subtle one, found by attacking the repair rather
    than by the grader: a Greek capital nu imitates Latin N while a Greek small
    nu imitates v, so casefolding before folding turned it into
    "vot authentic" and the claim escaped.
    """
    from searcher.retrieval.text import self_declared_replica

    attacks = (
        "replιca",
        "non-authentic",
        "non authentic",
        "nonauthentic",
        "non-genuine",
        "non_original",
        "un-authorised",
        "non-authorised",
        "unauthorised",
        "ΝOT AUTHENTIC",
        "ΗIGH QUALITY REPLICA",
        "ΒOOTLEG",
    )
    missed = [text for text in attacks if not self_declared_replica(text)]
    assert missed == [], f"replica language reached Real undetected: {missed}"


def test_words_that_merely_begin_with_non_are_not_replica_claims() -> None:
    """The generalised prefix must not swallow ordinary listing language."""
    from searcher.retrieval.text import self_declared_replica

    clean = (
        "NON-SMOKING HOME",
        "Norse Projects jacket",
        "Novesta sneakers",
        "authorised dealer",
        "authorized retailer",
        "no returns",
        "none left in this size",
    )
    wrong = [text for text in clean if self_declared_replica(text)]
    assert wrong == [], f"ordinary listing text called a replica: {wrong}"


def test_contraction_and_unicode_dash_replica_forms_are_detected() -> None:
    """The forms round 6 named in its remediation list.

    Two more members of two classes already fixed. The hedge pattern accepted
    only the bare word "not", so every contraction escaped it - "isn't 100%
    authentic" reads identically to a buyer. And the separator class held the
    ASCII hyphen but no Unicode dash, so "non-authentic" was caught while
    "non–authentic" with an en-dash was not.

    Both are now written once as classes and reused: one separator class
    covering the Unicode dash range, one negation class covering the
    contractions.
    """
    from searcher.retrieval.text import self_declared_replica

    attacks = (
        "isn't 100% authentic",
        "isnt 100% authentic",
        "isn't fully authentic",
        "ain't 100% genuine",
        "non\u2013authentic",
        "un\u2013authorized",
        "not\u2014authentic",
        "wasn't entirely genuine",
    )
    missed = [text for text in attacks if not self_declared_replica(text)]
    assert missed == [], f"replica language reached Real undetected: {missed}"


def test_ordinary_contractions_are_not_replica_claims() -> None:
    from searcher.retrieval.text import self_declared_replica

    clean = ("isn't damaged", "ain't cheap", "isn't available", "not a scratch on it")
    wrong = [text for text in clean if self_declared_replica(text)]
    assert wrong == [], f"ordinary listing text called a replica: {wrong}"


# Round 7 found four members of a class four earlier rounds had each patched by
# name. The characters were different every time; the trick never was.
ROUND_7_ESCAPES = ["re–plica", "re/plica", "r3pl!ca", "inauthentic"]

SEPARATOR_FAMILY = [
    "re–plica", "re—plica", "re/plica", "re\\plica", "re_plica",
    "r.e.p.l.i.c.a", "re*plica", "re+plica", "re~plica", "re=plica",
]

LETTER_SUBSTITUTE_FAMILY = ["r3pl!ca", "rep|ica", "re!plica", "r3pl1ca", "rep1ica", "r3plica"]

NEGATING_PREFIX_FAMILY = [
    "inauthentic", "ingenuine", "unauthentic", "un-authentic",
    "non authentic", "non-genuine", "unoriginal",
]

# Ordinary listing text that must never be read as a replica claim. Several of
# these are one character away from a pattern above.
INNOCENT = [
    "Air Max 1", "Levi 501", "Model 111", "Room 101", "size 8!", "great deal!",
    "in original box", "comes in original packaging", "in genuine leather",
    "in excellent condition", "authentic",
]

# Deliberately not in INNOCENT: "1-1 stitching detail". "1:1" is standard
# replica vocabulary and the hyphen form normalises onto it. Flagging it is the
# right call rather than a defect to fix, because the two errors do not cost the
# same: a missed replica claim can send a buyer to a counterfeit, while a
# false positive hides one listing. The detector should lean toward hiding.


@pytest.mark.parametrize("text", ROUND_7_ESCAPES)
def test_round_7_escapes_are_closed(text: str) -> None:
    assert self_declared_replica(text), f"{text!r} still publishes as Real"


@pytest.mark.parametrize("text", SEPARATOR_FAMILY)
def test_any_separator_inside_the_word_is_seen(text: str) -> None:
    """Naming separators one at a time is how this class escaped five rounds."""
    assert self_declared_replica(text), text


@pytest.mark.parametrize("text", LETTER_SUBSTITUTE_FAMILY)
def test_punctuation_standing_in_for_a_letter_is_read_as_one(text: str) -> None:
    assert self_declared_replica(text), text


@pytest.mark.parametrize("text", NEGATING_PREFIX_FAMILY)
def test_a_negating_prefix_is_a_negation(text: str) -> None:
    assert self_declared_replica(text), text


@pytest.mark.parametrize("text", INNOCENT)
def test_ordinary_listing_text_is_not_a_replica_claim(text: str) -> None:
    assert not self_declared_replica(text), f"{text!r} was wrongly called a replica claim"
