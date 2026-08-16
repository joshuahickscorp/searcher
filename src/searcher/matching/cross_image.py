"""§18.6 cross-view consistency within a listing."""

from __future__ import annotations

from searcher.matching.structure import colour_distance
from searcher.matching.types import StructuredDescriptor


def cross_view_consistency(
    descriptors: list[StructuredDescriptor],
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
    laterals = [item for item in descriptors if item.eyelet_count >= 2 and item.panel_count >= 2]
    if len(laterals) >= 2:
        eyelets = {item.eyelet_count for item in laterals}
        panels = {item.panel_count for item in laterals}
        if max(eyelets) - min(eyelets) >= 2:
            contradictions.append("gallery-eyelet-incompatible")
            score = min(score, 0.25)
        if max(panels) - min(panels) >= 2:
            contradictions.append("gallery-panel-incompatible")
            score = min(score, 0.25)
    smoothness = [item.smoothness for item in descriptors]
    if smoothness and max(smoothness) - min(smoothness) > 0.45:
        contradictions.append("stock-photo-smoothness-gap")
        score = min(score, 0.4)
    return score, contradictions, []
