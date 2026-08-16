"""§14.2 SourceManifest construction. Adapters declare this; they do not invent policy."""

from __future__ import annotations

from searcher.contracts.enums import FetchMode, SourceAdmission
from searcher.contracts.models import RatePolicy, SourceManifest


def build_manifest(
    *,
    source_id: str,
    adapter: str,
    domain: str,
    access_method: str,
    admission_status: SourceAdmission,
    allowed_use: str,
    name: str | None = None,
    version: str = "1.0.0",
    source_class: str = "general_web",
    capabilities: list[str] | None = None,
    public_access: bool = True,
    authentication: str = "none",
    robots_policy: str = "",
    terms_review_status: SourceAdmission | None = None,
    rate_policy: RatePolicy | None = None,
    fetch_modes: list[FetchMode] | None = None,
    fields: list[str] | None = None,
    retention: str = "temporary",
    thumbnail_policy: str = "link-only",
    publication_boundary: str = "link-only",
    refresh_policy: str = "on-demand",
    rights_review_status: str = "research-2026-08-16",
    retention_policy: dict[str, str] | None = None,
    health_check: str = "get_home",
    known_limitations: list[str] | None = None,
    languages: list[str] | None = None,
    enabled: bool = True,
    disallowed_path_prefixes: list[str] | None = None,
    open_question: str | None = None,
    robots_url: str | None = None,
    sitemap_urls: list[str] | None = None,
    listing_path_prefixes: list[str] | None = None,
) -> SourceManifest:
    return SourceManifest(
        source_id=source_id,
        adapter=adapter,
        domain=domain,
        access_method=access_method,
        admission_status=admission_status,
        allowed_use=allowed_use,
        name=name or source_id,
        version=version,
        source_class=source_class,
        capabilities=capabilities or ["listing_fetch"],
        public_access=public_access,
        authentication=authentication,
        robots_policy=robots_policy,
        terms_review_status=terms_review_status or admission_status,
        rate_policy=rate_policy or RatePolicy(requests_per_minute=20, burst=2, concurrent=1),
        fetch_modes=fetch_modes or [FetchMode.CACHE, FetchMode.HTTP],
        fields=fields or ["title", "url", "price", "currency", "availability", "images"],
        retention=retention,
        thumbnail_policy=thumbnail_policy,
        publication_boundary=publication_boundary,
        refresh_policy=refresh_policy,
        rights_review_status=rights_review_status,
        retention_policy=retention_policy or {"metadata": "campaign", "body": "transient"},
        health_check=health_check,
        known_limitations=known_limitations or [],
        languages=languages or ["en"],
        enabled=enabled,
        disallowed_path_prefixes=disallowed_path_prefixes or [],
        open_question=open_question,
        robots_url=robots_url,
        sitemap_urls=sitemap_urls or [],
        listing_path_prefixes=listing_path_prefixes or [],
    )


def validate_manifest(manifest: SourceManifest) -> SourceManifest:
    if not manifest.source_id or not manifest.adapter or not manifest.domain:
        raise ValueError("manifest requires source_id, adapter, and domain")
    if not manifest.access_method:
        raise ValueError("manifest requires access_method")
    if manifest.admission_status is SourceAdmission.BLOCKED and manifest.enabled:
        raise ValueError(f"{manifest.source_id} is blocked and cannot be enabled")
    return manifest
