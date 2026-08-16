"""Side-by-side comparison artifacts showing parts that agreed and disagreed."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from searcher.core.ids import sha256_hex
from searcher.reference.imaging import open_rgb


@dataclass
class ComparisonArtifact:
    digest: str
    png: bytes
    agreed: list[str]
    disagreed: list[str]
    missing: list[str]
    caption: str


def render_comparison(
    *,
    reference_png: bytes,
    candidate_png: bytes,
    agreed: list[str],
    disagreed: list[str],
    missing: list[str],
    title: str = "comparison",
) -> ComparisonArtifact:
    from PIL import Image, ImageDraw, ImageFont

    left = open_rgb(reference_png)
    right = open_rgb(candidate_png)
    left.thumbnail((360, 220))
    right.thumbnail((360, 220))
    pad = 16
    header = 36
    footer = 18 + 16 * (1 + len(agreed[:6]) + len(disagreed[:6]) + len(missing[:6]))
    width = left.width + right.width + pad * 3
    height = max(left.height, right.height) + header + footer + pad
    canvas = Image.new("RGB", (width, height), (246, 246, 244))
    draw = ImageDraw.Draw(canvas)
    try:
        font: Any = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14)
        small: Any = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((pad, 8), "Reference", fill=(20, 20, 20), font=font)
    draw.text((pad * 2 + left.width, 8), "Candidate", fill=(20, 20, 20), font=font)
    canvas.paste(left, (pad, header))
    canvas.paste(right, (pad * 2 + left.width, header))
    y = header + max(left.height, right.height) + 8
    draw.text((pad, y), title[:80], fill=(20, 20, 20), font=small)
    y += 16
    for label, items, colour in (
        ("agreed", agreed[:6], (24, 96, 48)),
        ("disagreed", disagreed[:6], (140, 40, 32)),
        ("missing", missing[:6], (90, 90, 90)),
    ):
        if not items:
            continue
        draw.text((pad, y), f"{label}: " + ", ".join(items), fill=colour, font=small)
        y += 16
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    png = buf.getvalue()
    return ComparisonArtifact(
        digest=sha256_hex(png),
        png=png,
        agreed=list(agreed),
        disagreed=list(disagreed),
        missing=list(missing),
        caption=title,
    )
