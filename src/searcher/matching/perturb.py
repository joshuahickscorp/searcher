"""Photometric and structural perturbations for metamorphic tests."""

from __future__ import annotations

import io
from typing import Any

from searcher.matching.synth import ShoeSpec, render_shoe
from searcher.reference.imaging import open_rgb


def _dump(image: Any, *, fmt: str = "PNG", **kwargs: object) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def resize(png: bytes, scale: float = 0.8) -> bytes:
    image = open_rgb(png)
    size = (max(8, int(image.width * scale)), max(8, int(image.height * scale)))
    return _dump(image.resize(size))


def jpeg(png: bytes, quality: int = 70) -> bytes:
    return _dump(open_rgb(png), fmt="JPEG", quality=quality)


def mild_crop(png: bytes, px: int = 10) -> bytes:
    image = open_rgb(png)
    return _dump(image.crop((px, px, image.width - px, image.height - px)))


def mild_rotate(png: bytes, degrees: float = 5.0) -> bytes:
    image = open_rgb(png)
    bg = image.getpixel((0, 0))
    return _dump(image.rotate(degrees, expand=True, fillcolor=bg))


def brightness(png: bytes, factor: float = 1.15) -> bytes:
    from PIL import ImageEnhance

    return _dump(ImageEnhance.Brightness(open_rgb(png)).enhance(factor))


def colour_temperature(png: bytes, factor: float = 1.2) -> bytes:
    from PIL import ImageEnhance

    return _dump(ImageEnhance.Color(open_rgb(png)).enhance(factor))


def background_change(png: bytes, colour: tuple[int, int, int] = (40, 80, 120)) -> bytes:

    image = open_rgb(png)
    bg = image.getpixel((2, 2))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixel = pixels[x, y]
            if all(abs(int(pixel[i]) - int(bg[i])) < 18 for i in range(3)):
                pixels[x, y] = colour
    return _dump(image)


def watermark(png: bytes, text: str = "WATERMARK") -> bytes:
    from PIL import ImageDraw, ImageFont

    image = open_rgb(png)
    draw = ImageDraw.Draw(image)
    try:
        font: Any = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    draw.text((image.width // 3, image.height - 28), text, fill=(180, 180, 184), font=font)
    return _dump(image)


def screenshot_frame(png: bytes) -> bytes:
    from PIL import Image, ImageDraw

    inner = open_rgb(png)
    # Light bezel so isolation still finds the product (screenshot chrome, not a new scene).
    canvas = Image.new("RGB", (inner.width + 24, inner.height + 36), (214, 214, 218))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, 16), fill=(208, 208, 212))
    canvas.paste(inner, (12, 22))
    return _dump(canvas)


def structural_variant(base: ShoeSpec, kind: str) -> ShoeSpec:
    from dataclasses import replace

    if kind == "panel-count":
        return replace(base, name=f"{base.name}-panels", panels=base.panels + 1)
    if kind == "eyelet-count":
        return replace(base, name=f"{base.name}-eyelets", eyelets=base.eyelets + 2)
    if kind == "outsole":
        return replace(base, name=f"{base.name}-outsole", outsole_height=base.outsole_height + 0.10)
    if kind == "logo":
        return replace(base, name=f"{base.name}-logo", logo_pos=(0.30, 0.62))
    if kind == "heel":
        other = "block" if base.heel_cut != "block" else "rounded"
        return replace(base, name=f"{base.name}-heel", heel_cut=other)
    if kind == "label":
        return replace(base, name=f"{base.name}-label", label_code="ZZZ999")
    if kind == "colourway":
        return replace(base, name=f"{base.name}-colour", body=(160, 40, 40), panel=(190, 70, 60))
    raise ValueError(kind)


def render_variant(base: ShoeSpec, kind: str, *, view: str = "lateral") -> bytes:
    return render_shoe(structural_variant(base, kind), view=view)
