"""Offline known-item: cached KIND listing photos must surface that listing first."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers_matching import make_candidate, make_hypothesis

from searcher.contracts.enums import BucketPublic, ImageRole
from searcher.ranking.pipeline import judge_candidates
from searcher.retrieval.embeddings import resolve_backend

PACK_DIR = Path("fixtures/known_item_kind")
TARGET_URL = "https://shop.kind.co.jp/products/8001001141404"


def _load_pack() -> dict[str, object]:
    pack_path = PACK_DIR / "pack.json"
    if not pack_path.is_file():
        pytest.fail(f"missing known-item fixture pack at {pack_path}")
    return json.loads(pack_path.read_text(encoding="utf-8"))


def _read_image(name: str) -> bytes:
    path = PACK_DIR / "images" / name
    if not path.is_file():
        pytest.fail(f"missing fixture image {path}")
    return path.read_bytes()


def test_fixture_pack_records_source_and_fetch_date() -> None:
    pack = _load_pack()
    assert pack["target_url"] == TARGET_URL
    assert pack.get("fetch_date")
    assert pack.get("reference_images")
    assert (PACK_DIR / "images").is_dir()


def test_known_item_ranked_first_and_negative_is_not_real() -> None:
    if resolve_backend() is None:
        pytest.skip("local embedding weights are not installed")
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    pack = _load_pack()
    ref_names = list(pack["reference_images"])
    true_names = list(pack["true_listing_images"])
    neg = pack["negative_listing"]
    assert isinstance(neg, dict)
    neg_names = list(neg["images"])
    cand_true = true_names[1:] + true_names[:1] if len(true_names) > 1 else true_names
    ref = {name: _read_image(name) for name in ref_names}
    hyp = make_hypothesis(category="garment", text="Willy Chavarria")
    hyp = hyp.model_copy(
        update={
            "brand": hyp.brand.model_copy(update={"value": "Willy Chavarria"}),
            "model_name": hyp.model_name.model_copy(update={"value": "long sleeve"}),
        }
    )
    true_c, true_p = make_candidate(
        candidate_id="true",
        url=TARGET_URL,
        title="無地 ロングスリーブカットソー",
        description="WILLY CHAVARRIA 無地 ロングスリーブカットソー",
        images=[(name, _read_image(name), ImageRole.PRODUCT) for name in cand_true],
    )
    true_c = true_c.model_copy(
        update={
            "seller_reported_brand": true_c.seller_reported_brand.model_copy(
                update={"value": "WILLY CHAVARRIA"}
            )
            if true_c.seller_reported_brand
            else true_c.seller_reported_brand
        }
    )
    neg_c, neg_p = make_candidate(
        candidate_id="neg",
        url=str(neg["url"]),
        title=str(neg.get("title") or "other listing"),
        description="different listing in the same shop",
        images=[(name, _read_image(name), ImageRole.PRODUCT) for name in neg_names],
    )
    report = judge_candidates(
        search_id=hyp.search_id,
        hypothesis=hyp,
        candidates=[neg_c, true_c],
        reference_pngs=ref,
        candidate_pngs={"true": true_p, "neg": neg_p},
        already_deduplicated=True,
        destination_verified={"true": True, "neg": True},
    )
    by_id = {bundle.candidate.candidate_id: bundle for bundle in report.bundles}
    assert "true" in by_id
    true_bundle = by_id["true"]
    assert true_bundle.decision.decision.public in {
        BucketPublic.REAL,
        BucketPublic.POSSIBLY_REAL,
    }
    public = [
        *[item.decision.candidate_id for item in report.ranked_real],
        *[item.decision.candidate_id for item in report.ranked_possible],
    ]
    assert public, "source listing was not published to a public tab"
    assert public[0] == "true"
    if "neg" in by_id:
        assert by_id["neg"].decision.decision.public is not BucketPublic.REAL
    cites = " ".join(true_bundle.match.explanation.support)
    assert "embedding" in cites or "ev:embedding" in " ".join(
        true_bundle.match.global_visual.support
    )
