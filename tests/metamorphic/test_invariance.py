"""§32.4 invariance within tolerance."""

from __future__ import annotations

from searcher.matching.perturb import (
    background_change,
    brightness,
    colour_temperature,
    jpeg,
    mild_crop,
    mild_rotate,
    resize,
    screenshot_frame,
    watermark,
)
from searcher.matching.structure import extract_structure
from searcher.matching.synth import REFERENCE_SHOE, render_shoe


def _base() -> bytes:
    return render_shoe(REFERENCE_SHOE, view="lateral")


def test_invariance_matrix() -> None:
    ref = extract_structure(_base(), image_id="ref")
    transforms = {
        "resize": resize(_base(), 0.8),
        "jpeg": jpeg(_base(), 70),
        "crop": mild_crop(_base(), 8),
        "rotate": mild_rotate(_base(), 4),
        "brightness": brightness(_base(), 1.12),
        "colour_temp": colour_temperature(_base(), 1.15),
        "background": background_change(_base()),
        "watermark": watermark(_base()),
        "screenshot": screenshot_frame(_base()),
    }
    rows: list[tuple[str, int, int]] = []
    for name, png in transforms.items():
        got = extract_structure(png, image_id=name)
        eye_delta = abs(got.eyelet_count - ref.eyelet_count)
        panel_delta = abs(got.panel_count - ref.panel_count)
        rows.append((name, eye_delta, panel_delta))
        assert eye_delta <= 1, (name, got.eyelet_count, ref.eyelet_count)
        assert panel_delta <= 1, (name, got.panel_count, ref.panel_count)
    assert len(rows) == 9
