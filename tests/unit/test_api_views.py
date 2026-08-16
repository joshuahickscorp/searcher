"""API projections and controller cancel/delete helpers."""

from __future__ import annotations

from tests.conftest import make_budget, make_intent
from tests.helpers_matching import make_candidate
from tests.support.offline_shop import tiny_png

from searcher.api.views import project_result, safe_http_url, safe_image_url, strip_private
from searcher.campaigns.events import numbered_public_events
from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    CampaignState,
    ImageRole,
    PublicEventName,
)
from searcher.contracts.models import BucketDecision, BucketDecisionFields
from searcher.contracts.primitives import PublicExplanation
from searcher.core.ids import new_id


def test_safe_urls_refuse_dangerous_schemes() -> None:
    assert safe_http_url("https://example.com/x") == "https://example.com/x"
    assert safe_http_url("javascript:alert(1)") is None
    assert safe_http_url("file:///etc/passwd") is None
    assert safe_image_url("/v1/media/abc") == "/v1/media/abc"
    assert safe_image_url("data:image/png;base64,aaa") is None


def test_strip_private_drops_paths() -> None:
    cleaned = strip_private({"state": "CREATED", "path": "/tmp/secret", "fixture_root": "/x"})
    assert "path" not in cleaned
    assert cleaned["state"] == "CREATED"


def test_cancel_from_created(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    updated = controller.cancel(intent.search_id)  # type: ignore[attr-defined]
    assert updated.state is CampaignState.CANCELLED
    events = numbered_public_events(controller.repos, intent.search_id)  # type: ignore[attr-defined]
    names = [event.event_name for _seq, event in events]
    assert PublicEventName.SEARCH_COMPLETE.value in names


def test_delete_then_missing(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    receipt = controller.delete(intent.search_id)  # type: ignore[attr-defined]
    assert receipt.receipt_type == "DeletionReceipt"
    assert receipt.verify()
    assert controller.repos.is_deleted(intent.search_id)  # type: ignore[attr-defined]
    assert controller.repos.get_receipt(receipt.receipt_id) is not None  # type: ignore[attr-defined]


def _decision(
    candidate_id: str, *, compared: list[str] | None = None
) -> BucketDecision:
    return BucketDecision(
        candidate_id=candidate_id,
        decision=BucketDecisionFields(
            internal=BucketInternal.POSSIBLY_REAL,
            public=BucketPublic.POSSIBLY_REAL,
        ),
        policy_version="matching-1",
        item_match_lower_bound=0.6,
        authenticity_lower_bound=0.5,
        evidence_completeness=0.4,
        explanation=PublicExplanation(
            compared_images=list(compared or []),
            live_status=Availability.LIVE,
        ),
    )


def test_images_compared_populated_when_comparison_ran(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    candidate, _pngs = make_candidate(
        images=[("lateral", tiny_png(), ImageRole.PRODUCT)],
    )
    image_id = candidate.images[0].listing_image_id
    decision = _decision(candidate.candidate_id, compared=[image_id])
    body = project_result(
        controller,  # type: ignore[arg-type]
        intent.search_id,
        new_id(),
        candidate_id=candidate.candidate_id,
        bucket=BucketPublic.POSSIBLY_REAL.value,
        rank=1,
        decision=decision,
        candidate=candidate,
    )
    compared = body["why"]["images_compared"]
    assert compared
    assert compared[0]["image_id"] == image_id
    assert compared[0]["role"] == ImageRole.PRODUCT.value
    assert compared[0]["url"].startswith("https://")
    assert body["why"]["images_compared_reason"] is None
    assert "reason" not in body["compare"]


def test_images_compared_states_reason_when_comparison_did_not_run(
    controller: object,
) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    candidate, _pngs = make_candidate(
        images=[("lateral", tiny_png(), ImageRole.PRODUCT)],
    )
    decision = _decision(candidate.candidate_id, compared=[])
    body = project_result(
        controller,  # type: ignore[arg-type]
        intent.search_id,
        new_id(),
        candidate_id=candidate.candidate_id,
        bucket=BucketPublic.POSSIBLY_REAL.value,
        rank=1,
        decision=decision,
        candidate=candidate,
    )
    assert body["why"]["images_compared"] == []
    assert body["why"]["images_compared_reason"] == "comparison stage did not run"
    assert body["compare"]["reason"] == "comparison stage did not run"


def test_images_compared_states_reason_when_comparison_recorded_none(
    controller: object,
) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    candidate, _pngs = make_candidate(
        images=[("lateral", tiny_png(), ImageRole.PRODUCT)],
    )
    decision = _decision(candidate.candidate_id, compared=[])
    controller.repos.insert_score(  # type: ignore[attr-defined]
        intent.search_id,
        new_id(),
        "ITEM_MATCH",
        0.5,
        0.4,
        0.6,
        {"match_evidence_id": new_id(), "explanation": {"compared_images": []}},
        candidate_id=candidate.candidate_id,
    )
    body = project_result(
        controller,  # type: ignore[arg-type]
        intent.search_id,
        new_id(),
        candidate_id=candidate.candidate_id,
        bucket=BucketPublic.POSSIBLY_REAL.value,
        rank=1,
        decision=decision,
        candidate=candidate,
    )
    assert body["why"]["images_compared"] == []
    assert body["why"]["images_compared_reason"] == (
        "comparison ran but recorded no compared images"
    )
