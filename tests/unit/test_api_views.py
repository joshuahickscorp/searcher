"""API projections and controller cancel/delete helpers."""

from __future__ import annotations

from tests.conftest import make_budget, make_intent

from searcher.api.views import safe_http_url, safe_image_url, strip_private
from searcher.campaigns.events import numbered_public_events
from searcher.contracts.enums import CampaignState, PublicEventName


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
