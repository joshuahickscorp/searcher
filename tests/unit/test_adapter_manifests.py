"""Every registered adapter exposes a valid §14.2 manifest."""

from __future__ import annotations

from searcher.contracts.enums import QueryType, SourceAdmission
from searcher.contracts.models import QueryVariant
from searcher.sources.adapters import ADAPTER_REGISTRY, resolve_adapter
from searcher.sources.adapters.ebay_api import EbayApiAdapter
from searcher.sources.adapters.etsy_api import EtsyApiAdapter
from searcher.sources.adapters.searx import SearxAdapter
from searcher.sources.manifest import validate_manifest


def _query() -> QueryVariant:
    return QueryVariant(
        query_id="q",
        hypothesis_id="h",
        round=1,
        language="en",
        query_text="dior",
        query_type=QueryType.EXACT_NAME,
    )


def test_every_adapter_has_valid_manifest() -> None:
    for name in ADAPTER_REGISTRY:
        adapter = resolve_adapter(name)
        manifest = adapter.manifest()  # type: ignore[attr-defined]
        validate_manifest(manifest)
        assert manifest.source_id
        assert manifest.languages
        assert manifest.terms_review_status is not None


def test_review_required_adapters_are_disabled() -> None:
    for name in ("vinted", "mercari_jp", "yahoo_auctions", "buyee", "bunjang"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        assert manifest.admission_status is SourceAdmission.REVIEW_REQUIRED
        assert manifest.enabled is False
        assert manifest.open_question


def test_pending_scope_adapters_are_disabled_review_required() -> None:
    for name in ("depop", "grailed", "vestiaire", "taobao", "weidian", "yupoo"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        assert manifest.admission_status is SourceAdmission.REVIEW_REQUIRED
        assert manifest.enabled is False
        assert manifest.open_question


def test_searx_unavailable_without_endpoint() -> None:
    adapter = SearxAdapter(endpoint="")
    page = adapter.discover(_query(), None)
    assert page.outcome == "SOURCE_UNAVAILABLE"


def test_ebay_and_etsy_report_auth_required() -> None:
    ebay = EbayApiAdapter()
    etsy = EtsyApiAdapter()
    q = _query()
    assert ebay.discover(q, None).outcome == "AUTH_REQUIRED"
    assert etsy.discover(q, None).outcome == "AUTH_REQUIRED"
