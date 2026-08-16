"""Upload validation matrix: magic bytes, bombs, traversal, malformed, oversized."""

from __future__ import annotations

import io
import struct

import pytest
from PIL import Image

from searcher.core.config import Settings
from searcher.core.errors import InputError, MalformedContentError
from searcher.reference.validation import (
    refuse_path_name,
    validate_upload_bytes,
    validate_upload_path,
)


def _png(width: int = 16, height: int = 16) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 20, 30)).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def test_png_and_jpeg_accepted(settings: Settings) -> None:
    png = validate_upload_bytes(_png(), declared_name="x.png", settings=settings)
    assert png.media_type == "image/png"
    jpeg = validate_upload_bytes(_jpeg(), declared_name="x.jpg", settings=settings)
    assert jpeg.media_type == "image/jpeg"


def test_wrong_extension_still_uses_magic(settings: Settings) -> None:
    got = validate_upload_bytes(_png(), declared_name="notes.txt", settings=settings)
    assert got.media_type == "image/png"


def test_declared_type_is_ignored(settings: Settings) -> None:
    got = validate_upload_bytes(
        _jpeg(), declared_name="x.png", declared_type="image/png", settings=settings
    )
    assert got.media_type == "image/jpeg"


@pytest.mark.parametrize(
    "payload",
    [
        b"%PDF-1.4",
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"<?xml version='1.0'?>",
        b"<!DOCTYPE html><html></html>",
        b"MZ\x90\x00",
        b"\x7fELF",
        b"PK\x03\x04payload",
        b"#!/bin/sh\necho hi\n",
    ],
)
def test_unsafe_magic_rejected(payload: bytes, settings: Settings) -> None:
    with pytest.raises(InputError):
        validate_upload_bytes(payload, settings=settings)


def test_empty_and_unknown_rejected(settings: Settings) -> None:
    with pytest.raises(MalformedContentError):
        validate_upload_bytes(b"", settings=settings)
    with pytest.raises(MalformedContentError):
        validate_upload_bytes(b"not-an-image", settings=settings)


def test_oversized_upload_rejected(settings: Settings) -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"x" * (settings.max_upload_bytes + 1)
    with pytest.raises(InputError, match="size cap"):
        validate_upload_bytes(data, settings=settings)


def test_png_bomb_header_rejected(settings: Settings) -> None:
    # Craft IHDR claiming a huge canvas without a real pixel buffer.
    # 7000² exceeds the pixel cap but stays under the per-edge cap.
    ihdr = struct.pack(">IIBBBBB", 7000, 7000, 8, 2, 0, 0, 0)
    # CRC ignored by our header parser.
    blob = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"
    with pytest.raises(MalformedContentError, match="bomb"):
        validate_upload_bytes(blob, settings=settings)


def test_path_traversal_refused() -> None:
    with pytest.raises(InputError):
        refuse_path_name("../../etc/passwd")
    with pytest.raises(InputError):
        refuse_path_name("/etc/passwd")
    with pytest.raises(InputError):
        refuse_path_name("foo/../../../secret")


def test_validate_path_missing(tmp_path, settings: Settings) -> None:
    missing = tmp_path / "nope.png"
    with pytest.raises(InputError):
        validate_upload_path(missing, settings=settings)
