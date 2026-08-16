"""§17 listing-family clustering and representative selection."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.enums import Availability
from searcher.contracts.models import ListingCandidate
from searcher.core.ids import new_id
from searcher.deduplication.images import image_family_id
from searcher.deduplication.text import jaccard
from searcher.deduplication.urls import url_cluster_key
from searcher.evidence.independence import independent_family_count
from searcher.evidence.records import EvidenceRecord


@dataclass
class Cluster:
    cluster_id: str
    member_ids: list[str]
    representative_id: str
    reason: str
    family_kind: str


@dataclass
class DedupeResult:
    clusters: list[Cluster]
    representatives: list[ListingCandidate]
    before: int
    after: int
    exact_url_dupes: int
    image_family_dupes: int
    text_dupes: int
    savings: dict[str, int] = field(default_factory=dict)


def _title_of(candidate: ListingCandidate) -> str:
    if candidate.title and candidate.title.value is not None:
        return str(candidate.title.value)
    return ""


def _score(candidate: ListingCandidate) -> tuple[int, int, int, str]:
    live = 1 if candidate.availability is Availability.LIVE else 0
    images = len(candidate.images)
    fields = sum(
        1
        for value in (
            candidate.title,
            candidate.price_original,
            candidate.size_original,
            candidate.currency_original,
        )
        if value
    )
    return (live, images, fields, candidate.canonical_url)


def cluster_candidates(candidates: list[ListingCandidate]) -> DedupeResult:
    by_url: dict[str, list[ListingCandidate]] = {}
    for candidate in candidates:
        by_url.setdefault(url_cluster_key(candidate), []).append(candidate)
    assigned: dict[str, str] = {}
    clusters: list[Cluster] = []
    exact = 0
    image_dupes = 0
    text_dupes = 0
    for _key, group in by_url.items():
        if len(group) > 1:
            exact += len(group) - 1
        cid = new_id()
        ordered = sorted(group, key=_score, reverse=True)
        clusters.append(
            Cluster(
                cluster_id=cid,
                member_ids=[c.candidate_id for c in ordered],
                representative_id=ordered[0].candidate_id,
                reason="canonical_url_or_listing_id",
                family_kind="url",
            )
        )
        for member in group:
            assigned[member.candidate_id] = cid
    # Merge leftover singles that share an image family or near-duplicate text.
    leftovers = [c for c in candidates if assigned.get(c.candidate_id)]
    # Second pass: image-family merge of existing clusters.
    # Distinct listing IDs stay independent even if they share a placeholder image.
    family_to_cluster: dict[str, str] = {}
    listing_of: dict[str, str] = {c.candidate_id: (c.source_listing_id or "") for c in leftovers}
    for candidate in leftovers:
        families = {image_family_id(image) for image in candidate.images if image.remote_url}
        cid = assigned[candidate.candidate_id]
        for family in families:
            other = family_to_cluster.get(family)
            if other and other != cid:
                left_id = listing_of.get(candidate.candidate_id, "")
                right_members = [mid for mid, cl in assigned.items() if cl == other]
                right_ids = {listing_of.get(mid, "") for mid in right_members}
                if left_id and right_ids and left_id not in right_ids:
                    continue
                image_dupes += 1
                _merge(clusters, assigned, cid, other)
                cid = assigned[candidate.candidate_id]
            family_to_cluster[family] = cid
    # Text merge only when listing IDs are missing or identical.
    reps = {c.cluster_id: _pick(candidates, c.representative_id) for c in clusters}
    changed = True
    while changed:
        changed = False
        ids = list(reps.keys())
        for i, left_id in enumerate(ids):
            left = reps.get(left_id)
            if left is None:
                continue
            for right_id in ids[i + 1 :]:
                right = reps.get(right_id)
                if right is None:
                    continue
                if (
                    left.source_listing_id
                    and right.source_listing_id
                    and left.source_listing_id != right.source_listing_id
                ):
                    continue
                if jaccard(_title_of(left), _title_of(right)) >= 0.9:
                    text_dupes += 1
                    _merge(clusters, assigned, left_id, right_id)
                    reps.pop(right_id, None)
                    changed = True
                    break
            if changed:
                break
    representatives: list[ListingCandidate] = []
    final_clusters: list[Cluster] = []
    seen: set[str] = set()
    for cluster in clusters:
        root = assigned[cluster.representative_id]
        if root in seen:
            continue
        members = [c for c in candidates if assigned.get(c.candidate_id) == root]
        if not members:
            continue
        ordered = sorted(members, key=_score, reverse=True)
        final = Cluster(
            cluster_id=root,
            member_ids=[m.candidate_id for m in ordered],
            representative_id=ordered[0].candidate_id,
            reason=cluster.reason,
            family_kind=cluster.family_kind,
        )
        final_clusters.append(final)
        representatives.append(ordered[0].model_copy(update={"cluster_id": root}))
        seen.add(root)
    savings = {
        "raw_urls": len(candidates),
        "canonical_urls": len(by_url),
        "exact_duplicates": exact,
        "image_family_duplicates": image_dupes,
        "listing_clusters": len(final_clusters),
        "expensive_analyses_avoided": max(0, len(candidates) - len(representatives)),
    }
    return DedupeResult(
        clusters=final_clusters,
        representatives=representatives,
        before=len(candidates),
        after=len(representatives),
        exact_url_dupes=exact,
        image_family_dupes=image_dupes,
        text_dupes=text_dupes,
        savings=savings,
    )


def _pick(candidates: list[ListingCandidate], candidate_id: str) -> ListingCandidate | None:
    for candidate in candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def _merge(clusters: list[Cluster], assigned: dict[str, str], keep: str, drop: str) -> None:
    for candidate_id, cid in list(assigned.items()):
        if cid == drop:
            assigned[candidate_id] = keep
    for cluster in clusters:
        if cluster.cluster_id == drop:
            cluster.cluster_id = keep


def independent_image_families(records: list[EvidenceRecord]) -> int:
    return independent_family_count(records)
