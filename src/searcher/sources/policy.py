"""§14.5 recorded per-source decisions. Technical access is not permission."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.enums import SourceAdmission, SourceFamily
from searcher.contracts.models import SourceManifest


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    source_id: str
    search: bool
    page_fetch: bool
    render: bool
    image_retrieval: bool
    cache: bool
    persistent_metadata: bool
    thumbnail_publication: bool
    refresh_frequency: str
    admission: SourceAdmission
    notes: str = ""
    open_question: str | None = None
    source_family: SourceFamily = SourceFamily.LEGITIMATE


# Derived from docs/sources/SOURCE_RESEARCH_2026-08-16.md. Do not invent.
RECORDED_POLICIES: dict[str, SourcePolicy] = {
    "searx": SourcePolicy(
        "searx",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Own SearxNG instance only. Public instances are not the production path.",
    ),
    "wikimedia": SourcePolicy(
        "wikimedia",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=True,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=True,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Action API + article HTML. Honour UA, maxlag, serial requests.",
    ),
    "marginalia": SourcePolicy(
        "marginalia",
        search=True,
        page_fetch=False,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="CC-BY-NC-SA 4.0 default. public key is rate-limited.",
    ),
    "archive_org": SourcePolicy(
        "archive_org",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="never-as-live",
        admission=SourceAdmission.ADMITTED,
        notes="Historical only. Never treat a capture as currently live.",
    ),
    "openverse": SourcePolicy(
        "openverse",
        search=True,
        page_fetch=False,
        render=False,
        image_retrieval=True,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=True,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="CC images for identity, not marketplace listings.",
    ),
    "the_realreal": SourcePolicy(
        "the_realreal",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Item pages and sitemap. Stay off ?*before= and ?*after= pagination.",
    ),
    "rebag": SourcePolicy(
        "rebag",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Disallow /digital_certificate/. Product pages allowed.",
    ),
    "komehyo": SourcePolicy(
        "komehyo",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Open robots. Sitemap-first.",
    ),
    "kind": SourcePolicy(
        "kind",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Product and collection pages. /search is Disallow.",
    ),
    "byronesque": SourcePolicy(
        "byronesque",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="Disallow /wp-admin/ only.",
    ),
    "heroine": SourcePolicy(
        "heroine",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.ADMITTED,
        notes="shopheroine.com robots empty Disallow. Storefront identity is an open question.",
        open_question="Is shopheroine.com the intended Heroine storefront?",
    ),
    "ebay": SourcePolicy(
        "ebay",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="api-ttl",
        admission=SourceAdmission.ADMITTED,
        notes="Official Browse API only. Web /sch/ is not admissible.",
    ),
    "etsy": SourcePolicy(
        "etsy",
        search=True,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="api-6h",
        admission=SourceAdmission.ADMITTED,
        notes="Official Open API v3 only. Screen-scraping is not allowed.",
    ),
    "vinted": SourcePolicy(
        "vinted",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Content-Signal search=yes, ai-train=no. Disabled pending the open question.",
        open_question="Does part-level comparison count as search or ai-input?",
    ),
    "mercari_jp": SourcePolicy(
        "mercari_jp",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Item pages not disallowed. /v1/ /v2/ are. ToS of automated access unverified.",
        open_question="Terms of automated access were not fetched on 2026-08-16.",
    ),
    "yahoo_auctions": SourcePolicy(
        "yahoo_auctions",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Item pages. /closedsearch and member paths Disallow.",
        open_question="Item HTML fetchability without login was not confirmed.",
    ),
    "buyee": SourcePolicy(
        "buyee",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Public catalog only. Link, never bid. No /api/v1/ or /internalapi/.",
        open_question="Full Terms of Use beyond the caution page were not fetched.",
    ),
    "bunjang": SourcePolicy(
        "bunjang",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Public pages allowed except login/apps/talk. JS completeness unverified.",
        open_question="Is a listing complete without JS?",
    ),
    "duckduckgo": SourcePolicy(
        "duckduckgo",
        search=True,
        page_fetch=False,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=False,
        thumbnail_publication=False,
        refresh_frequency="transient",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="html.duckduckgo.com Allow: /. ToS for automated commercial reuse unverified.",
        open_question="DDG ToS for automated commercial reuse were not fetched.",
    ),
    "ssense": SourcePolicy(
        "ssense",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes="Product pages only. Never ?q= or /api/. Disabled pending review.",
        open_question="JSON-LD and sold markers unverified.",
        source_family=SourceFamily.LEGITIMATE,
    ),
    "depop": SourcePolicy(
        "depop",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "Browser-rendered robots.txt on 2026-08-16 is a real file: "
            "Disallow /search/*, magic-link, selling/sold/likes, and filter queries. "
            "/products/ is allowed. Plain HTTP robots and item URLs returned 403. "
            "Browser placeholder item returned 404 without a challenge. "
            "Disabled pending review."
        ),
        open_question="Is automated access of /products/ permitted given the 403 on honest HTTP?",
        source_family=SourceFamily.LEGITIMATE,
    ),
    "grailed": SourcePolicy(
        "grailed",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "robots.txt is fetchable over HTTP and browser (2026-08-16). "
            "Disallow /search, /listings/*/edit, account and checkout paths. "
            "/listings/<id> is allowed. Listing pages return a Cloudflare "
            "Just a moment challenge. Disabled pending review."
        ),
        open_question="Can a listing page be read without a Cloudflare challenge?",
        source_family=SourceFamily.LEGITIMATE,
    ),
    "vestiaire": SourcePolicy(
        "vestiaire",
        search=False,
        page_fetch=True,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "HTTP robots.txt is a Cloudflare interstitial (2026-08-16). "
            "Browser-rendered robots.txt is real: Disallow /admin/ /api/ /members/ "
            "checkout. HTTP listing fetches are challenged. Disabled pending review."
        ),
        open_question="Can robots.txt and a listing page be fetched over honest HTTP?",
        source_family=SourceFamily.LEGITIMATE,
    ),
    "taobao": SourcePolicy(
        "taobao",
        search=False,
        page_fetch=False,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "robots.txt (HTTP and browser, 2026-08-16): Allow /$ and /list/*; "
            "Disallow /*?*. Typical item URLs carry query strings and are covered "
            "by that Disallow. Disabled pending review."
        ),
        open_question="Is there an admitted item-page path that does not require login?",
        source_family=SourceFamily.REPLICA,
    ),
    "weidian": SourcePolicy(
        "weidian",
        search=False,
        page_fetch=False,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "robots.txt still redirected to h5.weidian.com/m/abnormal/404.html "
            "over HTTP and browser on 2026-08-16. No usable robots file. "
            "Disabled pending review."
        ),
        open_question="Is there a fetchable robots.txt and an admitted public listing path?",
        source_family=SourceFamily.REPLICA,
    ),
    "yupoo": SourcePolicy(
        "yupoo",
        search=False,
        page_fetch=False,
        render=False,
        image_retrieval=False,
        cache=False,
        persistent_metadata=True,
        thumbnail_publication=False,
        refresh_frequency="on-demand",
        admission=SourceAdmission.REVIEW_REQUIRED,
        notes=(
            "www.yupoo.com/robots.txt and /albums/ redirected to x.yupoo.com/404 "
            "over HTTP and browser on 2026-08-16. No robots file. Disabled pending review."
        ),
        open_question=(
            "What does a real robots.txt allow, and is album HTML an admitted listing path?"
        ),
        source_family=SourceFamily.REPLICA,
    ),
}


def policy_for(source_id: str) -> SourcePolicy | None:
    return RECORDED_POLICIES.get(source_id)


def policy_from_manifest(manifest: SourceManifest) -> SourcePolicy:
    recorded = RECORDED_POLICIES.get(manifest.source_id)
    if recorded is not None:
        return recorded
    return SourcePolicy(
        source_id=manifest.source_id,
        search="text_search" in manifest.capabilities,
        page_fetch="listing_fetch" in manifest.capabilities,
        render=any(m.value == "browser" for m in manifest.fetch_modes),
        image_retrieval="image_search" in manifest.capabilities,
        cache=True,
        persistent_metadata=True,
        thumbnail_publication=manifest.thumbnail_policy != "none",
        refresh_frequency=manifest.refresh_policy,
        admission=manifest.admission_status,
        notes="; ".join(manifest.known_limitations),
        open_question=manifest.open_question,
        source_family=manifest.source_family,
    )


@dataclass(slots=True)
class PolicyTable:
    policies: dict[str, SourcePolicy] = field(default_factory=lambda: dict(RECORDED_POLICIES))

    def get(self, source_id: str) -> SourcePolicy | None:
        return self.policies.get(source_id)
