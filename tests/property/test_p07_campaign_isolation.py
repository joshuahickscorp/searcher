"""Property 7: one campaign cannot read another campaign's private artifacts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st
from pytest import raises

from searcher.core.errors import CrossCampaignAccessError
from searcher.evidence.content_store import ContentStore


@given(st.binary(min_size=1, max_size=64), st.text(min_size=1, max_size=8, alphabet="abcdef"))
def test_one_campaign_cannot_read_another_private_artifact(payload: bytes, name: str) -> None:
    with TemporaryDirectory() as raw:
        store = ContentStore(Path(raw), disk_margin_bytes=1)
        store.put_private("campaign-a", name, payload)
        with raises(CrossCampaignAccessError):
            store.get(store.put_bytes(payload, campaign_id="campaign-a"), campaign_id="campaign-b")
        # Named private catalog is per-campaign.
        with raises(FileNotFoundError):
            store.get_private("campaign-b", name)
        assert store.get_private("campaign-a", name) == payload
