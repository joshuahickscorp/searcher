"""§27.5 cache keys. Every version that can change an answer is in the key."""

from __future__ import annotations

from dataclasses import dataclass

from searcher import CODE_VERSION, SCHEMA_VERSION
from searcher.core.config import Settings
from searcher.core.ids import canonical_dumps, sha256_hex
from searcher.core.policy import POLICY_VERSION

INDEX_SCHEMA = "index-1"
LISTING_ADAPTER = "listing-index-1"
DESCRIPTOR_MODEL = "histogram-1"
LISTING_PARAMETERS = "listing"


@dataclass(frozen=True, slots=True)
class CacheVersions:
    adapter_version: str
    model_version: str
    parameters: str
    schema_version: str
    policy_version: str


def versions_from_settings(
    settings: Settings | None = None,
    *,
    parameters: str = LISTING_PARAMETERS,
    adapter_version: str = LISTING_ADAPTER,
    model_version: str = DESCRIPTOR_MODEL,
) -> CacheVersions:
    schema = settings.schema_version if settings is not None else SCHEMA_VERSION
    policy = settings.policy_version if settings is not None else POLICY_VERSION
    return CacheVersions(
        adapter_version=adapter_version,
        model_version=model_version,
        parameters=parameters,
        schema_version=schema,
        policy_version=policy,
    )


def cache_key(*, content_digest: str, versions: CacheVersions) -> str:
    payload = {
        "content_digest": content_digest,
        "adapter_version": versions.adapter_version,
        "model_version": versions.model_version,
        "parameters": versions.parameters,
        "schema_version": versions.schema_version,
        "policy_version": versions.policy_version,
        "index_schema": INDEX_SCHEMA,
        "code_version": CODE_VERSION,
    }
    return sha256_hex(canonical_dumps(payload).encode("utf-8"))


def with_parameters(versions: CacheVersions, parameters: str) -> CacheVersions:
    return CacheVersions(
        adapter_version=versions.adapter_version,
        model_version=versions.model_version,
        parameters=parameters,
        schema_version=versions.schema_version,
        policy_version=versions.policy_version,
    )
