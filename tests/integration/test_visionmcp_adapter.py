"""Real VisionMCP invocation and honest degradation."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from searcher.campaigns.controller import CampaignController
from searcher.core.config import Settings
from searcher.core.errors import CapabilityUnavailable
from searcher.core.ids import new_id
from searcher.evidence.content_store import ContentStore
from searcher.integrations.visionmcp.adapter import SearcherVisionAdapter
from searcher.integrations.visionmcp.compatibility import (
    PINNED_VERSION,
    assert_core_contract,
    import_visionmcp,
)
from searcher.reference.analysis import analyze_stored_references
from searcher.reference.ingest import ingest_bytes
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


def _png(label: str = "LAT") -> bytes:
    image = Image.new("RGB", (320, 220), (24, 24, 26))
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 50, 290, 190), fill=(16, 16, 18), outline=(90, 90, 80))
    draw.text((12, 8), label, fill=(230, 230, 220))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _session(tmp_path: Path) -> tuple[Settings, Database, ContentStore, CampaignController]:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db, settings.migrations_dir)
    store = ContentStore(settings.data_root, disk_margin_bytes=1024, max_object_bytes=5_000_000)
    return settings, db, store, CampaignController(db, store, settings)


def test_real_visionmcp_inspect_and_analyze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # These assertions describe what the donor contributes on its own. Local
    # embedding weights are a separate lane and would otherwise flip
    # learned_embedding_available on any host that has them installed.
    monkeypatch.delenv("SEARCHER_EMBEDDING_WEIGHTS", raising=False)
    monkeypatch.setenv("SEARCHER_DATA_ROOT", str(tmp_path))
    pkg = import_visionmcp()
    if pkg is None:
        pytest.skip("visionmcp not installed; pin the audited SHA to run this test")
    pin = assert_core_contract()
    assert pin["version"] == PINNED_VERSION
    settings, db, store, _controller = _session(tmp_path)
    try:
        search_id = new_id()
        refs = [
            ingest_bytes(store, _png("A"), search_id=search_id, settings=settings),
            ingest_bytes(store, _png("B"), search_id=search_id, settings=settings),
        ]
        adapter = SearcherVisionAdapter(store, search_id=search_id, settings=settings)
        tmp = tmp_path / "donor.png"
        tmp.write_bytes(_png("C"))
        inspected = adapter.inspect_via_donor(tmp)
        assert inspected is not None
        assert inspected["decode_ok"] is True
        assert inspected["width"] > 0
        analysis = asyncio.run(
            adapter.analyze_reference_set(refs, "House Name Field Model 07", ["black"])
        )
        assert analysis.donor_invoked is True
        assert analysis.images
        assert analysis.primary_cluster.image_ids
        assert analysis.visual_signature.descriptor_kind == "cheap_histogram"
        assert analysis.visual_signature.learned_embedding_available is False
        assert analysis.promotion_blocked is True
        assert any(lane.name == "DENSE_FEATURES" and lane.blocked for lane in analysis.lanes)
        with pytest.raises(CapabilityUnavailable, match="retrieve_candidates"):
            asyncio.run(adapter.retrieve_candidates(analysis, []))
        with pytest.raises(CapabilityUnavailable, match="compare_candidate"):
            asyncio.run(adapter.compare_candidate(analysis, object()))
        missing = asyncio.run(adapter.request_missing_evidence(analysis, []))
        assert missing
    finally:
        db.close()


def test_honest_degradation_without_donor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCHER_VISIONMCP", "0")
    monkeypatch.delenv("SEARCHER_EMBEDDING_WEIGHTS", raising=False)
    monkeypatch.setenv("SEARCHER_DATA_ROOT", str(tmp_path))
    settings, db, store, _controller = _session(tmp_path)
    try:
        search_id = new_id()
        refs = [ingest_bytes(store, _png("A"), search_id=search_id, settings=settings)]
        adapter = SearcherVisionAdapter(store, search_id=search_id, settings=settings)
        assert adapter.donor_available() is False
        analysis = analyze_stored_references(
            store,
            refs,
            text="House Name Field Model 07",
            tags=["black"],
            search_id=search_id,
            settings=settings,
            donor_inspect=None,
        )
        assert analysis.donor_invoked is False
        assert analysis.promotion_blocked is True
        assert analysis.visual_signature.learned_embedding_available is False
        assert "learned dense embedding unavailable" in analysis.visual_signature.uncertain_features
        # No fabricated learned embedding digest presented as a model output.
        assert analysis.visual_signature.descriptor_kind == "cheap_histogram"
        with pytest.raises(CapabilityUnavailable):
            asyncio.run(adapter.retrieve_candidates(analysis, []))
    finally:
        db.close()
