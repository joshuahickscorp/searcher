"""Synthetic footwear diagrams for fixtures and metamorphic tests.

The matcher never reads ShoeSpec; it only sees pixels. This renderer exists
so hard negatives and invariance pairs can be generated without scraping.
Parts are drawn as distinct regions so classical measurements can see them.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class ShoeSpec:
    name: str
    body: tuple[int, int, int] = (52, 56, 46)
    panel: tuple[int, int, int] = (88, 92, 70)
    sole: tuple[int, int, int] = (18, 18, 20)
    heel: tuple[int, int, int] = (40, 38, 34)
    logo: tuple[int, int, int] = (232, 196, 48)
    eyelets: int = 6
    panels: int = 3
    outsole_height: float = 0.16
    heel_width: float = 0.14
    heel_cut: str = "notched"
    logo_pos: tuple[float, float] = (0.68, 0.40)
    logo_kind: str = "bar"
    tread: str = "parallel"
    label_code: str | None = "3SH107"
    background: tuple[int, int, int] = (210, 210, 214)
    width: int = 480
    height: int = 280


REFERENCE_SHOE = ShoeSpec(name="reference")
ADJACENT_SHOE = ShoeSpec(
    name="adjacent",
    eyelets=8,
    panels=4,
    outsole_height=0.26,
    heel_cut="block",
    logo_pos=(0.32, 0.58),
    logo_kind="triangle",
    tread="waffle",
    heel_width=0.22,
    label_code="B01X99",
)
SEASON_SHOE = replace(REFERENCE_SHOE, name="season", heel=(62, 48, 32))
COLOURWAY_SHOE = replace(
    REFERENCE_SHOE,
    name="colourway",
    body=(140, 44, 40),
    panel=(176, 70, 58),
    logo=(250, 230, 80),
)
CLOSE_COUNTERFEIT_SHOE = replace(
    REFERENCE_SHOE,
    name="close_counterfeit",
    logo_pos=(0.78, 0.22),
    logo_kind="circle",
    label_code="XXXXXX",
)
REPLICA_SHOE = replace(
    REFERENCE_SHOE,
    name="replica",
    eyelets=4,
    panels=2,
    heel_cut="rounded",
    logo_kind="circle",
    logo_pos=(0.78, 0.28),
    label_code="XXXXXX",
    outsole_height=0.12,
)


def _pil() -> Any:
    from PIL import Image, ImageDraw, ImageFont

    return Image, ImageDraw, ImageFont


def render_shoe(spec: ShoeSpec, *, view: str = "lateral") -> bytes:
    Image, ImageDraw, ImageFont = _pil()
    image = Image.new("RGB", (spec.width, spec.height), spec.background)
    draw = ImageDraw.Draw(image)
    if view == "label":
        _draw_label(draw, spec, ImageFont)
    elif view == "sole":
        _draw_sole(draw, spec)
    elif view == "heel":
        _draw_heel_view(draw, spec)
    elif view == "front":
        _draw_front(draw, spec)
    else:
        _draw_lateral(draw, spec)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _draw_lateral(draw: Any, spec: ShoeSpec) -> None:
    # Upper body: rounded rectangle, not a covering ellipse.
    ux0, uy0, ux1, uy1 = 48, 78, 360, 188
    draw.rounded_rectangle(
        (ux0, uy0, ux1, uy1), radius=36, fill=spec.body, outline=(16, 16, 16), width=2
    )
    # Toe
    draw.ellipse((40, 88, 130, 180), fill=spec.panel, outline=(16, 16, 16), width=2)
    # Mid panels with thick black seams.
    mid_l, mid_r, mid_t, mid_b = 132, 300, 92, 176
    n = max(1, spec.panels)
    span = mid_r - mid_l
    pw = span / n
    for index in range(n):
        px0 = int(mid_l + index * pw)
        px1 = int(mid_l + (index + 1) * pw) - 1
        draw.rectangle((px0, mid_t, px1, mid_b), fill=spec.panel, outline=(8, 8, 8), width=1)
        if index > 0:
            sx = int(mid_l + index * pw)
            draw.line((sx, mid_t, sx, mid_b), fill=(0, 0, 0), width=5)
    # Eye-stay band + isolated eyelets.
    draw.rectangle((150, 86, 290, 114), fill=(30, 30, 32))
    if spec.eyelets > 0:
        xs = _spread(160, 280, spec.eyelets)
        for cx in xs:
            draw.ellipse(
                (cx - 8, 92, cx + 8, 108), fill=(236, 236, 238), outline=(0, 0, 0), width=2
            )
    # Heel attached on the right, past the upper so its silhouette is unique.
    hx1 = 438
    hx0 = int(hx1 - spec.heel_width * spec.width) - 8
    hy0, hy1 = 82, 198
    if spec.heel_cut == "block":
        draw.rectangle((hx0, hy0, hx1, hy1), fill=spec.heel, outline=(8, 8, 8), width=2)
    elif spec.heel_cut == "rounded":
        draw.ellipse((hx0, hy0, hx1, hy1), fill=spec.heel, outline=(8, 8, 8), width=2)
    else:
        mid_y = (hy0 + hy1) // 2
        draw.polygon(
            [
                (hx0 + 28, hy0),
                (hx1, hy0),
                (hx1, hy1),
                (hx0 + 10, hy1),
                (hx0 - 12, mid_y),
            ],
            fill=spec.heel,
            outline=(8, 8, 8),
        )
    # Outsole sits strictly below the upper so height is measurable.
    sole_h = max(14, int(round(spec.outsole_height * 160)))
    sy0 = 196
    sy1 = sy0 + sole_h
    draw.rectangle((44, sy0, 400, sy1), fill=spec.sole, outline=(4, 4, 4), width=2)
    _draw_tread(draw, spec, 50, sy0 + 2, 394, sy1 - 2)
    _draw_logo(draw, spec, ux0, uy0, ux1, uy1)


def _draw_front(draw: Any, spec: ShoeSpec) -> None:
    draw.rounded_rectangle(
        (150, 36, 330, 230), radius=40, fill=spec.body, outline=(16, 16, 16), width=2
    )
    draw.rectangle((188, 58, 292, 150), fill=spec.panel, outline=(10, 10, 10), width=2)
    draw.rectangle((200, 62, 280, 92), fill=(30, 30, 32))
    xs = _spread(210, 270, max(2, spec.eyelets // 2))
    for cx in xs:
        draw.ellipse((cx - 7, 68, cx + 7, 84), fill=(236, 236, 238), outline=(0, 0, 0), width=2)
    _draw_logo(draw, spec, 150, 36, 330, 230)


def _draw_heel_view(draw: Any, spec: ShoeSpec) -> None:
    if spec.heel_cut == "block":
        draw.rectangle((168, 46, 312, 232), fill=spec.heel, outline=(8, 8, 8), width=3)
    elif spec.heel_cut == "rounded":
        draw.ellipse((168, 46, 312, 232), fill=spec.heel, outline=(8, 8, 8), width=3)
    else:
        draw.polygon(
            [(188, 46), (312, 46), (312, 232), (168, 232), (148, 140)],
            fill=spec.heel,
            outline=(8, 8, 8),
        )
    _draw_logo(draw, spec, 168, 46, 312, 232)


def _draw_sole(draw: Any, spec: ShoeSpec) -> None:
    draw.ellipse((36, 78, 444, 202), fill=spec.sole, outline=(6, 6, 6), width=2)
    _draw_tread(draw, spec, 56, 92, 424, 188)


def _draw_label(draw: Any, spec: ShoeSpec, ImageFont: Any) -> None:
    draw.rectangle((70, 64, 410, 216), fill=(250, 248, 240), outline=(20, 20, 20), width=3)
    code = spec.label_code or ""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((100, 108), code, fill=(20, 20, 20), font=font)
    seed = sum(ord(ch) for ch in code) or 1
    x = 100
    for index, ch in enumerate(code):
        w = 6 + (ord(ch) + seed + index) % 10
        draw.rectangle((x, 172, x + w, 198), fill=(12, 12, 12))
        x += w + 4


def _draw_logo(draw: Any, spec: ShoeSpec, x0: int, y0: int, x1: int, y1: int) -> None:
    cx = int(x0 + spec.logo_pos[0] * (x1 - x0))
    cy = int(y0 + spec.logo_pos[1] * (y1 - y0))
    if spec.logo_kind == "triangle":
        draw.polygon(
            [(cx, cy - 16), (cx + 16, cy + 14), (cx - 16, cy + 14)],
            fill=spec.logo,
            outline=(20, 20, 10),
        )
    elif spec.logo_kind == "circle":
        draw.ellipse(
            (cx - 14, cy - 14, cx + 14, cy + 14),
            fill=spec.logo,
            outline=(20, 20, 10),
            width=2,
        )
    else:
        draw.rectangle(
            (cx - 20, cy - 7, cx + 20, cy + 7),
            fill=spec.logo,
            outline=(20, 20, 10),
            width=2,
        )


def _draw_tread(draw: Any, spec: ShoeSpec, x0: int, y0: int, x1: int, y1: int) -> None:
    if spec.tread == "waffle":
        y = y0
        while y < y1 - 6:
            x = x0
            while x < x1 - 6:
                draw.rectangle((x, y, x + 7, y + 7), outline=(110, 110, 110))
                x += 11
            y += 11
    elif spec.tread == "circle":
        y = y0 + 8
        while y < y1:
            x = x0 + 8
            while x < x1:
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline=(120, 120, 120))
                x += 14
            y += 14
    else:
        y = y0 + 3
        while y < y1:
            draw.line((x0, y, x1, y), fill=(90, 90, 90), width=2)
            y += 5


def _spread(start: int, end: int, count: int) -> list[int]:
    if count <= 1:
        return [(start + end) // 2]
    return [int(start + i * (end - start) / (count - 1)) for i in range(count)]


def render_views(spec: ShoeSpec) -> dict[str, bytes]:
    return {
        "lateral": render_shoe(spec, view="lateral"),
        "heel": render_shoe(spec, view="heel"),
        "sole": render_shoe(spec, view="sole"),
        "label": render_shoe(spec, view="label"),
        "front": render_shoe(spec, view="front"),
    }
