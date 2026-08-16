"""Content-addressed object store: sha256 layout, zones, isolation, refusal."""

from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from searcher.core.errors import CrossCampaignAccessError, PathEscapeError, StoragePressureError
from searcher.core.ids import sha256_hex

ZONES = (
    "incoming",
    "quarantine",
    "verified",
    "derived",
    "temporary",
    "exports",
)

_DIGEST_HEX_LEN = 64


@dataclass(frozen=True, slots=True)
class StoreStat:
    root: str
    object_count: int
    byte_count: int
    zones: dict[str, int]
    disk_free: int
    disk_margin: int


class ContentStore:
    """Filesystem CAS at ``<root>/objects/sha256/ab/cd/<digest>`` plus §27.3 zones."""

    def __init__(
        self,
        root: Path | str,
        *,
        disk_margin_bytes: int = 256 * 1024 * 1024,
        max_object_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.root = Path(root).resolve()
        self.disk_margin_bytes = disk_margin_bytes
        self.max_object_bytes = max_object_bytes
        self.objects = self.root / "objects" / "sha256"
        self.zones = {name: self.root / name for name in ZONES}
        self.campaigns = self.root / "campaigns"
        self._index = self.root / "object_index.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)
        self.campaigns.mkdir(parents=True, exist_ok=True)
        for path in self.zones.values():
            path.mkdir(parents=True, exist_ok=True)
        if not self._index.exists():
            self._write_index({})

    def _read_index(self) -> dict[str, Any]:
        raw = json.loads(self._index.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return raw

    def _write_index(self, payload: dict[str, Any]) -> None:
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(self._index)

    def _safe_under(self, root: Path, candidate: Path) -> Path:
        root_resolved = root.resolve()
        # Reject traversal tokens before resolution.
        parts = candidate.parts
        if ".." in parts:
            raise PathEscapeError(f"path traversal refused: {candidate}")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise PathEscapeError(f"path escapes store root: {candidate}") from exc
        if resolved.is_symlink():
            target = resolved.resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError as exc:
                raise PathEscapeError(f"symlink escapes store root: {candidate}") from exc
        return resolved

    def _assert_digest(self, digest: str) -> str:
        if not digest or any(ch in digest for ch in ("/", "\\", ".", os.sep)):
            raise PathEscapeError(f"refusing digest that looks like a path: {digest!r}")
        if len(digest) != _DIGEST_HEX_LEN or any(c not in "0123456789abcdef" for c in digest):
            raise PathEscapeError(f"digest is not a sha256 hex: {digest!r}")
        return digest

    def path_for(self, digest: str) -> Path:
        digest = self._assert_digest(digest)
        path = self.objects / digest[:2] / digest[2:4] / digest
        return self._safe_under(self.root, path)

    def exists(self, digest: str) -> bool:
        return self.path_for(digest).is_file()

    def check_disk_margin(self, additional: int) -> None:
        usage = shutil.disk_usage(self.root)
        if usage.free - additional < self.disk_margin_bytes:
            raise StoragePressureError(
                f"disk margin would be crossed (free={usage.free}, "
                f"additional={additional}, margin={self.disk_margin_bytes})"
            )

    def put_bytes(
        self,
        data: bytes,
        *,
        zone: str = "incoming",
        campaign_id: str | None = None,
        private: bool = True,
        extra_meta: dict[str, str] | None = None,
    ) -> str:
        if zone not in ZONES:
            raise PathEscapeError(f"unknown zone: {zone}")
        if len(data) > self.max_object_bytes:
            raise StoragePressureError(
                f"object exceeds size cap ({len(data)} > {self.max_object_bytes})"
            )
        self.check_disk_margin(len(data))
        digest = sha256_hex(data)
        dest = self.path_for(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            tmp = dest.with_suffix(".partial")
            tmp.write_bytes(data)
            tmp.replace(dest)
            dest.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        self.link_zone(digest, zone)
        index = self._read_index()
        owners = list(index.get(digest, {}).get("owners") or [])
        if campaign_id and campaign_id not in owners:
            owners.append(campaign_id)
        index[digest] = {
            "owners": owners,
            "private": bool(private),
            "byte_length": len(data),
            "zone": zone,
            "extra": extra_meta or {},
        }
        self._write_index(index)
        if campaign_id and private:
            self._record_private(campaign_id, digest, data=None)
        return digest

    def link_zone(self, digest: str, zone: str) -> Path:
        if zone not in ZONES:
            raise PathEscapeError(f"unknown zone: {zone}")
        source = self.path_for(digest)
        if not source.is_file():
            raise FileNotFoundError(digest)
        dest = self._safe_under(self.zones[zone], self.zones[zone] / digest)
        if dest.exists() or dest.is_symlink():
            return dest
        os.link(source, dest)
        return dest

    def get(self, digest: str, *, campaign_id: str | None = None) -> bytes:
        if campaign_id is not None and not self.owned_by(digest, campaign_id):
            raise CrossCampaignAccessError(
                "campaign cannot read another campaign's private artifact",
                search_id=campaign_id,
            )
        path = self.path_for(digest)
        if not path.is_file():
            raise FileNotFoundError(digest)
        return path.read_bytes()

    def owned_by(self, digest: str, campaign_id: str) -> bool:
        index = self._read_index()
        entry = index.get(digest)
        if entry is None:
            return False
        owners = list(entry.get("owners") or [])
        private = bool(entry.get("private", True))
        if not private:
            return True
        return campaign_id in owners

    def _record_private(self, campaign_id: str, digest: str, data: bytes | None) -> None:
        private_dir = self._campaign_private_dir(campaign_id)
        marker = self._safe_under(private_dir, private_dir / f"{digest}.ref")
        marker.write_text(digest, encoding="utf-8")
        if data is not None:
            # data already lives in CAS; marker is the catalog entry
            del data

    def _campaign_private_dir(self, campaign_id: str) -> Path:
        if ".." in campaign_id or "/" in campaign_id or "\\" in campaign_id:
            raise PathEscapeError(f"illegal campaign id: {campaign_id!r}")
        path = self.campaigns / campaign_id / "private"
        path.mkdir(parents=True, exist_ok=True)
        return self._safe_under(self.campaigns, path)

    def put_private(self, campaign_id: str, name: str, data: bytes) -> str:
        """Store a named private artifact. Isolated per campaign."""
        if ".." in Path(name).parts or name.startswith("/") or name.startswith("\\"):
            raise PathEscapeError(f"illegal private artifact name: {name!r}")
        digest = self.put_bytes(data, zone="incoming", campaign_id=campaign_id, private=True)
        private_dir = self._campaign_private_dir(campaign_id)
        dest = self._safe_under(private_dir, private_dir / name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(digest, encoding="utf-8")
        return digest

    def get_private(self, campaign_id: str, name: str) -> bytes:
        """GUARD: one campaign cannot read another campaign's private artifacts."""
        if ".." in Path(name).parts or name.startswith("/") or name.startswith("\\"):
            raise PathEscapeError(f"illegal private artifact name: {name!r}")
        private_dir = self._campaign_private_dir(campaign_id)
        dest = self._safe_under(private_dir, private_dir / name)
        if not dest.is_file():
            raise FileNotFoundError(name)
        digest = dest.read_text(encoding="utf-8").strip()
        return self.get(digest, campaign_id=campaign_id)

    def list_private(self, campaign_id: str) -> list[str]:
        private_dir = self._campaign_private_dir(campaign_id)
        names: list[str] = []
        for path in private_dir.rglob("*"):
            if path.is_file() and not path.name.endswith(".ref"):
                names.append(str(path.relative_to(private_dir)))
        return sorted(names)

    def refuse_external_path(self, user_path: str | Path) -> None:
        """Public refusal helper used by tests and later upload validation."""
        raw = Path(user_path)
        if raw.is_absolute():
            try:
                raw.resolve().relative_to(self.root)
            except ValueError as exc:
                raise PathEscapeError(f"absolute path outside store: {user_path}") from exc
        self._safe_under(self.root, self.root / raw)

    def purge_campaign_private(self, campaign_id: str) -> dict[str, int]:
        """Remove campaign-private files. Shared CAS objects with other owners stay."""
        if ".." in campaign_id or "/" in campaign_id or "\\" in campaign_id:
            raise PathEscapeError(f"illegal campaign id: {campaign_id!r}")
        removed_objects = 0
        removed_names = 0
        private_root = self.campaigns / campaign_id
        digests: set[str] = set()
        if private_root.exists():
            safe_root = self._safe_under(self.campaigns, private_root)
            for path in safe_root.rglob("*"):
                if not path.is_file():
                    continue
                removed_names += 1
                text = path.read_text(encoding="utf-8").strip()
                if len(text) == _DIGEST_HEX_LEN and all(c in "0123456789abcdef" for c in text):
                    digests.add(text)
            shutil.rmtree(safe_root)

        index = self._read_index()
        for digest, entry in list(index.items()):
            owners = list(entry.get("owners") or [])
            if campaign_id not in owners:
                continue
            owners.remove(campaign_id)
            if digest:
                digests.add(str(digest))
            if not owners and bool(entry.get("private", True)):
                try:
                    path = self.path_for(str(digest))
                except PathEscapeError:
                    continue
                if path.is_file():
                    path.unlink()
                    removed_objects += 1
                for zone in self.zones.values():
                    link = zone / str(digest)
                    if link.exists() or link.is_symlink():
                        link.unlink()
                index.pop(digest, None)
            else:
                entry["owners"] = owners
                index[digest] = entry
        self._write_index(index)

        exports = self.root / "exports" / campaign_id
        if exports.exists():
            safe_export = self._safe_under(self.root / "exports", exports)
            shutil.rmtree(safe_export)
        return {"objects": removed_objects, "private_names": removed_names}

    def stat(self) -> StoreStat:
        object_count = 0
        byte_count = 0
        if self.objects.exists():
            for path in self.objects.rglob("*"):
                if path.is_file():
                    object_count += 1
                    byte_count += path.stat().st_size
        zone_counts = {
            name: sum(1 for p in zone.rglob("*") if p.is_file())
            for name, zone in self.zones.items()
        }
        usage = shutil.disk_usage(self.root)
        return StoreStat(
            root=str(self.root),
            object_count=object_count,
            byte_count=byte_count,
            zones=zone_counts,
            disk_free=usage.free,
            disk_margin=self.disk_margin_bytes,
        )
