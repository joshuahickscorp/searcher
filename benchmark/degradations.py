"""The seven query degradations from the match-calibration receipt."""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

from searcher.matching.perturb import jpeg, screenshot_frame
from searcher.reference.imaging import open_rgb

DEGRADATION_NAMES: tuple[str, ...] = (
    "pristine",
    "blur",
    "heavy_blur",
    "crop",
    "small",
    "recompressed",
    "phone_snapshot",
)


def _dump(image: Any, *, fmt: str = "PNG", **kwargs: object) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _pristine(data: bytes) -> bytes:
    return _dump(open_rgb(data))


def _blur(data: bytes, radius: float) -> bytes:
    from PIL import ImageFilter

    return _dump(open_rgb(data).filter(ImageFilter.GaussianBlur(radius=radius)))


def _crop(data: bytes, fraction: float = 0.18) -> bytes:
    image = open_rgb(data)
    dx = max(1, int(image.width * fraction))
    dy = max(1, int(image.height * fraction))
    box = (dx, dy, image.width - dx, image.height - dy)
    if box[2] <= box[0] or box[3] <= box[1]:
        return _dump(image)
    return _dump(image.crop(box))


def _small(data: bytes, long_edge: int = 72) -> bytes:
    image = open_rgb(data)
    image.thumbnail((long_edge, long_edge))
    return _dump(image)


def _recompressed(data: bytes) -> bytes:
    return jpeg(data, quality=22)


def _phone_snapshot(data: bytes) -> bytes:
    framed = screenshot_frame(data)
    return jpeg(framed, quality=48)


def apply_degradation(data: bytes, name: str) -> bytes:
    if name == "pristine":
        return _pristine(data)
    if name == "blur":
        return _blur(data, 1.8)
    if name == "heavy_blur":
        return _blur(data, 5.5)
    if name == "crop":
        return _crop(data)
    if name == "small":
        return _small(data)
    if name == "recompressed":
        return _recompressed(data)
    if name == "phone_snapshot":
        return _phone_snapshot(data)
    raise ValueError(f"unknown degradation {name}")


def all_degradations(data: bytes) -> dict[str, bytes]:
    return {name: apply_degradation(data, name) for name in DEGRADATION_NAMES}


DEGRADERS: dict[str, Callable[[bytes], bytes]] = {
    name: (lambda blob, _name=name: apply_degradation(blob, _name)) for name in DEGRADATION_NAMES
}
