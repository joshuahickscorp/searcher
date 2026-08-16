# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.liveness.classify skeleton (marketplace markers, not job CTAs)
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Liveness is one GET of the item URL already in hand."""

from __future__ import annotations

import re

from searcher.contracts.enums import Availability, SourceOutcome
from searcher.contracts.models import ListingCandidate, LiveStatus, SourceManifest
from searcher.core.time import utc_now
from searcher.sources.fetch_modes import Escalator
from searcher.sources.statuses import classify_http

SOLD_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bsold\b",
        r"this listing has ended",
        r"no longer available",
        r"売り切れ",
        r"売却済",
        r"落札済",
        r"판매완료",
        r"판매 완료",
        r"已售",
        r"卖完",
        r"\bvendu\b",
        r"\bvenduto\b",
        r"продано",
        r"sold out",
    )
]
RESERVED_PATTERNS = [
    re.compile(p, re.I)
    for p in (r"\breserved\b", r"取引中", r"仮押さえ", r"예약", r"réservé", r"riservato")
]
MIN_CONTENT_CHARS = 300
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_SCHEMA_AVAIL = re.compile(
    r"schema\.org/(InStock|OutOfStock|SoldOut|LimitedAvailability|"
    r"OnlineOnly|PreOrder|Discontinued|InStoreOnly)",
    re.I,
)
_SCHEMA_LIVE = frozenset(
    {"instock", "limitedavailability", "onlineonly", "preorder", "instoreonly"}
)
_SCHEMA_SOLD = frozenset({"outofstock", "soldout"})
_SCHEMA_REMOVED = frozenset({"discontinued"})


def _visible_body(body: str) -> str:
    """Drop theme JS/CSS. Shopify pages ship unused 'Sold out' i18n in <script>."""
    return _SCRIPT_OR_STYLE.sub(" ", body)


def _schema_availability(body: str) -> Availability | None:
    match = _SCHEMA_AVAIL.search(body)
    if match is None:
        return None
    token = match.group(1).lower()
    if token in _SCHEMA_LIVE:
        return Availability.LIVE
    if token in _SCHEMA_SOLD:
        return Availability.SOLD
    if token in _SCHEMA_REMOVED:
        return Availability.REMOVED
    return None


def classify_liveness(*, http_status: int | None, body: str, outcome: SourceOutcome) -> LiveStatus:
    now = utc_now()
    if outcome in {
        SourceOutcome.BLOCKED_BY_ACCESS,
        SourceOutcome.AUTH_REQUIRED,
        SourceOutcome.RATE_LIMITED,
        SourceOutcome.BLOCKED_BY_POLICY,
    }:
        return LiveStatus(
            availability=Availability.UNKNOWN,
            checked_at=now,
            http_status=http_status,
            outcome=outcome,
            note="blocked, not sold",
        )
    if http_status in {404, 410}:
        return LiveStatus(
            availability=Availability.REMOVED,
            checked_at=now,
            http_status=http_status,
            outcome=SourceOutcome.SEARCHED_NO_MATCH,
            note="http gone",
        )
    if http_status == 200:
        structured = _schema_availability(body)
        if structured is Availability.LIVE:
            return LiveStatus(
                availability=Availability.LIVE,
                checked_at=now,
                destination_verified=True,
                http_status=200,
                outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                note="schema.org InStock",
            )
        if structured is Availability.SOLD:
            return LiveStatus(
                availability=Availability.SOLD,
                checked_at=now,
                http_status=200,
                outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                note="schema.org OutOfStock",
            )
        if structured is Availability.REMOVED:
            return LiveStatus(
                availability=Availability.REMOVED,
                checked_at=now,
                http_status=200,
                outcome=SourceOutcome.SEARCHED_NO_MATCH,
                note="schema.org Discontinued",
            )
        visible = _visible_body(body)
        for pattern in SOLD_PATTERNS:
            if pattern.search(visible):
                return LiveStatus(
                    availability=Availability.SOLD,
                    checked_at=now,
                    http_status=200,
                    outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                    note=f"sold marker {pattern.pattern}",
                )
        for pattern in RESERVED_PATTERNS:
            if pattern.search(visible):
                return LiveStatus(
                    availability=Availability.RESERVED,
                    checked_at=now,
                    http_status=200,
                    outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                    note="reserved marker",
                )
        if len(visible.strip()) < MIN_CONTENT_CHARS:
            return LiveStatus(
                availability=Availability.UNKNOWN,
                checked_at=now,
                http_status=200,
                outcome=SourceOutcome.UNMEASURABLE,
                note="body too short",
            )
        return LiveStatus(
            availability=Availability.LIVE,
            checked_at=now,
            destination_verified=True,
            http_status=200,
            outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
            note="200 without sold marker",
        )
    return LiveStatus(
        availability=Availability.UNKNOWN,
        checked_at=now,
        http_status=http_status,
        outcome=outcome
        if outcome is not SourceOutcome.SEARCHED_NO_MATCH
        else SourceOutcome.UNMEASURABLE,  # noqa: E501
        note="unclassified",
    )


def check_candidate(
    candidate: ListingCandidate,
    manifest: SourceManifest,
    escalator: Escalator,
) -> tuple[ListingCandidate, LiveStatus]:
    doc = escalator.fetch(candidate.canonical_url, manifest, source_id=manifest.source_id)
    outcome = doc.result.outcome
    if outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
        outcome = classify_http(doc.result.http_status, body=doc.body)
    status = classify_liveness(
        http_status=doc.result.http_status,
        body=doc.body.decode("utf-8", errors="replace"),
        outcome=outcome,
    )
    updated = candidate.model_copy(
        update={
            "availability": status.availability,
            "last_checked_at": status.checked_at,
            "explanation": candidate.explanation.model_copy(
                update={"live_status": status.availability, "last_checked_at": status.checked_at}
            ),
        }
    )
    return updated, status
