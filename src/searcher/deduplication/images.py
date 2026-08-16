"""Image families by cryptographic digest and a cheap content fingerprint."""

from __future__ import annotations

from searcher.contracts.models import ListingImage
from searcher.core.ids import sha256_hex


def content_fingerprint(data: bytes) -> str:
    """Deterministic 64-sample byte fingerprint. Not a DCT pHash."""
    if not data:
        return ""
    step = max(1, len(data) // 64)
    samples = [data[index] for index in range(0, min(len(data), step * 64), step)]
    mean = sum(samples) / len(samples)
    bits = "".join("1" if sample >= mean else "0" for sample in samples)
    return f"{int(bits, 2):016x}"


def image_family_id(image: ListingImage) -> str:
    if image.duplicate_family_id:
        return image.duplicate_family_id
    if image.content_digest:
        return image.content_digest
    if image.perceptual_hash:
        return f"phash:{image.perceptual_hash}"
    return sha256_hex(image.remote_url.encode("utf-8"))


def assign_families(images: list[ListingImage]) -> list[ListingImage]:
    by_digest: dict[str, str] = {}
    out: list[ListingImage] = []
    for image in images:
        key = image.content_digest or image.perceptual_hash or sha256_hex(image.remote_url.encode())
        family = by_digest.setdefault(key, image_family_id(image))
        out.append(image.model_copy(update={"duplicate_family_id": family}))
    return out
