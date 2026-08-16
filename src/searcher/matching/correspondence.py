"""§18.4 / §18.5 keypoint correspondence with ratio test and RANSAC."""

from __future__ import annotations

from searcher.matching.features import detect_keypoints, match_descriptors, ransac_similarity
from searcher.matching.types import CorrespondenceResult
from searcher.retrieval.cost import CostLedger, CostStage


def correspond_pair(
    reference_png: bytes,
    candidate_png: bytes,
    *,
    ledger: CostLedger | None = None,
) -> CorrespondenceResult:
    if ledger is not None:
        ledger.record(CostStage.LOCAL_CORRESPONDENCE, detail="orb_or_fallback")
    left = detect_keypoints(reference_png)
    right = detect_keypoints(candidate_png)
    matches = match_descriptors(left, right)
    ratio, inliers, residual, mirrored = ransac_similarity(left, right, matches)
    method = "orb" if _used_cv() else "brief_fallback"
    notes = []
    if not matches:
        notes.append("no_descriptor_matches")
    if mirrored:
        notes.append("mirrored_geometry_accepted")
    return CorrespondenceResult(
        inlier_ratio=round(ratio, 4),
        match_count=len(matches),
        inlier_count=inliers,
        method=method,
        mirrored=mirrored,
        residual=round(residual, 4),
        notes=notes,
    )


def _used_cv() -> bool:
    from searcher.matching.features import opencv_available

    return opencv_available()
