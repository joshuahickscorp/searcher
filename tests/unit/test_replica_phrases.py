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
