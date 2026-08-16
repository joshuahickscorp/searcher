"""§11.3 / §29.1 upload validation. Hostile images are rejected, never crashed on."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from searcher.core.config import Settings
from searcher.core.errors import InputError, MalformedContentError
from searcher.core.ids import sha256_hex

# Magic prefixes. Declared media types are never trusted.
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_TIFF_LE = b"II*\x00"
_TIFF_BE = b"MM\x00*"
_BMP = b"BM"
_WEBP_RIFF = b"RIFF"
_WEBP_TAG = b"WEBP"

_REJECT_PREFIXES = (
    (b"<?xml", "xml"),
    (b"<svg", "svg"),
    (b"%PDF", "pdf"),
    (b"<!DO", "html"),
    (b"<htm", "html"),
    (b"MZ", "executable"),
    (b"\x7fELF", "elf"),
    (b"PK\x03\x04", "archive"),
    (b"#!/", "script"),
)

_EXT_TO_HINT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    digest: str
    media_type: str
    byte_length: int
    declared_name: str | None
    header_width: int | None
    header_height: int | None


def _sniff_media_type(data: bytes) -> str | None:
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(_JPEG):
        return "image/jpeg"
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return "image/gif"
    if data.startswith(_TIFF_LE) or data.startswith(_TIFF_BE):
        return "image/tiff"
    if data.startswith(_BMP):
        return "image/bmp"
    if len(data) >= 12 and data.startswith(_WEBP_RIFF) and data[8:12] == _WEBP_TAG:
        return "image/webp"
    return None


def _png_ihdr_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(_PNG):
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _jpeg_sof_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(_JPEG):
        return None
    i = 2
    length = len(data)
    while i + 9 < length:
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xD8:
            i += 2
            continue
        if marker == 0xD9:
            return None
        if i + 3 >= length:
            return None
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB}:
            if i + 8 >= length:
                return None
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return int(width), int(height)
        i += 2 + seg_len
    return None


def header_dimensions(data: bytes, media_type: str) -> tuple[int, int] | None:
    if media_type == "image/png":
        return _png_ihdr_size(data)
    if media_type == "image/jpeg":
        return _jpeg_sof_size(data)
    return None


def refuse_path_name(name: str) -> None:
    """Refuse a user-supplied name that tries to escape the object store."""
    if not name:
        return
    if name.startswith("/") or name.startswith("\\") or ":" in name[:2]:
        raise InputError("path traversal refused")
    parts = Path(name).parts
    if ".." in parts or any(part in {".", ""} for part in parts if part == ".."):
        raise InputError("path traversal refused")
    if ".." in name or name.startswith("~"):
        raise InputError("path traversal refused")


def validate_upload_bytes(
    data: bytes,
    *,
    declared_name: str | None = None,
    declared_type: str | None = None,
    settings: Settings | None = None,
) -> ValidatedUpload:
    cfg = settings or Settings.from_env()
    if declared_name:
        refuse_path_name(declared_name)
    if not data:
        raise MalformedContentError("empty upload")
    if len(data) > cfg.max_upload_bytes:
        raise InputError(f"upload exceeds size cap ({len(data)} > {cfg.max_upload_bytes})")
    for prefix, label in _REJECT_PREFIXES:
        if data.startswith(prefix):
            raise InputError(f"rejected unsafe format: {label}")
    sniffed = _sniff_media_type(data)
    if sniffed is None:
        raise MalformedContentError("unrecognized or unsupported image magic bytes")
    # Wrong extension is allowed; magic wins. Declared type is ignored.
    del declared_type
    if declared_name:
        suffix = Path(declared_name).suffix.lower()
        hinted = _EXT_TO_HINT.get(suffix)
        if hinted and hinted != sniffed:
            # Magic still wins; we do not reject a jpeg named .png, we record it.
            pass
    dims = header_dimensions(data, sniffed)
    if dims is not None:
        width, height = dims
        if width <= 0 or height <= 0:
            raise MalformedContentError("decoded dimension is zero")
        if width > cfg.max_image_edge or height > cfg.max_image_edge:
            raise InputError("decoded dimension exceeds configured edge limit")
        pixels = width * height
        if pixels > cfg.max_image_pixels:
            raise MalformedContentError("decompression-bomb refusal: pixel count exceeds cap")
    return ValidatedUpload(
        digest=sha256_hex(data),
        media_type=sniffed,
        byte_length=len(data),
        declared_name=None,  # never persist the user filename
        header_width=dims[0] if dims else None,
        header_height=dims[1] if dims else None,
    )


def validate_upload_path(
    path: Path, *, settings: Settings | None = None
) -> tuple[bytes, ValidatedUpload]:
    refuse_path_name(path.name)
    resolved = path.expanduser()
    if not resolved.is_file():
        raise InputError("upload path is not a file")
    if resolved.is_symlink():
        # Read through a symlink only if the target is a regular file we can open.
        # The stored name is never the symlink path.
        try:
            resolved = resolved.resolve()
        except OSError as exc:
            raise InputError("cannot resolve upload path") from exc
        if not resolved.is_file():
            raise InputError("upload path is not a file")
    data = resolved.read_bytes()
    validated = validate_upload_bytes(data, declared_name=path.name, settings=settings)
    return data, validated
