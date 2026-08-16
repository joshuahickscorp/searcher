"""Source families and search-scope selection.

A source declares its family in registry / policy metadata. Call sites filter
by the selected scopes; they do not keep their own marketplace lists.
"""

from __future__ import annotations

from collections.abc import Iterable

from searcher.contracts.enums import SourceFamily
from searcher.sources.policy import policy_for

KNOWN_SOURCE_SCOPES: frozenset[str] = frozenset(
    {SourceFamily.LEGITIMATE.value, SourceFamily.REPLICA.value}
)
DEFAULT_SOURCE_SCOPES: tuple[str, ...] = (SourceFamily.LEGITIMATE.value,)
REPLICA_SOURCE_REASON = "REPLICA_SOURCE_FAMILY"

# Not planned as marketplace sources even though they are registered adapters.
_NON_MARKET_ADAPTERS = frozenset({"generic_page", "sitemap"})


def normalize_source_scopes(values: object) -> tuple[str, ...]:
    """Keep known scopes, drop unknown values, default to legitimate when empty."""
    if values is None:
        return DEFAULT_SOURCE_SCOPES
    if isinstance(values, str):
        raw_items: Iterable[object] = (values,)
    elif isinstance(values, Iterable):
        raw_items = values
    else:
        return DEFAULT_SOURCE_SCOPES
    seen: list[str] = []
    for raw in raw_items:
        key = str(raw).strip().lower()
        if key in KNOWN_SOURCE_SCOPES and key not in seen:
            seen.append(key)
    return tuple(seen) if seen else DEFAULT_SOURCE_SCOPES


def family_for(source_id: str) -> SourceFamily:
    recorded = policy_for(source_id)
    if recorded is not None:
        return recorded.source_family
    try:
        from searcher.sources.adapters import resolve_adapter

        manifest_fn = getattr(resolve_adapter(source_id), "manifest", None)
        if callable(manifest_fn):
            family = getattr(manifest_fn(), "source_family", None)
            if isinstance(family, SourceFamily):
                return family
    except Exception:
        pass
    return SourceFamily.LEGITIMATE


def registered_ids_for(family: SourceFamily) -> tuple[str, ...]:
    from searcher.sources.adapters import ADAPTER_REGISTRY

    names: list[str] = []
    for name in ADAPTER_REGISTRY:
        if name in _NON_MARKET_ADAPTERS:
            continue
        if family_for(name) is family:
            names.append(name)
    return tuple(names)


def names_for_scopes(
    scopes: Iterable[str],
    preferred: tuple[str, ...] | None = None,
    *,
    default_order: tuple[str, ...],
) -> tuple[str, ...]:
    """Sources eligible for the selected families, preserving planner order."""
    selected = {item for item in normalize_source_scopes(list(scopes))}
    if preferred is None:
        pool = list(default_order)
    else:
        pool = list(preferred)
        if SourceFamily.REPLICA.value in selected:
            for name in registered_ids_for(SourceFamily.REPLICA):
                if name not in pool:
                    pool.append(name)
    return tuple(name for name in pool if family_for(name).value in selected)
