"""Classical local features. OpenCV ORB/AKAZE when present; Pillow fallback."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from searcher.reference.imaging import open_rgb


@dataclass(frozen=True, slots=True)
class Keypoint:
    x: float
    y: float
    response: float
    descriptor: tuple[int, ...]


def opencv_available() -> bool:
    try:
        import cv2

        del cv2
        return True
    except Exception:
        return False


def detect_keypoints(png: bytes, *, max_points: int = 180) -> list[Keypoint]:
    if opencv_available():
        found = _detect_opencv(png, max_points=max_points)
        if found:
            return found
    return _detect_pillow(png, max_points=max_points)


def _detect_opencv(png: bytes, *, max_points: int) -> list[Keypoint]:
    import cv2
    import numpy as np

    image = open_rgb(png)
    array = np.array(image.convert("L"))
    orb = cv2.ORB_create(nfeatures=max_points)  # type: ignore[attr-defined]  # opencv 5 stubs omit ORB_create; it exists at runtime
    kps, desc = orb.detectAndCompute(array, None)
    if desc is None or kps is None:
        return []
    out: list[Keypoint] = []
    for kp, row in zip(kps, desc, strict=False):
        out.append(
            Keypoint(
                x=float(kp.pt[0]),
                y=float(kp.pt[1]),
                response=float(kp.response),
                descriptor=tuple(int(v) for v in row.tolist()),
            )
        )
    return out


def _detect_pillow(png: bytes, *, max_points: int) -> list[Keypoint]:
    from PIL import ImageFilter

    image = open_rgb(png).convert("L")
    image.thumbnail((256, 256))
    edges = image.filter(ImageFilter.FIND_EDGES)
    width, height = edges.size
    pix = edges.load()
    gray = image.load()
    candidates: list[tuple[int, int, int]] = []
    for y in range(6, height - 6, 2):
        for x in range(6, width - 6, 2):
            response = int(pix[x, y])
            if response >= 40:
                candidates.append((response, x, y))
    candidates.sort(reverse=True)
    picked: list[Keypoint] = []
    for response, x, y in candidates:
        if any(abs(x - p.x) < 6 and abs(y - p.y) < 6 for p in picked):
            continue
        picked.append(
            Keypoint(
                x=float(x),
                y=float(y),
                response=float(response),
                descriptor=_brief(gray, x, y, width, height),
            )
        )
        if len(picked) >= max_points:
            break
    return picked


# Deterministic BRIEF-like pairs. Not learned.
_BRIEF_PAIRS: tuple[tuple[int, int, int, int], ...] = tuple(
    (
        (i * 17 + 3) % 13 - 6,
        (i * 29 + 5) % 13 - 6,
        (i * 13 + 7) % 13 - 6,
        (i * 23 + 11) % 13 - 6,
    )
    for i in range(128)
)


def _brief(gray: Any, x: int, y: int, width: int, height: int) -> tuple[int, ...]:
    bits: list[int] = []
    byte = 0
    count = 0
    for dx1, dy1, dx2, dy2 in _BRIEF_PAIRS:
        x1, y1 = x + dx1, y + dy1
        x2, y2 = x + dx2, y + dy2
        if not (0 <= x1 < width and 0 <= y1 < height and 0 <= x2 < width and 0 <= y2 < height):
            bit = 0
        else:
            bit = 1 if gray[x1, y1] > gray[x2, y2] else 0
        byte = (byte << 1) | bit
        count += 1
        if count == 8:
            bits.append(byte)
            byte = 0
            count = 0
    if count:
        bits.append(byte << (8 - count))
    return tuple(bits)


def hamming_desc(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = min(len(a), len(b))
    dist = 0
    for i in range(n):
        dist += (a[i] ^ b[i]).bit_count()
    dist += 8 * abs(len(a) - len(b))
    return dist


def match_descriptors(
    left: list[Keypoint],
    right: list[Keypoint],
    *,
    ratio: float = 0.75,
) -> list[tuple[int, int, int]]:
    """Lowe ratio test. Returns (left_idx, right_idx, distance)."""
    if not left or not right:
        return []
    pairs: list[tuple[int, int, int]] = []
    for i, src in enumerate(left):
        best = 10_000
        second = 10_000
        best_j = -1
        for j, dst in enumerate(right):
            d = hamming_desc(src.descriptor, dst.descriptor)
            if d < best:
                second = best
                best = d
                best_j = j
            elif d < second:
                second = d
        if best_j >= 0 and best < 40 and (second == 0 or best / max(1, second) <= ratio):
            pairs.append((i, best_j, best))
    return pairs


def ransac_similarity(
    left: list[Keypoint],
    right: list[Keypoint],
    matches: list[tuple[int, int, int]],
    *,
    iterations: int = 64,
    threshold: float = 8.0,
) -> tuple[float, int, float, bool]:
    """Estimate translation+scale. Returns inlier_ratio, inliers, residual, mirrored."""
    if len(matches) < 3:
        return 0.0, 0, 99.0, False
    best_inliers = 0
    best_residual = 99.0
    best_mirror = False
    for mirror in (False, True):
        for seed in range(iterations):
            i1 = seed % len(matches)
            i2 = (seed * 3 + 1) % len(matches)
            if i1 == i2:
                continue
            a1, b1, _ = matches[i1]
            a2, b2, _ = matches[i2]
            p1, q1 = left[a1], right[b1]
            p2, q2 = left[a2], right[b2]
            q1x = -q1.x if mirror else q1.x
            q2x = -q2.x if mirror else q2.x
            dxp, dyp = p2.x - p1.x, p2.y - p1.y
            dxq, dyq = q2x - q1x, q2.y - q1.y
            denom = dxp * dxp + dyp * dyp
            if denom < 4:
                continue
            scale = math.sqrt((dxq * dxq + dyq * dyq) / denom)
            if scale < 0.3 or scale > 3.2:
                continue
            tx = q1x - scale * p1.x
            ty = q1.y - scale * p1.y
            inliers = 0
            residual = 0.0
            for ai, bi, _d in matches:
                src, dst = left[ai], right[bi]
                dx = (scale * src.x + tx) - ((-dst.x) if mirror else dst.x)
                dy = (scale * src.y + ty) - dst.y
                err = math.hypot(dx, dy)
                if err <= threshold:
                    inliers += 1
                    residual += err
            if inliers > best_inliers:
                best_inliers = inliers
                best_residual = residual / max(1, inliers)
                best_mirror = mirror
    ratio = best_inliers / max(1, len(matches))
    return ratio, best_inliers, best_residual, best_mirror
