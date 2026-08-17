"""Source branches exist to keep a fetch honest.

A blocked, failed, or unmeasured source must stay that, a disabled adapter
must not search, and a budget or robots rule must be visible in the skip
reason rather than disappearing into an empty result.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from searcher.campaigns.cancellation import CancellationController
from searcher.contracts.enums import (
    Availability,
    DocumentClass,
    FactClass,
    FactOrigin,
    FetchMode,
    FrontierState,
    SourceAdmission,
    SourceFamily,
    SourceHealthState,
    SourceOutcome,
    WorkKind,
)
from searcher.contracts.models import (
    ListingCandidate,
    ListingImage,
    RawListing,
    SourceHealth,
)
from searcher.contracts.primitives import classified
from searcher.core.errors import CancelledError, InvariantViolation
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.sources import escalate as escalate_mod
from searcher.sources import liveness as liveness_mod
from searcher.sources.adapters.generic_page import classify_page_type
from searcher.sources.adapters.product import query_slugs, slugify_query, usable_query_text
from searcher.sources.admission import AdmissionDecision, AdmissionGate
from searcher.sources.broker import Coverage, _adapter_unavailable_outcome, _health_skip_outcome
from searcher.sources.cancel import RunCancel
from searcher.sources.catalog import (
    feed_text_matches,
    haystack_from_product,
    match_score,
    query_terms,
)
from searcher.sources.challenge import (
    BLOCKED_BY_CHALLENGE,
    challenge_note,
    is_challenge_block,
    looks_like_challenge,
)
from searcher.sources.circuit import CircuitBreaker, CircuitOpen
from searcher.sources.classify import (
    classify_acquired_document,
    host_of,
    looks_like_index_url,
    looks_like_product_url,
    origin_of,
    try_json,
)
from searcher.sources.engine import (
    _kind_for_url,
    catalog_caps_for_campaign,
    catalog_page_share,
    remaining_page_budget,
)
from searcher.sources.expand import (
    IMAGES_MISSING_KEY,
    IndexMember,
    _host_allowed,
    _sitemap_loc_matches_query,
    _sitemap_query_tokens,
    attach_image_absence,
    expand_index,
    expansion_caps_from_env,
    extract_index_members,
    shopify_members_from_body,
)
from searcher.sources.families import (
    family_for,
    names_for_scopes,
    normalize_source_scopes,
    registered_ids_for,
)
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.frontier import MAX_DEPTH, FrontierItem, compute_priority
from searcher.sources.health import may_plan, state_from_outcome
from searcher.sources.http import redact_headers
from searcher.sources.live_check import classify_liveness
from searcher.sources.manifest import build_manifest, validate_manifest
from searcher.sources.platform import (
    credential_gate_note,
    feed_path_blocked_reason,
    host_variants,
    is_sitemap_loc,
    maybe_decompress,
    requires_operator_credential,
    robots_evidence,
)
from searcher.sources.policy import SourcePolicy
from searcher.sources.rate_limit import BandwidthLimiter
from searcher.sources.retry import backoff_seconds, parse_retry_after, should_retry
from searcher.sources.robots import RobotsCache, extract_crawl_delay, path_matches_prefix
from searcher.sources.statuses import (
    classify_http,
    is_block,
    is_failure,
    is_success,
    refuse_no_match_collapse,
)
from searcher.sources.strategies import (
    STATUS_BLOCKED,
    STATUS_SKIPPED,
    StrategyAttempt,
    _blocked_reason,
    format_strategy_detail,
    is_collection_template,
    is_site_search_template,
    missing_key_note,
    strategy_url_allowed,
)
from searcher.sources.work_key import work_key


def _listing(
    *,
    title: str = "trainer",
    url: str = "https://shop.example/products/1",
    images: list[ListingImage] | None = None,
) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url,
        source_adapter="kind",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        images=images or [],
        first_seen_at=utc_now(),
        last_checked_at=utc_now(),
    )


def _policy(**overrides: object) -> SourcePolicy:
    payload: dict[str, object] = {
        "source_id": "shop",
        "search": True,
        "page_fetch": True,
        "render": False,
        "image_retrieval": True,
        "cache": True,
        "persistent_metadata": True,
        "thumbnail_publication": False,
        "refresh_frequency": "on-demand",
        "admission": SourceAdmission.ADMITTED,
    }
    payload.update(overrides)
    return SourcePolicy(**payload)  # type: ignore[arg-type]


def _manifest(**overrides: object):
    payload: dict[str, object] = {
        "source_id": "shop",
        "adapter": "shop",
        "domain": "shop.example",
        "access_method": "http_get",
        "admission_status": SourceAdmission.ADMITTED,
        "allowed_use": "public listing fetch",
        "enabled": True,
    }
    payload.update(overrides)
    return build_manifest(**payload)  # type: ignore[arg-type]


# --- HTTP outcomes stay honest ------------------------------------------------


def test_a_missing_status_is_a_network_failure_not_an_empty_search() -> None:
    assert classify_http(None) is SourceOutcome.NETWORK_FAILED
    assert classify_http(408) is SourceOutcome.NETWORK_FAILED
    assert classify_http(504) is SourceOutcome.NETWORK_FAILED
    assert classify_http(302) is SourceOutcome.NETWORK_FAILED


def test_a_server_error_is_source_unavailable() -> None:
    assert classify_http(500) is SourceOutcome.SOURCE_UNAVAILABLE
    assert classify_http(503) is SourceOutcome.SOURCE_UNAVAILABLE


def test_success_statuses_are_matches_unless_the_body_is_a_challenge() -> None:
    assert classify_http(200, body=None) is SourceOutcome.SEARCHED_MATCHES_FOUND
    assert classify_http(304, body="ok") is SourceOutcome.SEARCHED_MATCHES_FOUND
    assert classify_http(200, body=b"Just a moment...") is SourceOutcome.BLOCKED_BY_ACCESS
    assert classify_http(200, challenge=True) is SourceOutcome.BLOCKED_BY_ACCESS


def test_an_unknown_status_is_unmeasurable_not_no_match() -> None:
    assert classify_http(418) is SourceOutcome.UNMEASURABLE
    assert is_success(SourceOutcome.SEARCHED_NO_MATCH) is True
    assert is_success(SourceOutcome.SEARCHED_MATCHES_FOUND) is True
    assert is_success(SourceOutcome.NETWORK_FAILED) is False
    assert is_block(SourceOutcome.BLOCKED_BY_ACCESS) is True
    assert is_failure(SourceOutcome.NETWORK_FAILED) is True


def test_a_block_cannot_be_collapsed_into_no_match() -> None:
    assert (
        refuse_no_match_collapse(SourceOutcome.SEARCHED_NO_MATCH)
        is SourceOutcome.SEARCHED_NO_MATCH
    )
    assert (
        refuse_no_match_collapse(SourceOutcome.SEARCHED_MATCHES_FOUND)
        is SourceOutcome.SEARCHED_MATCHES_FOUND
    )
    with pytest.raises(InvariantViolation, match="SEARCHED_NO_MATCH"):
        refuse_no_match_collapse(SourceOutcome.BLOCKED_BY_POLICY)


# --- retry is cause-specific --------------------------------------------------


def test_retry_after_is_capped_and_a_past_date_is_zero() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("   ") is None
    assert parse_retry_after("not-a-date") is None
    assert parse_retry_after("120") == 60.0
    assert parse_retry_after("-3") == 0.0
    past = format_datetime(datetime(1999, 1, 1, tzinfo=UTC))
    assert parse_retry_after(past) == 0.0


def test_retry_stops_at_the_ceiling_and_honours_retry_after() -> None:
    assert should_retry(SourceOutcome.RATE_LIMITED, attempt=4) is False
    assert should_retry(SourceOutcome.RATE_LIMITED, attempt=1) is True
    assert should_retry(SourceOutcome.BLOCKED_BY_ACCESS, attempt=1) is False
    assert backoff_seconds(1, retry_after=90.0) == 60.0
    delay = backoff_seconds(3)
    assert 0 < delay <= 30.0


# --- families and scopes ------------------------------------------------------


def test_a_bare_string_scope_is_accepted_and_unknown_types_default() -> None:
    assert normalize_source_scopes("replica") == ("replica",)
    assert normalize_source_scopes(42) == ("legitimate",)
    assert normalize_source_scopes("LEGITIMATE") == ("legitimate",)


def test_a_preferred_order_still_gains_replica_ids_when_that_scope_is_selected() -> None:
    names = names_for_scopes(
        ["replica"],
        preferred=("ebay",),
        default_order=("ebay", "kind"),
    )
    assert "ebay" not in names
    assert set(names) == set(registered_ids_for(SourceFamily.REPLICA))
    assert family_for("not-a-registered-source") is SourceFamily.LEGITIMATE


# --- cancel, circuit, health --------------------------------------------------


def test_a_local_cancel_is_visible_without_a_campaign_controller() -> None:
    cancel = RunCancel("s")
    assert cancel.is_cancelled() is False
    cancel.request()
    assert cancel.is_cancelled() is True
    with pytest.raises(CancelledError, match="source run cancelled"):
        cancel.raise_if_cancelled()


def test_a_campaign_cancel_is_visible_to_the_source_run() -> None:
    campaign = CancellationController()
    cancel = RunCancel("s", campaign=campaign)
    campaign.request("s")
    assert cancel.is_cancelled() is True
    other = RunCancel("s", campaign=CancellationController())
    assert other.is_cancelled() is False
    other.raise_if_cancelled()


def test_an_open_circuit_refuses_new_work() -> None:
    class _Store:
        def __init__(self) -> None:
            self.rows: dict[str, SourceHealth] = {}

        def get(self, source_id: str) -> SourceHealth | None:
            return self.rows.get(source_id)

        def record(self, source_id: str, outcome: SourceOutcome) -> SourceHealth:
            health = SourceHealth(
                source_id=source_id,
                last_outcome=outcome,
                circuit_open=outcome is SourceOutcome.BLOCKED_BY_ACCESS,
                last_checked_at=utc_now(),
                state=SourceHealthState.BLOCKED,
            )
            self.rows[source_id] = health
            return health

    store = _Store()
    breaker = CircuitBreaker(store)  # type: ignore[arg-type]
    breaker.assert_closed("shop")
    assert breaker.is_open("shop") is False
    breaker.record("shop", SourceOutcome.BLOCKED_BY_ACCESS)
    assert breaker.is_open("shop") is True
    with pytest.raises(CircuitOpen):
        breaker.assert_closed("shop")


def test_health_state_follows_the_last_outcome_not_history() -> None:
    assert (
        state_from_outcome(
            SourceOutcome.SEARCHED_MATCHES_FOUND,
            consecutive_failures=0,
            circuit_open=False,
            policy_disabled=True,
        )
        is SourceHealthState.POLICY_DISABLED
    )
    assert (
        state_from_outcome(
            SourceOutcome.SOURCE_UNAVAILABLE,
            consecutive_failures=0,
            circuit_open=False,
            policy_disabled=False,
        )
        is SourceHealthState.UNAVAILABLE
    )
    assert (
        state_from_outcome(
            SourceOutcome.PARSER_FAILED,
            consecutive_failures=0,
            circuit_open=False,
            policy_disabled=False,
        )
        is SourceHealthState.PARSER_DRIFT
    )
    assert (
        state_from_outcome(
            SourceOutcome.RATE_LIMITED,
            consecutive_failures=0,
            circuit_open=False,
            policy_disabled=False,
        )
        is SourceHealthState.DEGRADED
    )
    assert (
        state_from_outcome(
            SourceOutcome.BLOCKED_BY_ACCESS,
            consecutive_failures=0,
            circuit_open=False,
            policy_disabled=False,
        )
        is SourceHealthState.BLOCKED
    )
    assert may_plan(SourceHealthState.HEALTHY) is True
    assert may_plan(SourceHealthState.BLOCKED) is False
    assert may_plan(SourceHealthState.UNAVAILABLE) is False


# --- manifest and challenge ---------------------------------------------------


def test_a_blocked_source_cannot_be_enabled() -> None:
    with pytest.raises(ValueError, match="source_id"):
        validate_manifest(_manifest(source_id="", adapter="a", domain="d"))
    with pytest.raises(ValueError, match="access_method"):
        validate_manifest(_manifest(access_method=""))
    with pytest.raises(ValueError, match="blocked and cannot be enabled"):
        validate_manifest(
            _manifest(admission_status=SourceAdmission.BLOCKED, enabled=True)
        )
    ok = validate_manifest(_manifest(admission_status=SourceAdmission.BLOCKED, enabled=False))
    assert ok.enabled is False


def test_a_challenge_note_is_the_block_reason() -> None:
    assert looks_like_challenge("Checking your browser before you continue") is True
    note = challenge_note("verify you are human")
    assert note.startswith(BLOCKED_BY_CHALLENGE)
    assert is_challenge_block(note) is True
    assert is_challenge_block(None, error_class=BLOCKED_BY_CHALLENGE) is True
    assert is_challenge_block("robots disallow") is False


# --- admission gates before any fetch -----------------------------------------


def test_a_disabled_adapter_is_blocked_by_policy() -> None:
    gate = AdmissionGate(robots=SimpleNamespace(), http=SimpleNamespace())  # type: ignore[arg-type]
    decision = gate.decide(
        "https://shop.example/item",
        _manifest(enabled=False, open_question="pending review"),
    )
    assert decision.allowed is False
    assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert "pending review" in decision.basis


def test_a_recorded_block_is_not_a_search() -> None:
    gate = AdmissionGate(robots=SimpleNamespace(), http=SimpleNamespace())  # type: ignore[arg-type]
    decision = gate.decide(
        "https://shop.example/item",
        _manifest(admission_status=SourceAdmission.BLOCKED),
    )
    assert decision.allowed is False
    assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert "recorded blocked" in decision.basis


def test_a_purpose_the_source_does_not_admit_is_blocked() -> None:
    gate = AdmissionGate(robots=SimpleNamespace(), http=SimpleNamespace())  # type: ignore[arg-type]
    no_search = gate.decide(
        "https://shop.example/item",
        _manifest(),
        purpose="search",
        policy=_policy(search=False),
    )
    assert no_search.allowed is False
    assert "search is not an admitted use" in no_search.basis
    no_render = gate.decide(
        "https://shop.example/item",
        _manifest(),
        purpose="render",
        policy=_policy(render=False, page_fetch=False),
    )
    assert no_render.allowed is False
    assert "render is not an admitted use" in no_render.basis
    no_page = gate.decide(
        "https://shop.example/item",
        _manifest(access_method="http_get"),
        purpose="page_fetch",
        policy=_policy(page_fetch=False),
    )
    assert no_page.allowed is False
    assert "page fetch is not an admitted use" in no_page.basis


def test_skipping_live_robots_is_recorded_not_silent() -> None:
    gate = AdmissionGate(robots=SimpleNamespace(), http=SimpleNamespace())  # type: ignore[arg-type]
    decision = gate.decide(
        "https://example.com/products/1",
        _manifest(domain="example.com"),
        skip_live_robots=True,
    )
    assert decision.allowed is True
    assert decision.robots_fetch_status == "skipped"
    assert decision.basis == "live robots skipped"


def test_refuse_if_disallowed_raises_on_a_disabled_adapter() -> None:
    gate = AdmissionGate(robots=SimpleNamespace(), http=SimpleNamespace())  # type: ignore[arg-type]
    with pytest.raises(Exception, match="disabled"):
        gate.refuse_if_disallowed("https://shop.example/item", _manifest(enabled=False))


# --- document class -----------------------------------------------------------


def test_a_collection_url_is_an_index_unless_it_names_one_product() -> None:
    assert looks_like_index_url("https://shop.example/collections/trainers") is True
    assert looks_like_index_url("https://shop.example/products.json") is True
    assert looks_like_index_url("https://shop.example/sitemap.xml") is True
    assert looks_like_index_url("https://shop.example/search?q=dior") is True
    product = "https://shop.example/collections/trainers/products/8001"
    assert looks_like_index_url(product) is False
    assert looks_like_product_url(product) is True
    assert looks_like_product_url("https://shop.example/products/8001") is True
    assert looks_like_product_url(
        "https://shop.example/item/8001", listing_prefixes=("/item/",)
    ) is True
    assert looks_like_product_url("https://shop.example/about") is False


def test_url_shape_wins_over_a_misleading_body() -> None:
    products = json.dumps({"products": [{"id": 1}, {"id": 2}]}).encode()
    one = json.dumps({"product": {"id": 1, "title": "x"}}).encode()
    assert (
        classify_acquired_document(url="https://shop.example/products.json", body=products)
        is DocumentClass.INDEX
    )
    assert (
        classify_acquired_document(
            url="https://shop.example/products/8001.json", body=one
        )
        is DocumentClass.PRODUCT
    )
    assert (
        classify_acquired_document(
            url="https://shop.example/products/8001", body=products
        )
        is DocumentClass.INDEX
    )


def test_a_sitemap_body_is_an_index_even_without_a_sitemap_url() -> None:
    body = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    assert (
        classify_acquired_document(
            url="https://shop.example/export", body=body, content_type="application/xml"
        )
        is DocumentClass.INDEX
    )


def test_json_ld_item_list_is_an_index_and_a_product_type_is_a_product() -> None:
    item_list = (
        b'<script type="application/ld+json">'
        b'{"@type":"ItemList","itemListElement":[]}</script>'
    )
    product = (
        b'<script type="application/ld+json">'
        b'{"@type":"Product","name":"trainer"}</script>'
    )
    assert (
        classify_acquired_document(url="https://shop.example/x", body=item_list)
        is DocumentClass.INDEX
    )
    assert (
        classify_acquired_document(url="https://shop.example/x", body=product)
        is DocumentClass.PRODUCT
    )
    assert (
        classify_acquired_document(url="https://shop.example/about", body=b"hello")
        is DocumentClass.OTHER
    )


def test_try_json_and_origin_helpers_do_not_invent_a_host() -> None:
    assert try_json(b"") is None
    assert try_json(b"not-json") is None
    assert try_json(b'{"ok": true}') == {"ok": True}
    assert origin_of("/relative") == ""
    assert origin_of("https://Shop.Example/a") == "https://Shop.Example"
    assert host_of("https://Shop.Example/a") == "shop.example"


# --- expansion ---------------------------------------------------------------


def test_expansion_caps_treat_junk_env_as_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCHER_INDEX_EXPAND_PER_INDEX", "not-a-number")
    monkeypatch.setenv("SEARCHER_INDEX_EXPAND_PER_CAMPAIGN", "")
    caps = expansion_caps_from_env()
    assert caps.per_index == 24
    assert caps.per_campaign == 48
    monkeypatch.setenv("SEARCHER_INDEX_EXPAND_PER_INDEX", "-3")
    assert expansion_caps_from_env().per_index == 0


def test_a_member_without_images_states_whether_the_feed_omitted_them() -> None:
    feed = IndexMember(url="https://shop.example/products/1", from_feed=True)
    page = IndexMember(url="https://shop.example/products/1", from_feed=False)
    pictured = IndexMember(url="https://shop.example/products/1", images=["https://img"])
    assert feed.image_absence_reason() == "feed_listed_no_images"
    assert page.image_absence_reason() == "page_extracted_no_images"
    assert pictured.image_absence_reason() is None


def test_off_host_index_links_are_not_taken() -> None:
    assert _host_allowed("https://shop.example/p/1", ["shop.example"]) is True
    assert _host_allowed("https://other.example/p/1", ["shop.example"]) is False
    assert _host_allowed("https://shop.example/p/1", []) is False
    assert _host_allowed("not-a-url", ["shop.example"]) is False


def test_sitemap_query_tokens_ignore_short_words_and_empty_matches_everything() -> None:
    tokens = _sitemap_query_tokens(["Dior of trainer", "of"])
    assert "dior" in tokens
    assert "of" not in tokens
    assert _sitemap_loc_matches_query("https://shop.example/dior-trainer", tokens) is True
    assert _sitemap_loc_matches_query("https://shop.example/unrelated", tokens) is False
    assert _sitemap_loc_matches_query("https://shop.example/x", []) is True


def test_a_sitemap_index_expands_to_child_sitemaps_and_listing_locs() -> None:
    body = b"""<?xml version="1.0"?>
    <sitemapindex>
      <loc>https://shop.example/sitemap_products_1.xml</loc>
      <loc>https://shop.example/products/8001</loc>
      <loc>https://shop.example/about</loc>
    </sitemapindex>
    """
    members = extract_index_members(
        url="https://shop.example/sitemap.xml",
        body=body,
        listing_prefixes=("/products/",),
    )
    urls = [item.url for item in members]
    assert "https://shop.example/sitemap_products_1.xml" in urls
    assert "https://shop.example/products/8001" in urls
    assert "https://shop.example/about" not in urls


def test_a_non_object_shopify_body_is_not_a_feed() -> None:
    origin = "https://shop.example"
    url = f"{origin}/products.json"
    assert shopify_members_from_body(b"[1, 2]", url, origin=origin) == []
    assert shopify_members_from_body(b"nope", url, origin=origin) == []


def test_a_shopify_product_object_becomes_one_member_and_skips_blank_handles() -> None:
    origin = "https://shop.example"
    body = json.dumps(
        {
            "product": {
                "handle": "trainer-07",
                "title": "Army Trainer",
                "vendor": "Dior",
                "body_html": "<p>Used</p>",
                "published_at": "2007-01-01",
                "images": [{"src": "https://img.example/2.jpg"}, "https://img.example/2.jpg"],
                "image": {"src": "https://img.example/1.jpg"},
                "variants": [
                    {
                        "price": "800",
                        "available": True,
                        "presentment_prices": [
                            {"price": {"currency_code": "JPY", "amount": "800"}}
                        ],
                    }
                ],
            }
        }
    ).encode()
    members = shopify_members_from_body(body, f"{origin}/products/trainer-07.json", origin=origin)
    assert len(members) == 1
    member = members[0]
    assert member.url.endswith("/products/trainer-07")
    assert member.from_feed is True
    assert member.availability == "InStock"
    assert member.images[0] == "https://img.example/1.jpg"
    assert member.currency == "JPY"
    skipped = shopify_members_from_body(
        json.dumps({"products": [{"title": "no handle"}, {"id": "x"}]}).encode(),
        f"{origin}/products.json",
        origin=origin,
    )
    assert [item.handle for item in skipped] == ["x"]


def test_json_ld_item_list_members_are_preferred_over_an_empty_feed() -> None:
    html = (
        b'<script type="application/ld+json">'
        b'{"@type":"ItemList","itemListElement":['
        b'{"@type":"ListItem","url":"https://shop.example/products/a"},'
        b'{"item":{"url":"https://shop.example/products/b","name":"B"}},'
        b'{"item":"https://shop.example/products/c"}'
        b"]}</script>"
    )
    members = extract_index_members(url="https://shop.example/collection", body=html)
    urls = [item.url for item in members]
    assert "https://shop.example/products/a" in urls
    assert "https://shop.example/products/b" in urls
    assert "https://shop.example/products/c" in urls


def test_expansion_records_why_a_member_was_dropped() -> None:
    body = json.dumps(
        {
            "products": [
                {"handle": "kept", "title": "Kept"},
                {"handle": "other-host", "title": "Other"},
            ]
        }
    ).encode()
    # Rewrite the second URL by expanding then checking host filter: members
    # from this feed all share shop.example, so inject an off-host member via
    # a sitemap loc instead.
    sitemap = b"""<?xml version="1.0"?><urlset>
      <loc>https://shop.example/products/kept</loc>
      <loc>https://evil.example/products/nope</loc>
      <loc></loc>
    </urlset>"""
    deep = expand_index(
        url="https://shop.example/sitemap.xml",
        body=sitemap,
        listing_prefixes=("/products/",),
        allowed_hosts=["shop.example"],
        child_depth=4,
        max_depth=3,
    )
    assert deep.taken == []
    assert deep.drop_reasons.get("max_depth", 0) >= 1
    result = expand_index(
        url="https://shop.example/sitemap.xml",
        body=sitemap,
        listing_prefixes=("/products/",),
        allowed_hosts=["shop.example"],
    )
    taken_urls = [item.url for item in result.taken]
    assert "https://shop.example/products/kept" in taken_urls
    assert "https://evil.example/products/nope" not in taken_urls
    assert result.drop_reasons.get("host_not_admitted", 0) >= 1
    del body


def test_image_absence_is_attached_when_the_listing_has_no_images() -> None:
    raw = RawListing(
        source_adapter="kind",
        url="https://shop.example/products/1",
        payload={IMAGES_MISSING_KEY: "feed_listed_no_images"},
        content_digest="abc",
        fetched_at=utc_now(),
    )
    bare = _listing()
    updated = attach_image_absence(bare, raw)
    assert updated.structured_data[IMAGES_MISSING_KEY] == "feed_listed_no_images"
    pictured = _listing(
        images=[ListingImage(listing_image_id=new_id(), candidate_id="c", remote_url="https://img")]
    )
    assert attach_image_absence(pictured, raw) is pictured
    fallback = attach_image_absence(_listing(), None)
    assert fallback.structured_data[IMAGES_MISSING_KEY] == "page_extracted_no_images"


# --- strategies and query slugs ----------------------------------------------


def test_strategy_detail_names_why_a_strategy_was_empty() -> None:
    attempts = [
        StrategyAttempt(name="catalog_feed", status="tried", reason="", yielded=3),
        StrategyAttempt(
            name="site_search",
            status=STATUS_SKIPPED,
            reason="robots Disallow: /search",
            yielded=0,
        ),
        {"name": "sitemap", "status": "tried", "reason": "no locs", "yielded": 0},
        {"name": "", "status": "tried", "reason": "ignored", "yielded": 1},
        StrategyAttempt(
            name="official_api", status=STATUS_BLOCKED, reason="missing key", yielded=0
        ),
    ]
    detail = format_strategy_detail(attempts)
    assert "catalog_feed: 3" in detail
    assert "site_search: skipped (robots Disallow: /search)" in detail
    assert "sitemap: 0 (no locs)" in detail
    assert "official_api: blocked (missing key)" in detail
    assert detail.count(":") >= 3


def test_missing_key_note_lists_every_absent_name() -> None:
    one = missing_key_note(
        key_names=["EBAY_APP_ID"],
        present={"EBAY_APP_ID": ""},
        signup_url="https://developer.ebay.com",
        product="eBay",
    )
    assert one.startswith("missing EBAY_APP_ID")
    two = missing_key_note(
        key_names=["A", "B"],
        present={"A": None, "B": " "},
        signup_url="https://example",
        product="X",
    )
    assert "A and B" in two
    three = missing_key_note(
        key_names=["A", "B", "C"],
        present={},
        signup_url="https://example",
        product="X",
    )
    assert "A, B, and C" in three
    present = missing_key_note(
        key_names=["A"],
        present={"A": "set"},
        signup_url="https://example",
        product="X",
    )
    assert "credentials are set" in present


def test_a_collection_template_is_not_a_site_search() -> None:
    assert is_site_search_template("https://shop.example/search?q={query}") is True
    assert is_site_search_template("https://shop.example/collections/{slug}") is False
    assert is_collection_template("https://shop.example/collections/{slug}") is True
    assert strategy_url_allowed("https://shop.example/search", ["/search"]) is False
    assert strategy_url_allowed("https://shop.example/products/1", ["/search"]) is True
    assert _blocked_reason("https://shop.example/search?q=x", []) == "robots Disallow: /search"
    assert _blocked_reason("https://shop.example/admin", ["/admin"]) == (
        "recorded disallowed path prefix"
    )
    assert _blocked_reason("https://shop.example/products/1", []) == "url is not admitted"


def test_query_slugs_are_vendor_handles_not_the_full_query() -> None:
    assert usable_query_text("x") == ""
    assert usable_query_text("  Dior Homme  ") == "Dior Homme"
    assert query_slugs("Dior Homme trainer 07") == ["dior-homme"]
    assert query_slugs("Comme") == ["comme"]
    assert query_slugs("") == []
    assert slugify_query("Dior  Homme!") == "dior-homme"


def test_page_type_follows_the_document_class() -> None:
    assert classify_page_type("<html></html>", "https://shop.example/search?q=x") == "search"
    assert classify_page_type("<html></html>", "https://shop.example/collections/x") == "collection"
    assert classify_page_type("<html></html>", "https://shop.example/products/1") == "product"
    assert classify_page_type("<html></html>", "https://shop.example/about") == "unknown"


# --- platform, catalog, engine budget -----------------------------------------


def test_gzip_sitemap_bodies_decompress_and_garbage_is_left_alone() -> None:
    raw = b"<urlset></urlset>"
    assert maybe_decompress(raw) == raw
    assert maybe_decompress(gzip.compress(raw)) == raw
    assert maybe_decompress(b"\x1f\x8bnot-gzip") == b"\x1f\x8bnot-gzip"
    assert is_sitemap_loc("https://shop.example/sitemap_products_1.xml") is True
    assert is_sitemap_loc("https://shop.example/export.xml.gz") is True
    assert is_sitemap_loc("https://shop.example/products/1") is False


def test_a_public_token_is_not_an_operator_credential() -> None:
    none = SimpleNamespace(authentication="none", access_method="http_get", known_limitations=[])
    assert requires_operator_credential(none) is False
    searx = SimpleNamespace(
        authentication="api_key", access_method="self_hosted_api", known_limitations=[]
    )
    assert requires_operator_credential(searx) is False
    public = SimpleNamespace(
        authentication="api_key",
        access_method="official_api",
        known_limitations=["public key, no signup"],
    )
    assert requires_operator_credential(public) is False
    oauth = SimpleNamespace(
        authentication="oauth", access_method="official_api", known_limitations=[]
    )
    assert requires_operator_credential(oauth) is True
    assert "operator-provisioned credential" in credential_gate_note("eBay")


def test_host_variants_include_www_and_shop() -> None:
    assert host_variants("") == ()
    variants = host_variants("www.kind.co.jp")
    assert "kind.co.jp" in variants
    assert "shop.kind.co.jp" in variants
    shop = host_variants("shop.kind.co.jp")
    assert "www.kind.co.jp" in shop
    apex = host_variants("kind.co.jp")
    assert "www.kind.co.jp" in apex
    assert "shop.kind.co.jp" in apex


def test_robots_evidence_records_sitemaps_and_search_disallow() -> None:
    body = "User-agent: *\nDisallow: /search\nSitemap: https://shop.example/sitemap.xml\n"
    evidence = robots_evidence(origin="https://shop.example", body=body, status="ok")
    assert evidence["sitemaps"] == ["https://shop.example/sitemap.xml"]
    assert evidence["disallows_search"] is True
    assert evidence["robots_fetch_status"] == "ok"
    assert feed_path_blocked_reason("https://shop.example/search?q=x") == "robots Disallow: /search"
    assert feed_path_blocked_reason("https://shop.example/admin", ["/admin"]) == (
        "recorded disallowed path prefix"
    )
    assert feed_path_blocked_reason("https://shop.example/products/1") == "url is not admitted"


def test_catalog_match_requires_a_distinctive_term_hit() -> None:
    assert query_terms("the of") == []
    haystack = haystack_from_product(
        {
            "title": "Dior Homme General Army Trainer",
            "vendor": "Dior",
            "tags": ["runway", "2007"],
            "handle": "general-army-trainer",
            "variants": [{"price": "800"}],
            "images": [{"src": "https://img/1.jpg"}],
        }
    )
    assert match_score(["dior homme trainer"], haystack) > 0
    assert feed_text_matches(["unrelated widget"], haystack) is False
    assert match_score(["dior"], "") == 0
    listed = haystack_from_product({"title": "x", "tags": ["alpha", "beta"]})
    assert "alpha" in listed


def test_catalogue_pages_are_shared_across_sources() -> None:
    assert catalog_page_share(0, 9) == 0
    assert catalog_page_share(40, 0) == 0
    assert catalog_page_share(40, 9) == max(2, 40 // 9)
    assert remaining_page_budget(object()) == 0
    usage = SimpleNamespace(
        sealed=SimpleNamespace(ceiling=lambda name: 40 if name == "pages" else 0),
        used=lambda name: 10 if name == "pages" else 0,
    )
    assert remaining_page_budget(usage) == 30
    caps = catalog_caps_for_campaign(40, 9)
    assert caps.pages_per_source <= catalog_page_share(40, 9)
    assert caps.pages_per_campaign <= 40


def test_url_kind_follows_the_path_not_the_adapter_name() -> None:
    assert _kind_for_url("https://shop.example/sitemap.xml") is WorkKind.SITEMAP
    assert _kind_for_url("https://shop.example/search?q=dior") is WorkKind.QUERY
    assert _kind_for_url("https://shop.example/collections/trainers") is WorkKind.QUERY
    assert _kind_for_url("https://shop.example/products/1") is WorkKind.LISTING


# --- broker skip reasons, rate limit, frontier, live-check --------------------


def test_coverage_records_a_skip_reason_and_strategies() -> None:
    coverage = Coverage()
    coverage.record(
        "ebay",
        SourceOutcome.AUTH_REQUIRED,
        detail="missing EBAY_APP_ID",
        strategies=[{"name": "official_api", "status": "blocked"}],
    )
    coverage.record("kind", SourceOutcome.SEARCHED_MATCHES_FOUND)
    assert coverage.per_source["ebay"] == SourceOutcome.AUTH_REQUIRED.value
    assert coverage.details["ebay"] == "missing EBAY_APP_ID"
    assert coverage.strategies["ebay"][0]["name"] == "official_api"
    assert "kind" not in coverage.details


def test_health_skip_uses_the_last_outcome_before_the_state() -> None:
    last = SimpleNamespace(last_outcome=SourceOutcome.RATE_LIMITED, state=SourceHealthState.HEALTHY)
    assert _health_skip_outcome(last) is SourceOutcome.RATE_LIMITED
    disabled = SimpleNamespace(
        last_outcome=SourceOutcome.NOT_ATTEMPTED, state=SourceHealthState.POLICY_DISABLED
    )
    assert _health_skip_outcome(disabled) is SourceOutcome.BLOCKED_BY_POLICY
    down = SimpleNamespace(
        last_outcome=SourceOutcome.NOT_ATTEMPTED, state=SourceHealthState.UNAVAILABLE
    )
    assert _health_skip_outcome(down) is SourceOutcome.SOURCE_UNAVAILABLE
    blocked = SimpleNamespace(
        last_outcome=SourceOutcome.NOT_ATTEMPTED, state=SourceHealthState.BLOCKED
    )
    assert _health_skip_outcome(blocked) is SourceOutcome.BLOCKED_BY_ACCESS


def test_an_adapter_without_a_health_check_is_not_skipped() -> None:
    assert _adapter_unavailable_outcome("generic_page") is None


def test_a_disabled_bandwidth_limiter_never_delays() -> None:
    assert BandwidthLimiter(bytes_per_second=0).charge(10_000) == 0.0
    limiter = BandwidthLimiter(bytes_per_second=100)
    limiter.window_start = limiter.window_start - 2.0
    assert limiter.charge(40) == 0.0
    overflow = limiter.charge(80)
    assert overflow > 0


def test_frontier_priority_rises_with_value_and_falls_with_cost() -> None:
    cheap = compute_priority(expected_match_value=0.9, fetch_cost=0.1, policy_risk=0.0)
    costly = compute_priority(expected_match_value=0.2, fetch_cost=0.8, policy_risk=0.5)
    assert cheap > costly
    row = FrontierItem(
        run_id="r",
        work_key=work_key(source_id="kind", kind=WorkKind.LISTING.value, target="https://x"),
        search_id="s",
        source_id="kind",
        url="https://x",
        kind=WorkKind.LISTING,
        depth=1,
        priority=1.0,
        state=FrontierState.PENDING,
        payload={"k": 1},
    ).to_row()
    restored = FrontierItem.from_row({**row, "payload_json": json.dumps({"k": 1})})
    assert restored.payload == {"k": 1}
    assert MAX_DEPTH == 3


def test_liveness_does_not_call_a_block_sold() -> None:
    blocked = classify_liveness(
        http_status=401, body="", outcome=SourceOutcome.AUTH_REQUIRED
    )
    assert blocked.availability is Availability.UNKNOWN
    assert blocked.note == "blocked, not sold"
    gone = classify_liveness(http_status=410, body="", outcome=SourceOutcome.SEARCHED_NO_MATCH)
    assert gone.availability is Availability.REMOVED
    reserved = classify_liveness(
        http_status=200,
        body="This item is reserved for another buyer. " + ("x" * 300),
        outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
    )
    assert reserved.availability is Availability.RESERVED
    short = classify_liveness(
        http_status=200, body="ok", outcome=SourceOutcome.SEARCHED_MATCHES_FOUND
    )
    assert short.availability is Availability.UNKNOWN
    assert short.note == "body too short"
    discontinued = classify_liveness(
        http_status=200,
        body='<script type="application/ld+json">{"availability":"https://schema.org/Discontinued"}</script>',
        outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
    )
    assert discontinued.availability is Availability.REMOVED
    other = classify_liveness(
        http_status=503, body="", outcome=SourceOutcome.SOURCE_UNAVAILABLE
    )
    assert other.availability is Availability.UNKNOWN
    assert other.note == "unclassified"
    collapsed = classify_liveness(
        http_status=503, body="", outcome=SourceOutcome.SEARCHED_NO_MATCH
    )
    assert collapsed.outcome is SourceOutcome.UNMEASURABLE


def test_sensitive_headers_are_redacted() -> None:
    redacted = redact_headers(
        {"Authorization": "Bearer secret", "Cookie": "sid=1", "Accept": "text/html"}
    )
    assert redacted["Authorization"] == "[redacted]"
    assert redacted["Cookie"] == "[redacted]"
    assert redacted["Accept"] == "text/html"


def test_robots_wildcard_prefixes_match_and_empty_prefixes_do_not() -> None:
    assert path_matches_prefix("https://shop.example/search?q=x", [""]) is False
    assert path_matches_prefix("https://shop.example/search?q=x", ["/search*"]) is True
    assert path_matches_prefix("https://shop.example/products/1", ["/search*"]) is False
    body = "User-agent: Searcher\nCrawl-delay: 2.5\nUser-agent: *\nCrawl-delay: 1\n"
    assert extract_crawl_delay(body, "Searcher/0.1") == 2.5
    later = "User-agent: *\nDisallow: /x\nUser-agent: Searcher\nCrawl-delay: 4\n"
    assert extract_crawl_delay(later, "Searcher/0.1") == 4.0


def test_a_renderer_that_did_not_run_is_not_preferred() -> None:
    from searcher.contracts.models import FetchResult

    def doc(
        *,
        note: str | None,
        mode: FetchMode,
        outcome: SourceOutcome,
        body: bytes = b"x",
    ) -> FetchedDocument:
        return FetchedDocument(
            result=FetchResult(
                attempt_id="a",
                url="https://shop.example/p",
                outcome=outcome,
                mode=mode,
                classification_note=note,
            ),
            body=body,
            headers={},
            final_url="https://shop.example/p",
        )

    esc = Escalator.__new__(Escalator)
    found = SourceOutcome.SEARCHED_MATCHES_FOUND
    assert (
        esc._prefer_rendered(
            doc(note="browser extra unavailable", mode=FetchMode.BROWSER, outcome=found)
        )
        is False
    )
    assert (
        esc._prefer_rendered(
            doc(
                note=None,
                mode=FetchMode.BROWSER,
                outcome=SourceOutcome.NETWORK_FAILED,
                body=b"",
            )
        )
        is False
    )
    assert (
        esc._prefer_rendered(doc(note=None, mode=FetchMode.LIGHT_RENDER, outcome=found))
        is True
    )
    assert esc._prefer_rendered(doc(note=None, mode=FetchMode.HTTP, outcome=found)) is False


def test_escalate_and_liveness_are_the_named_extraction_plan_exports() -> None:
    assert escalate_mod.Escalator is Escalator
    assert liveness_mod.classify_liveness is classify_liveness
    assert AdmissionDecision(True, SourceOutcome.NOT_ATTEMPTED, "ok").allowed is True
    cache = RobotsCache()
    assert cache.get_cached("https://missing.example") is None
