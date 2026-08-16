"""§11.4 reference-set unification. Ambiguity produces alternate clusters."""

from __future__ import annotations

from searcher.contracts.models import TargetCluster
from searcher.core.ids import new_id
from searcher.reference.imaging import hamming


def _hist_distance(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b, strict=False)) / max(1, len(a))


def unify_references(
    image_ids: list[str],
    hashes: dict[str, str],
    histograms: dict[str, list[float]],
    *,
    collage_flags: dict[str, bool] | None = None,
    worn_flags: dict[str, bool] | None = None,
    screenshot_flags: dict[str, bool] | None = None,
) -> tuple[TargetCluster, list[TargetCluster]]:
    collage_flags = collage_flags or {}
    worn_flags = worn_flags or {}
    screenshot_flags = screenshot_flags or {}
    if not image_ids:
        empty = TargetCluster(
            cluster_id=new_id(),
            role="primary",
            relation="empty",
            confidence=0.0,
            notes=["no images"],
        )
        return empty, []

    parent: dict[str, str] = {image_id: image_id for image_id in image_ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, left in enumerate(image_ids):
        for right in image_ids[i + 1 :]:
            dist = hamming(hashes.get(left, ""), hashes.get(right, ""))
            colour = _hist_distance(histograms.get(left, []), histograms.get(right, []))
            if dist <= 12 and colour < 0.18:
                union(left, right)

    groups: dict[str, list[str]] = {}
    for image_id in image_ids:
        groups.setdefault(find(image_id), []).append(image_id)
    ranked = sorted(groups.values(), key=lambda items: (-len(items), items[0]))

    def _relation(members: list[str]) -> str:
        if any(collage_flags.get(mid) for mid in members):
            return "collage"
        if any(screenshot_flags.get(mid) for mid in members):
            return "screenshot_multiple_products"
        if any(worn_flags.get(mid) for mid in members):
            return "worn_item"
        if len(members) == 1:
            return "single_view"
        colour_spread = 0.0
        if len(members) >= 2:
            base = histograms.get(members[0], [])
            colour_spread = max(_hist_distance(base, histograms.get(m, [])) for m in members[1:])
        if colour_spread > 0.22:
            return "colourways"
        return "same_item_multiple_views"

    clusters: list[TargetCluster] = []
    for index, members in enumerate(ranked):
        relation = _relation(members)
        notes = [relation]
        if len(ranked) > 1 and index == 0:
            notes.append("most_repeated_or_salient_target")
        clusters.append(
            TargetCluster(
                cluster_id=new_id(),
                image_ids=list(members),
                role="primary" if index == 0 else "alternate",
                relation=relation,
                confidence=round(min(0.9, 0.4 + 0.15 * len(members)), 4),
                notes=notes,
            )
        )
    primary = clusters[0]
    alternates = clusters[1:]
    if len(image_ids) >= 2 and not alternates:
        # Material ambiguity still recorded as a note; do not block.
        primary.notes.append("no_material_ambiguity")
    return primary, alternates
