"""Benchmark arithmetic stays honest on tiny synthetic inputs."""

from __future__ import annotations

from pathlib import Path

import pytest
from benchmark.degradations import DEGRADATION_NAMES, apply_degradation
from benchmark.metrics import (
    calibration_bins,
    false_real_report,
    mean_reciprocal_rank,
    precision_recall,
    recall_at_k,
    retrieval_block,
)
from tests.support.offline_shop import tiny_png


def test_recall_at_k_and_mrr() -> None:
    ranks = [1, 3, None]
    assert recall_at_k(ranks, 1) == pytest.approx(1 / 3)
    assert recall_at_k(ranks, 5) == pytest.approx(2 / 3)
    assert mean_reciprocal_rank(ranks) == pytest.approx((1.0 + 1.0 / 3) / 3)
    block = retrieval_block(ranks)
    assert block["n"] == 3
    assert block["missing"] == 1


def test_false_real_is_counted_separately() -> None:
    pairs = [
        ("a", "hidden", "real"),
        ("b", "real", "real"),
        ("c", "replica", "hidden"),
        ("d", "possibly_real", "possibly_real"),
    ]
    report = false_real_report(pairs)
    assert report["count"] == 1
    assert report["ids"] == ["a"]
    assert report["rate_among_not_real"] == 1 / 3


def test_precision_recall_and_confusion() -> None:
    pairs = [
        ("real", "real"),
        ("hidden", "real"),
        ("hidden", "hidden"),
        ("replica", "replica"),
        ("possibly_real", "hidden"),
    ]
    precision, recall, matrix = precision_recall(pairs)
    assert matrix["hidden"]["real"] == 1
    assert precision["real"] == 0.5
    assert recall["real"] == 1.0
    assert precision["replica"] == 1.0
    assert recall["possibly_real"] is None or recall["possibly_real"] == 0.0


def test_calibration_bins_place_shipped_threshold() -> None:
    pairs = [(0.1, False), (0.2, False), (0.87, True), (0.91, True), (0.4, False)]
    curve = calibration_bins(pairs, threshold=0.86)
    assert curve["threshold_bin"] is not None
    row = curve["bins"][curve["threshold_bin"]]
    assert row["lo"] <= 0.86 <= row["hi"]
    assert sum(int(bin_row["n"]) for bin_row in curve["bins"]) == 5


def test_named_degradations_are_deterministic() -> None:
    src = tiny_png((40, 80, 20))
    assert DEGRADATION_NAMES == (
        "pristine",
        "blur",
        "heavy_blur",
        "crop",
        "small",
        "recompressed",
        "phone_snapshot",
    )
    for name in DEGRADATION_NAMES:
        first = apply_degradation(src, name)
        second = apply_degradation(src, name)
        assert first == second
        assert first[:8] != b""  # produced bytes


def test_evidence_board_has_no_network_src(tmp_path: Path) -> None:
    from benchmark.evidence import render_board
    from benchmark.retrieval import QueryResult, RankedCandidate, RetrievalReport
    from benchmark.scores import resolve_scorer
    from benchmark.splits import assign_splits

    png = tiny_png((10, 10, 10))
    query = QueryResult(
        query_id="kind:x:pristine",
        target_id="kind:x",
        degradation="pristine",
        query_image="x_2.jpg",
        reference_image="x_1.jpg",
        query_bytes=png,
        rank=1,
        target_score=0.9,
        ranking=[RankedCandidate(item_id="kind:x", score=0.9, correct=True, image_name="x_1.jpg")],
        gallery_bytes={"kind:x": png},
    )
    retrieval = RetrievalReport(
        split="held_out",
        scorer=resolve_scorer(),
        protocol="test",
        queries=[query],
        wall_seconds=0.01,
        images_scored=1,
        not_computed=[],
    )
    from benchmark.buckets import BucketReport, BucketRow

    buckets = BucketReport(
        split="held_out",
        protocol="test",
        rows=[
            BucketRow(
                item_id="hardneg:true_match",
                case_id="true_match",
                truth="real",
                predicted="real",
                item_match_lower=0.9,
                authenticity_lower=0.8,
                completeness=0.7,
                reasons=["real-gate"],
                hard_vetoes=[],
                preview=png,
                reference_preview=png,
                correct=True,
            )
        ],
        wall_seconds=0.01,
        fetches=0,
        cache_hits=0,
        images_processed=2,
        not_computed=[],
    )
    html = render_board(
        splits=assign_splits(),
        retrieval=retrieval,
        buckets=buckets,
        calibration={
            "protocol": "test",
            "threshold_bin_note": "bin 8",
            "threshold_meaningful_on_this_scale": False,
            "curve": {
                "shipped_threshold": 0.86,
                "bins": [{"lo": 0.8, "hi": 0.9, "n": 2, "n_positive": 1}],
            },
        },
        operational={
            "wall_seconds_per_campaign": 0.01,
            "fetches_per_campaign": 0,
            "cache_hit_rate": 1.0,
            "images_per_second": 10.0,
            "note": "offline",
        },
        identity={"host": "test", "git_sha": "abc", "code_version": "0.1.0", "measured_at": "t"},
        not_computed=[],
        does_not_cover=["hidden evaluation"],
        adversarial=None,
    )
    assert "src='http://" not in html
    assert 'src="http://' not in html
    assert "src='https://" not in html
    assert 'src="https://' not in html
    assert "url(" not in html
    dest = tmp_path / "board.html"
    dest.write_text(html, encoding="utf-8")
    assert dest.stat().st_size > 100
