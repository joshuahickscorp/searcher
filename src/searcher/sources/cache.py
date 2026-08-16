"""Body-inclusive response cache. A 304 must replay the stored body."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.core.ids import sha256_hex
from searcher.core.time import format_utc, utc_now
from searcher.evidence.content_store import ContentStore
from searcher.normalization.url import canonicalize_url
from searcher.storage.repositories import Repositories


@dataclass(frozen=True, slots=True)
class CachedResponse:
    url_canonical: str
    body: bytes
    etag: str | None
    last_modified: str | None
    content_digest: str
    content_type: str | None
    fetched_at: str


class ResponseCache:
    def __init__(self, repos: Repositories, store: ContentStore) -> None:
        self.repos = repos
        self.store = store

    def get(self, url: str) -> CachedResponse | None:
        canon = canonicalize_url(url)
        row = self.repos.get_response_cache(canon)
        if row is None:
            return None
        body = self.store.get(str(row["content_digest"]))
        headers_raw = row.get("headers_json") or "{}"
        import json

        headers = json.loads(headers_raw) if isinstance(headers_raw, str) else {}
        return CachedResponse(
            url_canonical=canon,
            body=body,
            etag=row.get("etag"),
            last_modified=row.get("last_modified"),
            content_digest=str(row["content_digest"]),
            content_type=headers.get("content-type") if isinstance(headers, dict) else None,
            fetched_at=str(row["fetched_at"]),
        )

    def put(
        self,
        url: str,
        body: bytes,
        *,
        etag: str | None,
        last_modified: str | None,
        content_type: str | None,
        policy: str = "transient",
    ) -> CachedResponse:
        canon = canonicalize_url(url)
        digest = sha256_hex(body)
        self.store.put_bytes(body, zone="temporary")
        headers = {"content-type": content_type or ""}
        fetched = format_utc(utc_now())
        self.repos.upsert_response_cache(
            {
                "url_canonical": canon,
                "etag": etag,
                "last_modified": last_modified,
                "content_digest": digest,
                "body_ref": digest,
                "fetched_at": fetched,
                "policy": policy,
                "headers": headers,
            }
        )
        return CachedResponse(
            url_canonical=canon,
            body=body,
            etag=etag,
            last_modified=last_modified,
            content_digest=digest,
            content_type=content_type,
            fetched_at=fetched,
        )
