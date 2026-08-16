"""URL-family keys: canonical URL, listing id, host+id."""

from __future__ import annotations

from searcher.contracts.models import ListingCandidate
from searcher.normalization.url import canonicalize_url, extract_listing_id, host_of


def url_cluster_key(candidate: ListingCandidate) -> str:
    canon = canonicalize_url(candidate.canonical_url)
    listing_id = candidate.source_listing_id or extract_listing_id(canon)
    if listing_id:
        return f"{candidate.source_adapter}:{listing_id}"
    return f"url:{canon}"


def listing_id_key(url: str, source_id: str) -> str | None:
    listing_id = extract_listing_id(url)
    if listing_id:
        return f"{source_id}:{listing_id}"
    return None


def host_path_key(url: str) -> str:
    return f"{host_of(url)}|{canonicalize_url(url)}"
