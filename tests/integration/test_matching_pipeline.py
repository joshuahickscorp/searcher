"""Normalized candidates through retrieval, matching, authenticity, ranking."""

from __future__ import annotations

from pathlib import Path

from tests.helpers_matching import constraints, make_candidate, make_hypothesis, views_for

from searcher.contracts.enums import BucketPublic, JudgmentKind
from searcher.matching.synth import ADJACENT_SHOE, REFERENCE_SHOE, render_views
from searcher.ranking.pipeline import judge_candidates
from searcher.ranking.questions import QUESTIONS
from searcher.retrieval.cost import HEAVYWEIGHT_STAGES, CostStage
from searcher.workers.vision.worker import run_vision_worker


def test_end_to_end_judgment_and_artifacts(tmp_path: Path) -> None:
    hyp = make_hypothesis()
    ref = render_views(REFERENCE_SHOE)
    true_c, true_p = make_candidate(
        candidate_id="true",
        url="https://fixture.example/true",
        images=views_for(REFERENCE_SHOE),
    )
    adj_c, adj_p = make_candidate(
        candidate_id="adj",
        url="https://fixture.example/adj",
        images=views_for(ADJACENT_SHOE),
    )
    rare_c, rare_p = make_candidate(
        candidate_id="rare",
        url="https://fixture.example/rare",
        title="unrelated navy boot archive listing",
        images=views_for(ADJACENT_SHOE),
    )
    report = run_vision_worker(
        search_id=hyp.search_id,
        hypothesis=hyp,
        candidates=[true_c, adj_c, rare_c],
        reference_pngs=ref,
        candidate_pngs={"true": true_p, "adj": adj_p, "rare": rare_p},
        constraints=constraints(),
        already_deduplicated=True,
        destination_verified={"true": True, "adj": True, "rare": True},
    )
    assert "true" in report.retrieval_ids
    assert report.ledger.cheap_first_respected()
    names = report.ledger.stage_names()
    dedupe_at = names.index(CostStage.DEDUPLICATION.value)
    for stage in HEAVYWEIGHT_STAGES:
        if stage.value in names:
            assert names.index(stage.value) > dedupe_at
    by_id = {bundle.candidate.candidate_id: bundle for bundle in report.bundles}
    assert by_id["true"].decision.decision.public is BucketPublic.REAL
    assert by_id["adj"].decision.decision.public is BucketPublic.HIDDEN
    true = by_id["true"]
    assert true.match.judgment is not None
    assert true.match.judgment.kind is JudgmentKind.ITEM_MATCH
    assert true.authenticity.judgment.kind is JudgmentKind.AUTHENTICITY_CONFIDENCE
    assert true.utility.judgment.kind is JudgmentKind.LISTING_UTILITY
    for question in QUESTIONS:
        assert question in true.answers
        assert true.answers[question] is not None or question == "last_checked"
    assert true.comparison is not None
    out = tmp_path / "compare-true.png"
    out.write_bytes(true.comparison.png)
    assert out.stat().st_size > 100
    artifacts = Path("fixtures/hard_negatives/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "true_match.png").write_bytes(true.comparison.png)
    if by_id["adj"].comparison:
        (artifacts / "adjacent.png").write_bytes(by_id["adj"].comparison.png)
    assert report.cost_receipt.verify()
    assert report.cost_receipt.cheap_first is True


def test_recall_floor_keeps_rare_true_item() -> None:
    hyp = make_hypothesis()
    ref = render_views(REFERENCE_SHOE)
    candidates = []
    pngs: dict[str, dict[str, bytes]] = {}
    dest = {}
    true_c, true_p = make_candidate(
        candidate_id="needle",
        url="https://fixture.example/needle",
        title="House Name Field Model 07",
        images=views_for(REFERENCE_SHOE),
    )
    candidates.append(true_c)
    pngs["needle"] = true_p
    dest["needle"] = True
    for i in range(12):
        c, p = make_candidate(
            candidate_id=f"dist-{i}",
            url=f"https://fixture.example/d{i}",
            title=f"unrelated object {i}",
            images=views_for(ADJACENT_SHOE),
        )
        candidates.append(c)
        pngs[c.candidate_id] = p
        dest[c.candidate_id] = True
    report = judge_candidates(
        search_id=hyp.search_id,
        hypothesis=hyp,
        candidates=candidates,
        reference_pngs=ref,
        candidate_pngs=pngs,
        constraints=constraints(),
        already_deduplicated=True,
        destination_verified=dest,
    )
    assert "needle" in report.retrieval_ids
    by_id = {bundle.candidate.candidate_id: bundle for bundle in report.bundles}
    assert by_id["needle"].decision.decision.public in {
        BucketPublic.REAL,
        BucketPublic.POSSIBLY_REAL,
    }
