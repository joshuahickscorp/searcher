"""Warm local index: put/get, versioned keys, inverted text, compact descriptors."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from searcher.contracts.models import ItemHypothesis, ListingCandidate
from searcher.core.errors import CrossCampaignAccessError
from searcher.core.ids import sha256_hex
from searcher.core.time import format_utc, parse_utc
from searcher.deduplication.images import content_fingerprint
from searcher.index.keys import (
    CacheVersions,
    cache_key,
    versions_from_settings,
    with_parameters,
)
from searcher.index.sanitize import (
    hypothesis_digest_payload,
    listing_content_digest,
    public_listing_payload,
    refuse_private,
)
from searcher.index.text import (
    field_terms,
    listing_description_terms,
    listing_title_terms,
    term_frequencies,
)
from searcher.index.vectors import (
    cosine,
    hashed_text_vector,
    pack_descriptor,
    unpack_descriptor,
)
from searcher.storage.repositories import Repositories


@dataclass(frozen=True, slots=True)
class IndexHit:
    listing_key: str
    canonical_url: str
    content_digest: str
    payload: dict[str, Any]
    last_checked_at: str
    availability: str
    cluster_key: str | None
    image_digests: list[str]
    perceptual_hashes: list[str]
    term_score: float
    descriptor_score: float
    source_adapter: str


@dataclass
class IndexEvidence:
    evidence_key: str
    listing_key: str
    hypothesis_digest: str
    item_match_mean: float
    item_match_lower: float
    item_match_upper: float
    authenticity_mean: float
    authenticity_lower: float
    authenticity_upper: float
    completeness: float
    destination_verified: bool
    hard_vetoes: list[str] = field(default_factory=list)
    match_payload: dict[str, Any] | None = None
    authenticity_payload: dict[str, Any] | None = None


class WarmIndex:
    """Installation-local cache of public listing work. Not a campaign store."""

    def __init__(self, repos: Repositories) -> None:
        self.repos = repos
        self.tables = repos.index

    def put_listing(
        self,
        candidate: ListingCandidate,
        versions: CacheVersions,
        *,
        descriptors: dict[str, list[float]] | None = None,
        extra_ocr: list[str] | None = None,
    ) -> str:
        payload = public_listing_payload(candidate)
        digest = listing_content_digest(candidate)
        key = cache_key(content_digest=digest, versions=versions)
        title_terms = listing_title_terms(candidate)
        desc_terms = listing_description_terms(candidate)
        ocr_terms = list(extra_ocr or [])
        ocr_terms.extend(field_terms(*ocr_terms))
        image_digests = [img.content_digest or "" for img in candidate.images if img.content_digest]
        hashes = [img.perceptual_hash or "" for img in candidate.images if img.perceptual_hash]
        self.tables.upsert_listing(
            {
                "listing_key": key,
                "canonical_url": candidate.canonical_url,
                "content_digest": digest,
                "adapter_version": versions.adapter_version,
                "model_version": versions.model_version,
                "parameters": versions.parameters,
                "schema_version": versions.schema_version,
                "policy_version": versions.policy_version,
                "source_adapter": candidate.source_adapter,
                "source_listing_id": candidate.source_listing_id,
                "cluster_key": candidate.cluster_id,
                "availability": candidate.availability.value,
                "last_checked_at": format_utc(candidate.last_checked_at),
                "first_seen_at": format_utc(candidate.first_seen_at),
                "title_norm": " ".join(title_terms),
                "description_norm": " ".join(desc_terms),
                "ocr_terms": json.dumps(ocr_terms, sort_keys=True),
                "image_digests": image_digests,
                "perceptual_hashes": hashes,
                "payload": payload,
            }
        )
        term_rows: list[tuple[str, str, int]] = []
        for field_name, terms in (
            ("title", title_terms),
            ("description", desc_terms),
            ("ocr", ocr_terms),
        ):
            for term, tf in term_frequencies(terms).items():
                term_rows.append((term, field_name, tf))
        self.tables.replace_terms(key, term_rows)
        packed: list[tuple[str, int, bytes, str]] = []
        text_vec = hashed_text_vector(title_terms + desc_terms + ocr_terms)
        packed.append(("text", len(text_vec), pack_descriptor(text_vec), "hashed_text"))
        for digest_id, values in (descriptors or {}).items():
            packed.append((digest_id, len(values), pack_descriptor(values), "histogram"))
        self.tables.replace_descriptors(key, packed)
        return key

    def get(
        self,
        *,
        content_digest: str,
        versions: CacheVersions,
    ) -> dict[str, Any] | None:
        key = cache_key(content_digest=content_digest, versions=versions)
        return self.tables.get_listing(key)

    def get_by_url(self, canonical_url: str, versions: CacheVersions) -> dict[str, Any] | None:
        return self.tables.get_listing_by_url(
            canonical_url,
            adapter_version=versions.adapter_version,
            model_version=versions.model_version,
            parameters=versions.parameters,
            schema_version=versions.schema_version,
            policy_version=versions.policy_version,
        )

    def search(
        self,
        terms: list[str],
        versions: CacheVersions,
        *,
        query_descriptor: list[float] | None = None,
        limit: int = 50,
    ) -> list[IndexHit]:
        rows = self.tables.search_listings(
            terms,
            adapter_version=versions.adapter_version,
            model_version=versions.model_version,
            parameters=versions.parameters,
            schema_version=versions.schema_version,
            policy_version=versions.policy_version,
            limit=limit,
        )
        hits: list[IndexHit] = []
        seen_urls: set[str] = set()
        for row in rows:
            url = str(row["canonical_url"])
            if url in seen_urls:
                continue
            seen_urls.add(url)
            desc_score = 0.0
            if query_descriptor:
                best = 0.0
                for desc in self.tables.list_descriptors(str(row["listing_key"])):
                    vector = unpack_descriptor(desc["descriptor"])
                    best = max(best, cosine(query_descriptor, vector))
                desc_score = best
            hits.append(
                IndexHit(
                    listing_key=str(row["listing_key"]),
                    canonical_url=url,
                    content_digest=str(row["content_digest"]),
                    payload=dict(row["payload"]),
                    last_checked_at=str(row["last_checked_at"]),
                    availability=str(row["availability"]),
                    cluster_key=row.get("cluster_key"),
                    image_digests=list(row.get("image_digests") or []),
                    perceptual_hashes=list(row.get("perceptual_hashes") or []),
                    term_score=float(row.get("term_score") or 0.0),
                    descriptor_score=desc_score,
                    source_adapter=str(row.get("source_adapter") or ""),
                )
            )
        if query_descriptor:
            hits.sort(key=lambda hit: (hit.term_score, hit.descriptor_score), reverse=True)
        return hits

    def put_evidence(
        self,
        *,
        listing_key: str,
        hypothesis_digest: str,
        versions: CacheVersions,
        item_match_mean: float,
        item_match_lower: float,
        item_match_upper: float,
        authenticity_mean: float,
        authenticity_lower: float,
        authenticity_upper: float,
        completeness: float,
        destination_verified: bool,
        hard_vetoes: list[str],
        match_payload: dict[str, Any] | None,
        authenticity_payload: dict[str, Any] | None,
    ) -> str:
        if item_match_lower > item_match_mean or authenticity_lower > authenticity_mean:
            raise ValueError("index evidence cannot store inverted intervals")
        ev_versions = with_parameters(versions, hypothesis_digest)
        key = cache_key(content_digest=listing_key, versions=ev_versions)
        if match_payload is not None:
            refuse_private(match_payload)
        if authenticity_payload is not None:
            refuse_private(authenticity_payload)
        self.tables.upsert_evidence(
            {
                "evidence_key": key,
                "listing_key": listing_key,
                "hypothesis_digest": hypothesis_digest,
                "adapter_version": ev_versions.adapter_version,
                "model_version": ev_versions.model_version,
                "parameters": ev_versions.parameters,
                "schema_version": ev_versions.schema_version,
                "policy_version": ev_versions.policy_version,
                "item_match_mean": item_match_mean,
                "item_match_lower": item_match_lower,
                "item_match_upper": item_match_upper,
                "authenticity_mean": authenticity_mean,
                "authenticity_lower": authenticity_lower,
                "authenticity_upper": authenticity_upper,
                "completeness": completeness,
                "destination_verified": destination_verified,
                "hard_vetoes": hard_vetoes,
                "match_payload": match_payload,
                "authenticity_payload": authenticity_payload,
            }
        )
        return key

    def get_evidence(
        self,
        listing_key: str,
        hypothesis_digest: str,
        versions: CacheVersions,
    ) -> IndexEvidence | None:
        ev_versions = with_parameters(versions, hypothesis_digest)
        key = cache_key(content_digest=listing_key, versions=ev_versions)
        row = self.tables.get_evidence(key)
        if row is None:
            return None
        return IndexEvidence(
            evidence_key=str(row["evidence_key"]),
            listing_key=str(row["listing_key"]),
            hypothesis_digest=str(row["hypothesis_digest"]),
            item_match_mean=float(row["item_match_mean"] or 0.0),
            item_match_lower=float(row["item_match_lower"] or 0.0),
            item_match_upper=float(row["item_match_upper"] or 0.0),
            authenticity_mean=float(row["authenticity_mean"] or 0.0),
            authenticity_lower=float(row["authenticity_lower"] or 0.0),
            authenticity_upper=float(row["authenticity_upper"] or 0.0),
            completeness=float(row["completeness"] or 0.0),
            destination_verified=bool(row["destination_verified"]),
            hard_vetoes=list(row.get("hard_vetoes") or []),
            match_payload=row.get("match_payload"),
            authenticity_payload=row.get("authenticity_payload"),
        )

    def record_query(
        self,
        *,
        source_id: str,
        query_text: str,
        versions: CacheVersions,
        content_digest: str | None = None,
        pages: int = 0,
    ) -> str:
        query_norm = " ".join(field_terms(query_text))
        ior_versions = with_parameters(versions, f"ior:{source_id}")
        digest = content_digest or sha256_hex(query_norm.encode("utf-8"))
        # IOR identity is source + normalized query + versions, not the result digest.
        identity = cache_key(content_digest=f"{source_id}|{query_norm}", versions=ior_versions)
        self.tables.upsert_query(
            {
                "ior_key": identity,
                "source_id": source_id,
                "query_norm": query_norm,
                "adapter_version": ior_versions.adapter_version,
                "model_version": ior_versions.model_version,
                "parameters": ior_versions.parameters,
                "schema_version": ior_versions.schema_version,
                "policy_version": ior_versions.policy_version,
                "content_digest": digest,
                "pages": pages,
            }
        )
        return identity

    def query_already_run(
        self,
        *,
        source_id: str,
        query_text: str,
        versions: CacheVersions,
        content_digest: str | None = None,
    ) -> bool:
        query_norm = " ".join(field_terms(query_text))
        ior_versions = with_parameters(versions, f"ior:{source_id}")
        identity = cache_key(content_digest=f"{source_id}|{query_norm}", versions=ior_versions)
        row = self.tables.get_query(identity)
        if row is None:
            return False
        stored = row.get("content_digest")
        return content_digest is None or stored in {None, content_digest}

    def count(self) -> int:
        return self.tables.count_listings()

    def campaign_private_artifacts(self, search_id: str) -> list[Any]:
        raise CrossCampaignAccessError(
            "the warm index does not store or expose campaign-private artifacts",
            search_id=search_id,
        )

    def put_private(self, search_id: str, _name: str, _payload: bytes) -> None:
        raise CrossCampaignAccessError(
            "the warm index refuses campaign-private artifacts",
            search_id=search_id,
        )


def hypothesis_digest(hypothesis: ItemHypothesis) -> str:
    return hypothesis_digest_payload(
        category=hypothesis.category,
        brand=hypothesis.brand.value,
        model=hypothesis.model_name.value,
        line=hypothesis.line.value,
        year=hypothesis.year.value,
        colourway=hypothesis.colourway.value,
        aliases=[alias.alias for alias in hypothesis.aliases],
    )


def descriptor_from_bytes(data: bytes) -> list[float] | None:
    """Colour histogram when the bytes are an image; otherwise a content fingerprint."""
    try:
        from searcher.reference.imaging import colour_histogram

        return colour_histogram(data)
    except Exception:
        bits = content_fingerprint(data)
        if not bits:
            return None
        return hashed_text_vector([bits[i : i + 4] for i in range(0, len(bits), 4)])


def parse_listing(payload: dict[str, Any]) -> ListingCandidate:
    return ListingCandidate.model_validate(payload)


__all__ = [
    "IndexEvidence",
    "IndexHit",
    "WarmIndex",
    "descriptor_from_bytes",
    "hypothesis_digest",
    "parse_listing",
    "parse_utc",
    "versions_from_settings",
]
