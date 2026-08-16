"""Structured visual descriptors extracted from pixels, not from fixture labels."""

from __future__ import annotations

from typing import Any

from searcher.core.ids import sha256_hex
from searcher.matching.types import StructuredDescriptor
from searcher.reference.imaging import open_rgb, subject_bbox


def _pil() -> Any:
    from PIL import ImageFilter, ImageStat

    return ImageFilter, ImageStat


def _pixel_seq(image: Any) -> list[Any]:
    flatten = getattr(image, "get_flattened_data", None)
    if callable(flatten):
        return list(flatten())
    raw = image.tobytes()
    if image.mode == "L":
        return list(raw)
    step = len(image.getbands())
    return [tuple(raw[i : i + step]) for i in range(0, len(raw), step)]


def extract_structure(png: bytes, *, image_id: str) -> StructuredDescriptor:
    ImageFilter, ImageStat = _pil()
    rgb = open_rgb(png)
    width, height = rgb.size
    gray = rgb.convert("L")
    bbox = subject_bbox(png)
    bx, by, bw, bh = bbox
    subject_area = (bw * bh) / max(1, width * height)
    aspect = bw / max(1, bh)
    cx = (bx + bw / 2) / max(1, width)
    cy = (by + bh / 2) / max(1, height)
    eyelet_count = _count_eyelets(gray, bbox)
    seam_count, panel_count = _count_panels(gray, bbox)
    outsole_ratio, sole_to_upper = _outsole(gray, bbox)
    heel_aspect, heel_cut, heel_angle = _heel(gray, bbox)
    logo_xy, logo_kind = _logo(rgb, bbox)
    tread_kind = _tread(gray, bbox)
    label_hash = _label_hash(gray, bbox)
    subject = rgb.crop((bx, by, bx + max(1, bw), by + max(1, bh))).resize((32, 32))
    pixels = _pixel_seq(subject)
    if pixels:
        r = sum(int(p[0]) for p in pixels) / len(pixels)
        g = sum(int(p[1]) for p in pixels) / len(pixels)
        b = sum(int(p[2]) for p in pixels) / len(pixels)
    else:
        r = g = b = 0.0
    edges = gray.resize((64, 64)).filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    smoothness = 1.0 - min(1.0, float(stat.var[0] if stat.var else 0.0) / 4000.0)
    return StructuredDescriptor(
        image_id=image_id,
        width=width,
        height=height,
        aspect=round(aspect, 4),
        subject_area=round(subject_area, 4),
        centroid=(round(cx, 4), round(cy, 4)),
        eyelet_count=eyelet_count,
        panel_count=panel_count,
        seam_count=seam_count,
        outsole_ratio=round(outsole_ratio, 4),
        sole_to_upper=round(sole_to_upper, 4),
        heel_aspect=round(heel_aspect, 4),
        heel_cut=heel_cut,
        heel_angle=round(heel_angle, 4),
        logo_xy=logo_xy,
        logo_kind=logo_kind,
        tread_kind=tread_kind,
        label_hash=label_hash,
        dominant_rgb=(round(r, 2), round(g, 2), round(b, 2)),
        smoothness=round(smoothness, 4),
        keypoints=0,
    )


def _count_eyelets(gray: Any, bbox: tuple[int, int, int, int]) -> int:
    """Bright disks on a dark band — the rendered eye-stay."""
    bx, by, bw, bh = bbox
    # Search the upper third of the subject, full width minus heel.
    x0 = bx + int(bw * 0.20)
    x1 = bx + int(bw * 0.62)
    y0 = by + int(bh * 0.02)
    y1 = by + int(bh * 0.28)
    if x1 <= x0 or y1 <= y0:
        return 0
    crop = gray.crop((x0, y0, x1, y1))
    pixels = crop.load()
    w, h = crop.size
    found: list[tuple[int, int]] = []
    for y in range(6, h - 6, 2):
        for x in range(6, w - 6, 2):
            if pixels[x, y] < 215:
                continue
            if not _ring_dark(pixels, x, y, w, h):
                continue
            if any(abs(x - px) <= 14 and abs(y - py) <= 14 for px, py in found):
                continue
            found.append((x, y))
    return len(found)


def _ring_dark(pixels: Any, x: int, y: int, w: int, h: int) -> bool:
    dark = 0
    samples = 0
    for dx, dy in (
        (8, 0),
        (-8, 0),
        (0, 8),
        (0, -8),
        (6, 6),
        (-6, 6),
        (6, -6),
        (-6, -6),
    ):
        xx, yy = x + dx, y + dy
        if 0 <= xx < w and 0 <= yy < h:
            samples += 1
            if pixels[xx, yy] < 70:
                dark += 1
    return samples >= 6 and dark >= 4


