"""Lazy Pillow helpers. Importing searcher.reference does not import PIL until used."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from searcher.core.config import Settings
from searcher.core.errors import MalformedContentError


def _pil() -> Any:
    from PIL import Image, ImageFilter, ImageOps, ImageStat

    return Image, ImageOps, ImageFilter, ImageStat


@dataclass(frozen=True, slots=True)
class DecodedImage:
    width: int
    height: int
    mode: str
    orientation: str
    colour_space: str
    rgb_png: bytes
    thumbnail_png: bytes
    exif_quarantine: dict[str, str]
    grayscale_preview: bytes


def decode_and_normalize(data: bytes, *, settings: Settings | None = None) -> DecodedImage:
    """Decode, refuse bombs, apply EXIF orientation, strip metadata."""
    cfg = settings or Settings.from_env()
    Image, ImageOps, _ImageFilter, _ImageStat = _pil()
    Image.MAX_IMAGE_PIXELS = cfg.max_image_pixels
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.width * image.height > cfg.max_image_pixels:
                raise MalformedContentError("decompression-bomb refusal: pixel count exceeds cap")
            if image.width > cfg.max_image_edge or image.height > cfg.max_image_edge:
                raise MalformedContentError("decoded dimension exceeds configured edge limit")
            if image.width <= 0 or image.height <= 0:
                raise MalformedContentError("decoded dimension is zero")
            orientation = "1"
            exif_dump: dict[str, str] = {}
            try:
                exif = image.getexif()
                if exif:
                    orientation = str(exif.get(274, 1) or 1)
                    for key, value in list(exif.items())[:32]:
                        exif_dump[str(key)] = str(value)[:200]
            except Exception:
                exif_dump = {}
            transposed = ImageOps.exif_transpose(image)
            rgb = transposed.convert("RGB")
            width, height = rgb.size
            rgb_buf = io.BytesIO()
            rgb.save(rgb_buf, format="PNG", optimize=False)
            thumb = rgb.copy()
            thumb.thumbnail((256, 256))
            thumb_buf = io.BytesIO()
            thumb.save(thumb_buf, format="PNG", optimize=False)
            gray = rgb.convert("L")
            gray.thumbnail((64, 64))
            gray_buf = io.BytesIO()
            gray.save(gray_buf, format="PNG")
            return DecodedImage(
                width=width,
                height=height,
                mode=str(transposed.mode),
                orientation=orientation,
                colour_space="sRGB",
                rgb_png=rgb_buf.getvalue(),
                thumbnail_png=thumb_buf.getvalue(),
                exif_quarantine=exif_dump,
                grayscale_preview=gray_buf.getvalue(),
            )
    except MalformedContentError:
        raise
    except Exception as exc:
        raise MalformedContentError(f"malformed image: {type(exc).__name__}") from exc


def open_rgb(png_bytes: bytes) -> Any:
    Image, _ops, _filt, _stat = _pil()
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def average_hash(png_bytes: bytes, size: int = 8) -> str:
    Image, ImageOps, _f, _s = _pil()
    image = Image.open(io.BytesIO(png_bytes)).convert("L")
    image = ImageOps.exif_transpose(image)
    image = image.resize((size, size))
    flatten = getattr(image, "get_flattened_data", None)
    pixels = list(flatten()) if callable(flatten) else list(image.getdata())
    mean = sum(pixels) / max(1, len(pixels))
    bits = "".join("1" if px >= mean else "0" for px in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b, strict=True))


def colour_histogram(png_bytes: bytes, bins: int = 8) -> list[float]:
    image = open_rgb(png_bytes)
    hist = image.histogram()
    # 256 bins per channel
    out: list[float] = []
    step = 256 // bins
    total = float(max(1, image.width * image.height))
    for channel in range(3):
        base = channel * 256
        for i in range(bins):
            out.append(sum(hist[base + i * step : base + (i + 1) * step]) / total)
    return out


def edge_stats(png_bytes: bytes) -> tuple[float, float]:
    Image, _ops, ImageFilter, ImageStat = _pil()
    image = Image.open(io.BytesIO(png_bytes)).convert("L")
    image.thumbnail((256, 256))
    edges = image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    var = float(stat.var[0]) if stat.var else 0.0
    mean = float(stat.mean[0]) if stat.mean else 0.0
    return var, mean / 255.0


def exposure_mean(png_bytes: bytes) -> float:
    Image, _o, _f, ImageStat = _pil()
    image = Image.open(io.BytesIO(png_bytes)).convert("L")
    image.thumbnail((256, 256))
    return float(ImageStat.Stat(image).mean[0]) / 255.0


def silhouette_mask_png(png_bytes: bytes) -> bytes:
    """Cheap corner-background difference. DIAGNOSTIC, not product segmentation."""
    Image, _o, ImageFilter, _s = _pil()
    from PIL import ImageChops

    rgba = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    rgba.thumbnail((512, 512))
    width, height = rgba.size
    corner = max(1, min(width, height) // 50)
    samples = [
        rgba.crop((0, 0, corner, corner)),
        rgba.crop((width - corner, 0, width, corner)),
        rgba.crop((0, height - corner, corner, height)),
        rgba.crop((width - corner, height - corner, width, height)),
    ]
    total = [0, 0, 0]
    count = 0
    for sample in samples:
        pixels = sample.tobytes()
        for offset in range(0, len(pixels), 4):
            total[0] += pixels[offset]
            total[1] += pixels[offset + 1]
            total[2] += pixels[offset + 2]
        count += sample.width * sample.height
    background = tuple(round(value / max(1, count)) for value in total)
    flat = Image.new("RGB", rgba.size, background)
    difference = ImageChops.difference(rgba.convert("RGB"), flat).convert("L")
    mask = difference.point(lambda value: 255 if value >= 18 else 0)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


def subject_bbox(png_bytes: bytes) -> tuple[int, int, int, int]:
    """Bounding box of the silhouette; full frame if empty."""
    Image, _o, _f, _s = _pil()
    mask = Image.open(io.BytesIO(silhouette_mask_png(png_bytes))).convert("L")
    bbox = mask.getbbox()
    if bbox is None:
        rgb = open_rgb(png_bytes)
        return (0, 0, rgb.width, rgb.height)
    # mask may be thumbnail-sized; scale back
    rgb = open_rgb(png_bytes)
    sx = rgb.width / max(1, mask.width)
    sy = rgb.height / max(1, mask.height)
    x0, y0, x1, y1 = bbox
    return (
        max(0, int(x0 * sx)),
        max(0, int(y0 * sy)),
        max(1, int((x1 - x0) * sx)),
        max(1, int((y1 - y0) * sy)),
    )


def crop_png(png_bytes: bytes, region: tuple[int, int, int, int]) -> bytes:
    image = open_rgb(png_bytes)
    x, y, w, h = region
    cropped = image.crop((x, y, x + w, y + h))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()
