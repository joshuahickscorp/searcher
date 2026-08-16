"""Content-store paths, traversal refusal, zones, size cap."""

from __future__ import annotations

from pathlib import Path

import pytest

from searcher.core.errors import PathEscapeError, StoragePressureError
from searcher.evidence.content_store import ContentStore


def test_put_get_roundtrip(store: ContentStore) -> None:
    digest = store.put_bytes(b"hello-searcher", zone="incoming", campaign_id="c1")
    assert store.exists(digest)
    assert store.get(digest, campaign_id="c1") == b"hello-searcher"
    path = store.path_for(digest)
    assert path.as_posix().endswith(f"objects/sha256/{digest[:2]}/{digest[2:4]}/{digest}")


def test_traversal_in_digest_refused(store: ContentStore) -> None:
    with pytest.raises(PathEscapeError):
        store.path_for("../" + "a" * 60)
    with pytest.raises(PathEscapeError):
        store.path_for(".." + "a" * 62)


def test_refuse_external_path(store: ContentStore) -> None:
    with pytest.raises(PathEscapeError):
        store.refuse_external_path("../../etc/passwd")
    with pytest.raises(PathEscapeError):
        store.refuse_external_path("/etc/passwd")


def test_private_name_traversal(store: ContentStore) -> None:
    with pytest.raises(PathEscapeError):
        store.put_private("camp-a", "../escape", b"x")
    with pytest.raises(PathEscapeError):
        store.get_private("camp-a", "../../etc/passwd")


def test_symlink_escape_refused(store: ContentStore, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret"
    outside.write_text("secret", encoding="utf-8")
    link = store.root / "incoming" / "escape"
    link.symlink_to(outside)
    with pytest.raises(PathEscapeError):
        store._safe_under(store.root, link)  # noqa: SLF001


def test_size_cap(tmp_path: Path) -> None:
    store = ContentStore(tmp_path, max_object_bytes=8, disk_margin_bytes=1)
    with pytest.raises(StoragePressureError):
        store.put_bytes(b"0123456789", zone="incoming")


def test_unknown_zone(store: ContentStore) -> None:
    with pytest.raises(PathEscapeError):
        store.put_bytes(b"x", zone="not-a-zone")
