"""Canonical split authority. An identifier may appear in exactly one split."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from searcher.core.ids import canonical_dumps, sha256_hex

from .corpus import NEGATIVE_PARENTS, multiview_case_id
from .paths import KIND_PACK, SPLIT_MANIFEST

CALIBRATION = "calibration"
HELD_OUT = "held_out"
HIDDEN = "hidden"

# The known-item target is reserved for held-out so it cannot be used to tune.
KNOWN_ITEM_TARGET = "8001001141404"

# Constructed labels from the synthetic hard-negative recipe. These are not
# marketplace authenticity labels and are not a professional judgment.
_BASE_BUCKET_TRUTH: dict[str, str] = {
    "true_match": "real",
    "adjacent_model": "hidden",
    "different_season": "possibly_real",
    "different_colourway": "hidden",
    "replica_copied_title": "replica",
    "authentic_poor_photos": "possibly_real",
    "counterfeit_excellent_photos": "hidden",
    "stolen_photos": "hidden",
    "stock_mixed": "real",
    "two_items": "hidden",
    "copied_product_code": "hidden",
    "mirrored_image": "real",
    "rehosted_sold": "hidden",
    "ai_generated": "hidden",
    "prompt_injection": "real",
}

BUCKET_TRUTH: dict[str, str] = {
    **_BASE_BUCKET_TRUTH,
    **{
        multiview_case_id(case_id): truth
        for case_id, truth in _BASE_BUCKET_TRUTH.items()
        if case_id in NEGATIVE_PARENTS
    },
}

# Seed held-out cases: mix of Real / Possibly Real / Replica / hidden.
# Replica has a single constructed parent; its multi-view variant stays with it
# so the reporting split sees the pairing rule on a wrong item with many views.
# These seeds pull their whole render group; they are not a per-case assignment.
_SEED_HELD_OUT_BUCKET_IDS: frozenset[str] = frozenset(
    {
        "true_match",
        "adjacent_model",
        "replica_copied_title",
        "authentic_poor_photos",
        "different_colourway",
        "stolen_photos",
        "two_items",
    }
)


def _image_digests_for(case_id: str) -> list[str]:
    """SHA-256 of each rendered PNG the constructed case is built from."""
    import hashlib

    from .corpus import images_for

    return [hashlib.sha256(png).hexdigest() for _name, png, _role in images_for(case_id)]


def _union_find(case_ids: Iterable[str]) -> dict[str, str]:
    """Join cases that share any rendered image digest."""
    ids = tuple(case_ids)
    parent = {case_id: case_id for case_id in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    by_digest: dict[str, list[str]] = {}
    for case_id in ids:
        for digest in _image_digests_for(case_id):
            by_digest.setdefault(digest, []).append(case_id)
    for members in by_digest.values():
        head = members[0]
        for other in members[1:]:
            union(head, other)
    return {case_id: find(case_id) for case_id in ids}


def render_groups(case_ids: Iterable[str] | None = None) -> tuple[frozenset[str], ...]:
    """Connected components of constructed cases that share a rendered image."""
    ids = tuple(case_ids) if case_ids is not None else tuple(BUCKET_TRUTH)
    roots = _union_find(ids)
    grouped: dict[str, set[str]] = {}
    for case_id, root in roots.items():
        grouped.setdefault(root, set()).add(case_id)
    return tuple(frozenset(group) for group in grouped.values())


def _held_out_from_render_groups() -> frozenset[str]:
    seeds = _SEED_HELD_OUT_BUCKET_IDS | frozenset(
        multiview_case_id(case_id)
        for case_id in _SEED_HELD_OUT_BUCKET_IDS
        if case_id in NEGATIVE_PARENTS
    )
    held: set[str] = set()
    for group in render_groups(BUCKET_TRUTH):
        if group & seeds:
            held |= group
    return frozenset(held)


KIND_PERMISSION = (
    "Cached public product photographs from shop.kind.co.jp, already held in "
    "fixtures/known_item_kind. KIND is admitted by SOURCE_POLICY for GET "
    "product/collection. Fetch date is recorded in pack.json. Images column "
    "of SOURCE_POLICY is 'no' for KIND, so this benchmark does not fetch new "
    "KIND photographs. Not an operator photograph."
)

HARDNEG_PERMISSION = (
    "Project-generated synthetic shoe diagrams from searcher.matching.synth "
    "and fixtures/hard_negatives. Not a marketplace image. Not an operator "
    "photograph. The bucket label is constructed from the fixture recipe, "
    "not a professional authenticity judgment."
)

SPLIT_RULE = (
    "Split by product identity (listing handle or constructed-case id) and, "
    "for constructed cases, by render provenance. "
    "An identifier appears in exactly one of {calibration, held_out}. "
    "There is no authorized hidden-evaluation set; that split is absent. "
    "KIND: the known-item target handle is reserved for held_out; remaining "
    "handles sorted lexicographically, first five calibration, rest held_out. "
    "Hard-negative cases: group by the rendered images they are built from "
    "(connected components of shared image digests); assign each group "
    "wholly to one split. A group is held_out if it contains any seed "
    "reporting case (the original seven plus multi-view variants of those "
    "negatives), so the reporting split still contains Real, Possibly Real, "
    "Replica, and hidden, and so best-of-N pairing is scored on wrong items "
    "that carry many views; remaining groups are calibration. Groups are "
    "not split, trimmed, dropped, or moved to hidden. "
    "Calibration is used only to inspect the score-versus-outcome curve and "
    "to show where the already-shipped 0.86 threshold sits. Thresholds are "
    "not retuned. Held-out is used only to report retrieval and bucket numbers."
)


class SplitLeakageError(ValueError):
    """Raised when the same identifier is present in more than one split."""


# Whole render groups, not individual cases. A group that contains any seed
# reporting case is held_out; the rest stay calibration. No group is trimmed.
# Shared view templates (sole, label, front) connect most constructed cases
# into one component; that size is reported, not cut down.
HELD_OUT_BUCKET_IDS: frozenset[str] = _held_out_from_render_groups()


@dataclass(frozen=True, slots=True)
class SplitItem:
    item_id: str
    family: str
    split: str
    source: str
    permission: str
    truth_bucket: str | None
    listing_handle: str | None
    images: tuple[str, ...]
    source_url: str | None
    title: str | None

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.item_id,
            "family": self.family,
            "split": self.split,
            "source": self.source,
            "permission": self.permission,
            "truth_bucket": self.truth_bucket,
            "listing_handle": self.listing_handle,
            "images": list(self.images),
            "source_url": self.source_url,
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class SplitSet:
    rule: str
    items: tuple[SplitItem, ...]

    @property
    def calibration(self) -> tuple[SplitItem, ...]:
        return tuple(item for item in self.items if item.split == CALIBRATION)

    @property
    def held_out(self) -> tuple[SplitItem, ...]:
        return tuple(item for item in self.items if item.split == HELD_OUT)

    @property
    def calibration_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.calibration)

    @property
    def held_out_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.held_out)

    def ids_for(self, split: str, *, family: str | None = None) -> tuple[str, ...]:
        out: list[str] = []
        for item in self.items:
            if item.split != split:
                continue
            if family is not None and item.family != family:
                continue
            out.append(item.item_id)
        return tuple(out)

    def item(self, item_id: str) -> SplitItem:
        for row in self.items:
            if row.item_id == item_id:
                return row
        raise KeyError(item_id)

    def hash_for(self, split: str) -> str:
        ids = sorted(self.ids_for(split))
        return sha256_hex(canonical_dumps(ids).encode("utf-8"))

    def as_payload(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "hidden_evaluation": {
                "present": False,
                "reason": (
                    "No authorized hidden-evaluation set is held. A hidden "
                    "split is not invented. Metrics that require it are "
                    "reported as not computed."
                ),
            },
            "calibration": {
                "ids": list(self.calibration_ids),
                "hash": self.hash_for(CALIBRATION),
            },
            "held_out": {
                "ids": list(self.held_out_ids),
                "hash": self.hash_for(HELD_OUT),
            },
            "items": [item.as_payload() for item in self.items],
        }


def kind_item_id(handle: str) -> str:
    return f"kind:{handle}"


def hardneg_item_id(case_id: str) -> str:
    return f"hardneg:{case_id}"


def assert_no_leakage(
    calibration: Iterable[str],
    held_out: Iterable[str],
    *,
    hidden: Iterable[str] = (),
) -> None:
    """Fail if any identifier appears in more than one split."""
    groups = {
        CALIBRATION: list(calibration),
        HELD_OUT: list(held_out),
        HIDDEN: list(hidden),
    }
    empty = [name for name, ids in groups.items() if name != HIDDEN and not ids]
    if empty:
        raise SplitLeakageError(f"empty split(s): {empty}")
    seen: dict[str, str] = {}
    overlap: dict[str, list[str]] = {}
    for name, ids in groups.items():
        for item_id in ids:
            prior = seen.get(item_id)
            if prior is None:
                seen[item_id] = name
                continue
            overlap.setdefault(item_id, [prior]).append(name)
    if overlap:
        detail = ", ".join(f"{item_id} in {parts}" for item_id, parts in sorted(overlap.items()))
        raise SplitLeakageError(f"identifier(s) in more than one split: {detail}")


def _kind_handles() -> list[dict[str, Any]]:
    pack = json.loads(KIND_PACK.read_text(encoding="utf-8"))
    listings = pack.get("listings") or []
    if not isinstance(listings, list) or not listings:
        raise SplitLeakageError(f"no listings in {KIND_PACK}")
    rows: list[dict[str, Any]] = []
    for raw in listings:
        if not isinstance(raw, dict):
            continue
        handle = str(raw.get("handle") or "")
        if not handle:
            continue
        images = tuple(str(name) for name in (raw.get("local_images") or []))
        rows.append(
            {
                "handle": handle,
                "images": images,
                "url": str(raw.get("url") or ""),
                "title": str(raw.get("title") or ""),
            }
        )
    if not any(row["handle"] == KNOWN_ITEM_TARGET for row in rows):
        raise SplitLeakageError(f"known-item target {KNOWN_ITEM_TARGET} missing from pack")
    return rows


def assign_kind_split(handle: str, handles: Iterable[str]) -> str:
    if handle == KNOWN_ITEM_TARGET:
        return HELD_OUT
    rest = sorted(h for h in handles if h != KNOWN_ITEM_TARGET)
    if handle in rest[:5]:
        return CALIBRATION
    return HELD_OUT


def assign_bucket_split(case_id: str) -> str:
    if case_id not in BUCKET_TRUTH:
        raise SplitLeakageError(f"unknown constructed case {case_id}")
    return HELD_OUT if case_id in HELD_OUT_BUCKET_IDS else CALIBRATION


def assign_splits() -> SplitSet:
    """Apply the stated rule to the authorized fixtures."""
    kind_rows = _kind_handles()
    handles = [row["handle"] for row in kind_rows]
    items: list[SplitItem] = []
    for row in kind_rows:
        handle = row["handle"]
        items.append(
            SplitItem(
                item_id=kind_item_id(handle),
                family="kind_listing",
                split=assign_kind_split(handle, handles),
                source="fixtures/known_item_kind",
                permission=KIND_PERMISSION,
                truth_bucket=None,
                listing_handle=handle,
                images=tuple(row["images"]),
                source_url=row["url"] or None,
                title=row["title"] or None,
            )
        )
    for case_id, truth in sorted(BUCKET_TRUTH.items()):
        items.append(
            SplitItem(
                item_id=hardneg_item_id(case_id),
                family="hard_negative",
                split=assign_bucket_split(case_id),
                source="fixtures/hard_negatives + searcher.matching.synth",
                permission=HARDNEG_PERMISSION,
                truth_bucket=truth,
                listing_handle=None,
                images=(),
                source_url=None,
                title=case_id,
            )
        )
    items.sort(key=lambda item: item.item_id)
    splits = SplitSet(rule=SPLIT_RULE, items=tuple(items))
    assert_no_leakage(splits.calibration_ids, splits.held_out_ids)
    return splits


def _item_from_payload(raw: dict[str, Any]) -> SplitItem:
    return SplitItem(
        item_id=str(raw["id"]),
        family=str(raw["family"]),
        split=str(raw["split"]),
        source=str(raw["source"]),
        permission=str(raw["permission"]),
        truth_bucket=raw.get("truth_bucket"),
        listing_handle=raw.get("listing_handle"),
        images=tuple(str(name) for name in (raw.get("images") or [])),
        source_url=raw.get("source_url"),
        title=raw.get("title"),
    )


def load_canonical_splits() -> SplitSet:
    """Load the frozen manifest and refuse it if it leaks or disagrees with the rule."""
    if not SPLIT_MANIFEST.is_file():
        raise SplitLeakageError(f"missing split manifest {SPLIT_MANIFEST}")
    payload = json.loads(SPLIT_MANIFEST.read_text(encoding="utf-8"))
    items = tuple(_item_from_payload(row) for row in payload.get("items") or [])
    frozen = SplitSet(rule=str(payload.get("rule") or SPLIT_RULE), items=items)
    assert_no_leakage(frozen.calibration_ids, frozen.held_out_ids)
    built = assign_splits()
    if set(frozen.calibration_ids) != set(built.calibration_ids):
        raise SplitLeakageError("frozen calibration ids disagree with the stated rule")
    if set(frozen.held_out_ids) != set(built.held_out_ids):
        raise SplitLeakageError("frozen held-out ids disagree with the stated rule")
    return frozen


def write_split_manifest(path: Any = None) -> SplitSet:
    splits = assign_splits()
    dest = SPLIT_MANIFEST if path is None else path
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "protocol": "searcher-public-benchmark-v1",
        **splits.as_payload(),
    }
    dest.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return splits

def assert_no_pixel_leakage(
    images_by_case: dict[str, list[bytes]],
    calibration_cases: Iterable[str],
    held_out_cases: Iterable[str],
) -> None:
    """Fail if calibration and held-out cases share image content.

    `assert_no_leakage` compares identifiers. Identifiers are cheap to keep
    distinct and say nothing about pixels, so a case can sit in calibration
    carrying the same bytes as a held-out case under another name - and in this
    corpus 22 image hashes did exactly that, because the synthetic cases are
    built from shared renders. Any pixel-based scorer has then seen the
    held-out images during calibration, and every held-out number measured
    afterwards is measured partly on its own tuning data.
    """
    import hashlib

    cal = set(calibration_cases)
    held = set(held_out_cases)
    digests: dict[str, set[str]] = {}
    for case, images in images_by_case.items():
        side = "calibration" if case in cal else ("held_out" if case in held else None)
        if side is None:
            continue
        for png in images:
            digests.setdefault(hashlib.sha256(png).hexdigest(), set()).add(side)
    shared = sorted(d for d, sides in digests.items() if len(sides) > 1)
    if shared:
        raise SplitLeakageError(
            f"{len(shared)} image digest(s) appear in both calibration and held_out; "
            f"first: {shared[0][:16]}"
        )
