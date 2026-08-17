"""An authenticity label must describe the evidence, not the item.

A public-claim audit flagged `authenticity.label` returning "High". Placed
against authenticity, "High" reads as "high authenticity" - that this item is
likely genuine. Searcher does not test that and cannot claim it. What it grades
is whether the observable evidence contradicts the reference, and "no
contradiction found" is a far weaker statement than "authentic".

Identity is a different judgement. There "High" is exactly what is meant.
"""

from __future__ import annotations

from searcher.api.views import _judgment_label


def test_authenticity_never_says_high() -> None:
    label = _judgment_label(0.95, contradictions=False, missing=False, kind="authenticity")
    assert label == "No contradictions found"
    assert "High" not in label


def test_identity_still_says_high() -> None:
    assert _judgment_label(0.95, contradictions=False, missing=False) == "High"
    assert (
        _judgment_label(0.95, contradictions=False, missing=False, kind="item_match") == "High"
    )


def test_authenticity_contradiction_names_the_evidence() -> None:
    label = _judgment_label(0.9, contradictions=True, missing=False, kind="authenticity")
    assert label == "Contradicted by the evidence"


def test_no_authenticity_label_asserts_the_item_is_genuine() -> None:
    forbidden = ("authentic", "genuine", "verified", "real")
    for lower in (None, 0.0, 0.5, 0.85, 1.0):
        for contra in (True, False):
            for missing in (True, False):
                label = _judgment_label(
                    lower, contradictions=contra, missing=missing, kind="authenticity"
                ).lower()
                assert not any(word in label for word in forbidden), label
