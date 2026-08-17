"""Ask for views the thing actually has.

Observed on a live campaign for a long-sleeve T-shirt: the engine recorded
missing_reference_views as sole, label and heel. A garment has no sole and no
heel, so those views could never arrive, and the part evidence they gate could
never arrive either — while parts carry 0.30 of the item-match combination.
That is why the score could not rise no matter how many photographs were given.
"""

from __future__ import annotations

from searcher.reference.gaps import _priority_for


def _views(category: str | None) -> set[str]:
    return {view.value for view, _request, _impact in _priority_for(category)}


def test_a_garment_is_never_asked_for_a_sole_or_a_heel() -> None:
    asked = _views("garment")
    assert "sole" not in asked
    assert "heel" not in asked
    assert {"front", "rear", "label", "detail"} <= asked


def test_footwear_keeps_the_views_that_identify_a_shoe() -> None:
    asked = _views("footwear")
    assert {"sole", "heel", "label", "lateral"} <= asked


def test_an_unknown_category_is_not_treated_as_footwear() -> None:
    # Defaulting to shoes is what produced the shirt-with-a-sole request.
    assert "sole" not in _views(None)
    assert "sole" not in _views("bag")
