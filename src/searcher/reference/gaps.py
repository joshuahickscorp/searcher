"""Missing-evidence requests. Searcher-owned; not the donor 3D planner."""

from __future__ import annotations

from searcher.contracts.enums import ViewHypothesis
from searcher.contracts.models import EvidenceGap, NextEvidenceRequest, ReferenceAnalysis
from searcher.core.ids import new_id

_PRIORITY = (
    (ViewHypothesis.SOLE, "Upload a sole / outsole view.", "Distinguishes adjacent models."),
    (ViewHypothesis.LABEL, "Upload the size / tongue label.", "Improves product-code evidence."),
    (ViewHypothesis.HEEL, "Upload a straight rear / heel view.", "Heel overlay is unseen."),
    (ViewHypothesis.LATERAL, "Upload a clean lateral view.", "Panel layout is incomplete."),
    (ViewHypothesis.MEDIAL, "Upload a medial view.", "The opposite side is not in the set."),
)


def evidence_gaps(analysis: ReferenceAnalysis) -> list[EvidenceGap]:
    seen = {entry.view for entry in analysis.view_inventory}
    gaps: list[EvidenceGap] = []
    for view, request, impact in _PRIORITY:
        if view not in seen:
            gaps.append(EvidenceGap(gap=f"missing_{view.value}", impact=impact, request=request))
    if analysis.visual_signature.learned_embedding_available is False:
        gaps.append(
            EvidenceGap(
                gap="dense_features_blocked",
                impact="No learned embedding; identity is text + cheap descriptors only.",
                request=None,
            )
        )
    low_res = [
        image_id for image_id, quality in analysis.quality_map.items() if quality.resolution < 0.4
    ]
    if low_res:
        gaps.append(
            EvidenceGap(
                gap="low_resolution",
                impact="Current images are too small for reliable part comparison.",
                request="Upload a higher-resolution photograph.",
            )
        )
    return gaps[:8]


def request_missing_evidence(analysis: ReferenceAnalysis) -> list[NextEvidenceRequest]:
    requests: list[NextEvidenceRequest] = []
    for gap in evidence_gaps(analysis):
        if not gap.request:
            continue
        requests.append(
            NextEvidenceRequest(
                request_id=new_id(),
                target=gap.gap,
                reason=gap.impact,
                expected_gain=0.35 if "label" in gap.gap or "sole" in gap.gap else 0.22,
            )
        )
        if len(requests) >= 3:
            break
    return requests
