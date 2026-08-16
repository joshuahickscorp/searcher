"""§11.6 part inventory. Every label remains probabilistic."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, ViewHypothesis
from searcher.contracts.models import PartInventoryEntry, ViewInventoryEntry

_VIEW_PARTS: dict[ViewHypothesis, tuple[str, ...]] = {
    ViewHypothesis.LATERAL: ("toe", "eyestay", "lateral_panels", "heel", "outsole"),
    ViewHypothesis.MEDIAL: ("toe", "medial_panels", "heel", "outsole"),
    ViewHypothesis.FRONT: ("toe", "vamp", "eyestay"),
    ViewHypothesis.HEEL: ("heel", "collar"),
    ViewHypothesis.REAR: ("heel", "collar"),
    ViewHypothesis.SOLE: ("outsole", "tread"),
    ViewHypothesis.TOP: ("vamp", "eyestay", "tongue"),
    ViewHypothesis.LABEL: ("size_tag", "tongue_label"),
    ViewHypothesis.DETAIL: ("detail",),
    ViewHypothesis.WORN: ("on_foot", "outsole"),
    ViewHypothesis.BOX: ("packaging",),
    ViewHypothesis.UNKNOWN: ("subject",),
}


def parts_for_view(entry: ViewInventoryEntry) -> list[PartInventoryEntry]:
    names = _VIEW_PARTS.get(entry.view, ("subject",))
    scale = max(0.2, min(0.7, entry.confidence * 0.9))
    return [
        PartInventoryEntry(
            crop_id=entry.crop_id,
            part=name,
            confidence=round(scale, 4),
            fact_class=FactClass.INFERRED,
        )
        for name in names
    ]
