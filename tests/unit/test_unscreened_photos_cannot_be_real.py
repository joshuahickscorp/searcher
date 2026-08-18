"""Real must not open when theft and stock-photo screening never ran.

An adversarial pass found IMAGE_THEFT_OR_SCAM unreachable in production. It
fires only when a caller supplies `stolen_photo`, the only caller that supplies
it is the vision worker, and that worker is referenced solely from
tests/integration. So `stolen_ids` was always empty and a listing reusing the
brand's official photographs on a day-old account demanding off-platform
payment published as Real: item 0.91, authenticity 0.80, no veto.

`judge_candidates` now distinguishes never-screened (None) from screened-clean
(empty set), and the Real gate is fail-closed on the former. A gate that depends
on a check which never ran must not open.
"""

from __future__ import annotations

import inspect

from searcher.ranking import pipeline as ranking_pipeline
from searcher.ranking.buckets import route_candidate


def test_the_gate_takes_a_screening_flag_and_defaults_to_closed() -> None:
    sig = inspect.signature(route_candidate)
    param = sig.parameters.get("photo_screening_ran")
    assert param is not None, "the Real gate must know whether screening ran"
    assert param.default is False, (
        "the default must be fail-closed; a caller that says nothing has not screened"
    )


def test_judge_candidates_separates_never_screened_from_screened_clean() -> None:
    source = inspect.getsource(ranking_pipeline.judge_candidates)
    assert "stolen is not None" in source, (
        "None and an empty set must not collapse; that is what made an unreachable "
        "veto look like a clean result"
    )
    assert "photo_screening_ran" in source


def test_the_gate_refuses_real_before_it_consults_calibration() -> None:
    """Screening is checked first, so an unscreened candidate cannot pass."""
    from searcher.ranking import buckets

    source = inspect.getsource(buckets.route_candidate)
    screening = source.index("photo_screening_ran")
    calibrated = source.index("require_calibrated_for_real")
    assert screening < calibrated, (
        "the unscreened check must precede the calibration branch, or an "
        "unscreened candidate can still take the calibrated path to Real"
    )


def test_the_vision_worker_can_declare_both_screenings() -> None:
    """Fail-closed must be reachable, or it is fail-permanent.

    The gate requires both theft and stock screening before Real can open. The
    production worker took `stolen` and had no `stock_mixed` parameter at all,
    so no caller could ever say screening had run and Real was shut for every
    candidate regardless of what had actually been checked. A gate nothing can
    satisfy is not a safety property, it is a dead branch.
    """
    from searcher.workers.vision.worker import run_vision_worker

    params = inspect.signature(run_vision_worker).parameters
    assert "stolen" in params
    assert "stock_mixed" in params, (
        "a caller that screened for inserted stock photography must be able to say so"
    )


def test_the_orchestrator_screens_at_the_gate_it_actually_runs() -> None:
    """The screener has to sit on the path production takes.

    It was wired into `run_vision_worker`, which is referenced only from
    tests/integration. The orchestrator's own `route_candidate` call passed
    neither `stolen_photo` nor `photo_screening_ran`, so on every live campaign
    screening never ran and the Real gate stayed fail-closed for all candidates.

    That is the same shape as the defect the gate was written to fix: a safety
    behaviour present in a function nothing calls. Round 8 found it by running a
    campaign rather than reading the code.
    """
    from searcher.campaigns.orchestrator import CampaignOrchestrator

    source = inspect.getsource(CampaignOrchestrator._rank)
    assert "screen_photo_reuse(candidates)" in source, (
        "the ranking path must screen its own candidates"
    )
    assert "photo_screening_ran=True" in source, (
        "and must tell the gate that screening ran, or Real stays shut"
    )
    assert "stolen_photo=candidate.candidate_id in reused_ids" in source, (
        "and must pass the finding, or the veto is unreachable again"
    )