def _count_panels(gray: Any, bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    """Count thick near-black vertical seams in the mid-body."""
    bx, by, bw, bh = bbox
    x0 = bx + int(bw * 0.20)
    x1 = bx + int(bw * 0.62)
    y0 = by + int(bh * 0.18)
    y1 = by + int(bh * 0.68)
    if x1 <= x0 or y1 <= y0:
        return 0, 1
    crop = gray.crop((x0, y0, x1, y1))
    w, h = crop.size
    pixels = crop.load()
    energy = []
    for x in range(w):
        dark = sum(1 for y in range(h) if pixels[x, y] <= 20)
        energy.append(dark / max(1, h))
    peaks: list[int] = []
    for x in range(2, w - 2):
        peak = energy[x] >= 0.25 and energy[x] >= energy[x - 1] and energy[x] >= energy[x + 1]
        if peak and (not peaks or x - peaks[-1] > 10):
            peaks.append(x)
    seams = len(peaks)
    # Internal seams plus one bounding edge are typical; panel count ≈ seam count.
    panels = seams if seams else 1
    return seams, panels


def _outsole(gray: Any, bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    bx, by, bw, bh = bbox
    x0, x1 = bx + int(bw * 0.05), bx + int(bw * 0.85)
    y0, y1 = by + int(bh * 0.55), by + bh
    if x1 <= x0 or y1 <= y0:
        return 0.12, 0.2
    crop = gray.crop((x0, y0, x1, y1))
    w, h = crop.size
    pixels = crop.load()
    dark_rows = 0
    for y in range(h):
        dark = sum(1 for x in range(0, w, 2) if pixels[x, y] < 40)
        if dark / max(1, w / 2) > 0.45:
            dark_rows += 1
    ratio = dark_rows / max(1, bh)
    sole_to_upper = dark_rows / max(1, bh - dark_rows)
    return min(0.7, ratio), min(1.8, sole_to_upper)


def _heel(gray: Any, bbox: tuple[int, int, int, int]) -> tuple[float, str, float]:
    bx, by, bw, bh = bbox
    x0 = bx + int(bw * 0.80)
    crop = gray.crop((x0, by, bx + bw, by + int(bh * 0.78)))
    w, h = crop.size
    if w < 6 or h < 8:
        return 1.0, "unknown", 0.0
    mask = crop.point(lambda v: 255 if v < 120 else 0)
    box = mask.getbbox()
    if box is None:
        return 1.0, "unknown", 0.0
    ww = box[2] - box[0]
    hh = box[3] - box[1]
    aspect = ww / max(1, hh)
    pixels = mask.load()
    left_col: list[int] = []
    for y in range(box[1], box[3], 2):
        xs = [x for x in range(w) if pixels[x, y] > 0]
        if xs:
            left_col.append(min(xs))
    if len(left_col) < 6:
        return aspect, "unknown", 0.0
    first, mid, last = left_col[0], left_col[len(left_col) // 2], left_col[-1]
    # A left-side bite pushes the mid left-edge further right.
    notch = mid - (first + last) / 2
    spread = max(left_col) - min(left_col)
    if notch > 5:
        cut = "notched"
    elif spread <= 10:
        cut = "block"
    else:
        cut = "rounded"
    angle = (last - first) / max(1, len(left_col))
    return aspect, cut, angle


def _logo(
    rgb: Any, bbox: tuple[int, int, int, int]
) -> tuple[tuple[float, float] | None, str | None]:
    bx, by, bw, bh = bbox
    crop = rgb.crop((bx, by, bx + bw, by + bh))
    w, h = crop.size
    pixels = crop.load()
    hits: list[tuple[int, int]] = []
    for y in range(3, h - 3, 2):
        for x in range(3, w - 3, 2):
            r, g, b = pixels[x, y][:3]
            # Gold / yellow mark used by the renderer; not body gray.
            if r > 180 and g > 140 and r - b > 60:
                hits.append((x, y))
    if not hits:
        return None, None
    mx = sum(p[0] for p in hits) / len(hits)
    my = sum(p[1] for p in hits) / len(hits)
    xs = [p[0] for p in hits]
    ys = [p[1] for p in hits]
    span_x = max(xs) - min(xs) + 1
    span_y = max(ys) - min(ys) + 1
    if span_x > span_y * 1.6:
        kind = "bar"
    elif abs(span_x - span_y) <= 6:
        kind = "circle"
    else:
        kind = "triangle"
    return (round(mx / max(1, w), 3), round(my / max(1, h), 3)), kind


def _tread(gray: Any, bbox: tuple[int, int, int, int]) -> str:
    bx, by, bw, bh = bbox
    crop = gray.crop((bx, by + int(bh * 0.70), bx + bw, by + bh))
    w, h = crop.size
    if w < 10 or h < 8:
        return "unknown"
    pixels = crop.load()
    row_means = []
    x_trans = []
    for y in range(h):
        vals = [pixels[x, y] for x in range(0, w, 2)]
        row_means.append(sum(vals) / max(1, len(vals)))
        trans = sum(1 for i in range(1, len(vals)) if abs(vals[i] - vals[i - 1]) > 25)
        x_trans.append(trans)
    osc = sum(1 for i in range(1, len(row_means)) if abs(row_means[i] - row_means[i - 1]) > 12)
    mean_trans = sum(x_trans) / max(1, len(x_trans))
    if mean_trans > 6 and osc > h * 0.25:
        return "waffle"
    if osc >= max(3, h // 5) and mean_trans <= 5:
        return "parallel"
    return "circle"


def _label_hash(gray: Any, bbox: tuple[int, int, int, int]) -> str | None:
    """Only hash bright label-card images, never a lateral product shot."""
    bx, by, bw, bh = bbox
    crop = gray.crop((bx, by, bx + bw, by + bh))
    sample = crop.resize((32, 32))
    pixels = _pixel_seq(sample)
    if not pixels:
        return None
    mean = sum(int(v) for v in pixels) / len(pixels)
    if mean < 170:
        return None
    strip = crop.crop((0, int(crop.size[1] * 0.65), crop.size[0], crop.size[1])).resize((32, 8))
    data = bytes(_pixel_seq(strip))
    if not data:
        return None
    return sha256_hex(data)[:16]


def colour_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 / 441.67)


def logo_distance(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
    *,
    allow_mirror: bool = True,
) -> float:
    if a is None or b is None:
        return 1.0
    direct = float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
    if not allow_mirror:
        return min(1.0, direct)
    mirrored = float(((1.0 - a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
    return min(1.0, min(direct, mirrored))
