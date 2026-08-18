"""A content digest is not proof this campaign holds the bytes.

`_download_listing_image` skipped any image that already had a `content_digest`.
That holds for a candidate this campaign discovered and downloaded. It does not
hold for one hydrated from the warm index: hydration copies the digest out of
the stored payload while the bytes live in whichever campaign first indexed
them.

Measured on the known-item campaign before this change: the target candidate
carried five images and zero retrievable bytes, reached broad retrieval with no
pixels to compare, scored nothing visually, and was cut by the fine-compare cap
of eight before any judgment ran - which is why it appeared neither in a public
tab nor among the hidden.
"""

from __future__ import annotations

from typing import Any

from searcher.campaigns.orchestrator import CampaignOrchestrator


class _Store:
    def __init__(self, present: set[str]) -> None:
        self.present = present

    def get(self, digest: str, campaign_id: str | None = None) -> bytes:
        if digest in self.present:
            return b"image-bytes"
        raise KeyError(digest)


class _Controller:
    def __init__(self, present: set[str]) -> None:
        self.store = _Store(present)


def _orch(present: set[str]) -> Any:
    orch = CampaignOrchestrator.__new__(CampaignOrchestrator)
    orch.controller = _Controller(present)  # type: ignore[assignment]
    return orch


def test_a_digest_whose_bytes_are_present_counts_as_held() -> None:
    assert _orch({"abc"})._bytes_present("s", "abc") is True


def test_a_digest_whose_bytes_are_absent_does_not() -> None:
    """The index-hydrated case: the digest travelled, the bytes did not."""
    assert _orch(set())._bytes_present("s", "abc") is False


def test_a_store_that_raises_is_treated_as_absent() -> None:
    """Failing closed here means a redundant download, not a pixel-less candidate."""

    class _Angry:
        def get(self, digest: str, campaign_id: str | None = None) -> bytes:
            raise RuntimeError("store unavailable")

    orch = CampaignOrchestrator.__new__(CampaignOrchestrator)
    orch.controller = type("C", (), {"store": _Angry()})()  # type: ignore[assignment]
    assert orch._bytes_present("s", "abc") is False


def test_the_downloader_consults_possession_not_just_the_digest() -> None:
    import inspect

    source = inspect.getsource(CampaignOrchestrator._download_listing_image)
    assert "_bytes_present" in source, (
        "a digest alone must not short-circuit the download, or an index-hydrated "
        "candidate reaches matching with no pixels"
    )
