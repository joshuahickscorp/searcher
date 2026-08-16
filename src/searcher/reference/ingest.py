"""Ingest validated uploads into the Wave 1 object store."""

from __future__ import annotations

from pathlib import Path

from searcher.contracts.primitives import ArtifactRef
from searcher.core.config import Settings
from searcher.core.errors import InputError
from searcher.evidence.content_store import ContentStore
from searcher.reference.validation import validate_upload_bytes, validate_upload_path


def ingest_bytes(
    store: ContentStore,
    data: bytes,
    *,
    search_id: str,
    settings: Settings | None = None,
    declared_name: str | None = None,
) -> ArtifactRef:
    validated = validate_upload_bytes(data, declared_name=declared_name, settings=settings)
    digest = store.put_bytes(data, zone="incoming", campaign_id=search_id, private=True)
    return ArtifactRef(digest=digest, media_type=validated.media_type)


def ingest_paths(
    store: ContentStore,
    paths: list[Path],
    *,
    search_id: str,
    settings: Settings | None = None,
) -> list[ArtifactRef]:
    cfg = settings or Settings.from_env()
    if len(paths) < 1:
        raise InputError("at least one image is required")
    if len(paths) > cfg.max_images_per_search:
        raise InputError(f"too many images (max {cfg.max_images_per_search})")
    refs: list[ArtifactRef] = []
    for path in paths:
        data, _validated = validate_upload_path(path, settings=cfg)
        refs.append(ingest_bytes(store, data, search_id=search_id, settings=cfg))
    return refs
