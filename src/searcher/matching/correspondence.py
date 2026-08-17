"""§18.4 / §18.5 keypoint correspondence with ratio test and RANSAC.

Two detectors sit behind this, and the difference between them is not a detail.
Measured on fixtures/user_snapshots, ten photographs of an object against their
own listing and against another listing:

    opencv ORB        same median 35 inliers (min 14), other median 0 (max 7)
                      TPR 1.000 at FPR 0.000 with a threshold of 10
    BRIEF fallback    same median 6.5, other median 5.5
                      TPR equals FPR at every threshold: the signal is noise

opencv is optional and was absent from the environment for this project's whole
life, so every campaign ran on the fallback and no one was told. `method` on the
result says which detector answered, and `degraded_signal` says plainly when the
answer carries no information, because a quiet degraded path is how a product
ends up asserting things it cannot support.

Install it with `uv sync --extra correspondence`.
"""

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
    used_cv = _used_cv()
    method = "orb" if used_cv else "brief_fallback"
    notes = []
    if not used_cv:
        # Do not let this be silent. On the fallback, inlier counts for the same
        # object and for different objects overlap completely.
        notes.append("degraded_signal:no_opencv_correspondence_is_noise")
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
