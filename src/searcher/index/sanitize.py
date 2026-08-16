"""Index content is untrusted third-party text. Never private paths or HTML."""

from __future__ import annotations

import json
from typing import Any

from searcher.contracts.models import ListingCandidate, ListingImage
from searcher.core.errors import CrossCampaignAccessError
from searcher.core.ids import canonical_dumps, sha256_hex

_PRIVATE_KEYS = frozenset(
    {
        "path",
        "fixture_root",
        "image_paths",
        "local_path",
        "user_upload",
        "private_path",
        "upload_path",
    }
)
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "file://",
    "put_private",
    "user_upload",
    "\\\\",
)


def listing_content_digest(candidate: ListingCandidate) -> str:
    images = sorted(image.content_digest or image.remote_url for image in candidate.images)
    payload = {
        "url": candidate.canonical_url,
        "title": candidate.title.value if candidate.title is not None else None,
        "description": candidate.description.value if candidate.description is not None else None,
        "images": images,
        "source": candidate.source_adapter,
        "listing_id": candidate.source_listing_id,
    }
    return sha256_hex(canonical_dumps(payload).encode("utf-8"))


def hypothesis_digest_payload(
    *,
    category: str,
    brand: object,
    model: object,
    line: object,
    year: object,
    colourway: object,
    aliases: list[str],
) -> str:
    payload = {
        "category": category,
        "brand": brand,
        "model": model,
        "line": line,
        "year": year,
        "colourway": colourway,
        "aliases": sorted(aliases),
    }
    return sha256_hex(canonical_dumps(payload).encode("utf-8"))


def refuse_private(payload: dict[str, Any], *, search_id: str | None = None) -> None:
    blob = json.dumps(payload, default=str)
    if any(marker in blob for marker in _PRIVATE_MARKERS):
        raise CrossCampaignAccessError(
            "the warm index refuses private paths and campaign-private artifacts",
            search_id=search_id or "index",
        )
    if "<html" in blob.lower() or "<script" in blob.lower():
        raise CrossCampaignAccessError(
            "the warm index refuses HTML; listing text is data, not markup",
            search_id=search_id or "index",
        )


def _strip_meta(meta: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in meta.items() if key not in _PRIVATE_KEYS}


def _public_image(image: ListingImage) -> dict[str, object]:
    return {
        "listing_image_id": image.listing_image_id,
        "candidate_id": image.candidate_id,
        "remote_url": image.remote_url,
        "content_digest": image.content_digest,
        "perceptual_hash": image.perceptual_hash,
        "width": image.width,
        "height": image.height,
        "role": image.role.value,
        "duplicate_family_id": image.duplicate_family_id,
        "schema_version": image.schema_version,
    }


def public_listing_payload(candidate: ListingCandidate) -> dict[str, Any]:
    data = candidate.model_dump(mode="json")
    data["seller_metadata"] = _strip_meta(dict(data.get("seller_metadata") or {}))
    data["images"] = [_public_image(image) for image in candidate.images]
    data.pop("source_evidence", None)
    refuse_private(data)
    return data
