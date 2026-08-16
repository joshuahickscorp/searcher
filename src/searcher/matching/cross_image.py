"""§18.6 cross-view consistency within a listing."""

from __future__ import annotations

from searcher.matching.structure import colour_distance
from searcher.matching.types import StructuredDescriptor


def cross_view_consistency(
    descriptors: list[StructuredDescriptor],
    *,
    apply_footwear_rules: bool = True,
) -> tuple[float, list[str], list[str]]:
    """Return (score, contradictions, missing)."""
    if len(descriptors) < 2:
        return 0.55, [], ["cross-view-second-image"]
    contradictions: list[str] = []
    laterals = [item for item in descriptors if item.eyelet_count >= 3]
    colours = [item.dominant_rgb for item in laterals] or [
        item.dominant_rgb for item in descriptors if item.label_hash is None
    ]
    max_c = 0.0
    for i, a in enumerate(colours):
        for b in colours[i + 1 :]:
            max_c = max(max_c, colour_distance(a, b))
    score = 0.78 if len(colours) < 2 else max(0.2, 1.0 - max_c * 2.4)
    # Only compare structure across images that look like the same view class.
    if apply_footwear_rules:
        laterals = [
            item for item in descriptors if item.eyelet_count >= 2 and item.panel_count >= 2
        ]
        if len(laterals) >= 2:
            eyelets = {item.eyelet_count for item in laterals}
            panels = {item.panel_count for item in laterals}
            if max(eyelets) - min(eyelets) >= 2:
                contradictions.append("gallery-eyelet-incompatible")
                score = min(score, 0.25)
            if max(panels) - min(panels) >= 2:
                contradictions.append("gallery-panel-incompatible")
                score = min(score, 0.25)
    if _stock_photo_gap(descriptors):
        contradictions.append("stock-photo-smoothness-gap")
        score = min(score, 0.4)
    return score, contradictions, []


def _view_class(item: StructuredDescriptor) -> str:
    """A coarse grouping of what the photograph is showing.

    Only rough classes are needed: the point is to avoid comparing a full-item
    shot against a close detail crop, which differ in smoothness for reasons
    that say nothing about whether a photograph was taken by the seller.
    """
    if item.subject_area >= 0.99:
        # No subject was segmented at all. On a real resale listing this is the
        # size chart, the condition table or a shop banner - not a photograph of
        # the item, and nothing about its smoothness says who took it.
        return "graphic"
    if item.label_hash is not None:
        return "label"
    if item.eyelet_count >= 2 and item.panel_count >= 2:
        return "lateral"
    if item.subject_area >= 0.55:
        return "full"
    return "detail"


def _stock_photo_gap(descriptors: list[StructuredDescriptor], *, spread: float = 0.45) -> bool:
    """True when one view class mixes a very smooth image with a rough one.

    A listing that pairs a manufacturer's stock photograph with a real snapshot
    of the same view is worth doubting. A listing that shows a garment laid flat
    and then crops in on a seam is not: those differ in smoothness by design.
    The comment above this block has always said the comparison belongs within a
    view class; before this it ran across every image in the gallery, which
    suppressed ordinary resale listings that photograph an item several ways.

    ponytail: `spread` is inherited, not calibrated. It needs the labelled
    stock-versus-snapshot pairs tracked in G056 before it can be defended.
    """
    groups: dict[str, list[float]] = {}
    for item in descriptors:
        view = _view_class(item)
        if view == "graphic":
            continue
        groups.setdefault(view, []).append(item.smoothness)
    return any(len(v) >= 2 and max(v) - min(v) > spread for v in groups.values())
