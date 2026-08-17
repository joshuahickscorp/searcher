"""The correspondence detector must say which one answered, and when it is noise.

opencv is optional and was absent for this project's whole life, so every
campaign ran on the BRIEF fallback and nothing reported it. Measured on
fixtures/user_snapshots: ORB separates an object from another object with TPR
1.000 at FPR 0.000, while the fallback's inlier counts for the same object and
for different objects overlap completely. A signal that carries no information
must not be presented as if it does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from searcher.matching.correspondence import correspond_pair
from searcher.matching.features import opencv_available

SNAPSHOTS = Path("fixtures/user_snapshots")
LISTINGS = Path("fixtures/known_item_kind/images")
DEGRADED = "degraded_signal:no_opencv_correspondence_is_noise"


def _pair() -> tuple[bytes, bytes]:
    row = json.loads((SNAPSHOTS / "MANIFEST.json").read_text())["items"][0]
    return (
        (SNAPSHOTS / row["snapshot"]).read_bytes(),
        (LISTINGS / row["derived_from"]).read_bytes(),
    )


def test_the_detector_names_itself() -> None:
    snapshot, listing = _pair()
    result = correspond_pair(snapshot, listing)
    assert result.method in {"orb", "brief_fallback"}
    assert result.method == ("orb" if opencv_available() else "brief_fallback")


def test_the_fallback_declares_that_it_is_noise() -> None:
    snapshot, listing = _pair()
    result = correspond_pair(snapshot, listing)
    if opencv_available():
        assert DEGRADED not in result.notes
    else:
        assert DEGRADED in result.notes


@pytest.mark.skipif(not opencv_available(), reason="opencv is the correspondence extra")
def test_a_photograph_of_the_object_corresponds_to_its_own_listing() -> None:
    rows = json.loads((SNAPSHOTS / "MANIFEST.json").read_text())["items"]
    own = correspond_pair(
        (SNAPSHOTS / rows[0]["snapshot"]).read_bytes(),
        (LISTINGS / rows[0]["derived_from"]).read_bytes(),
    )
    other = correspond_pair(
        (SNAPSHOTS / rows[0]["snapshot"]).read_bytes(),
        (LISTINGS / rows[1]["derived_from"]).read_bytes(),
    )
    assert own.inlier_count >= 10
    assert other.inlier_count < 10
    assert own.inlier_count > other.inlier_count
