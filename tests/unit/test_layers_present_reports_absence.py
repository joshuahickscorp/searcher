"""`layers_present` must report a missing layer, not assume it is there.

This is the probe the capabilities endpoint and the campaign runner consult
before claiming a lane works. Its except-branches were never exercised, so
nothing checked that an unimportable layer is reported absent rather than
present. A probe that cannot report absence is decoration: the failure it exists
to catch is exactly the one it would miss.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from typing import Any

import pytest

from searcher.campaigns.orchestrator import layers_present


@pytest.fixture
def blocked_import() -> Iterator[Any]:
    real = builtins.__import__
    blocked: set[str] = set()

    def fake(name: str, *args: Any, **kwargs: Any) -> Any:
        if any(name.startswith(prefix) for prefix in blocked):
            raise ImportError(f"blocked for test: {name}")
        return real(name, *args, **kwargs)

    builtins.__import__ = fake
    try:
        yield blocked
    finally:
        builtins.__import__ = real


def test_both_layers_present_when_nothing_is_blocked() -> None:
    assert layers_present() == {"discovery": True, "routing": True}


def test_discovery_absent_is_reported(blocked_import: set[str]) -> None:
    blocked_import.add("searcher.sources.engine")
    present = layers_present()
    assert present["discovery"] is False, "an unimportable discovery layer must report absent"
    assert present["routing"] is True, "one missing layer must not condemn the other"


def test_routing_absent_is_reported(blocked_import: set[str]) -> None:
    blocked_import.add("searcher.ranking.buckets")
    present = layers_present()
    assert present["routing"] is False
    assert present["discovery"] is True


def test_both_absent_is_reported(blocked_import: set[str]) -> None:
    blocked_import.add("searcher.sources.engine")
    blocked_import.add("searcher.retrieval.pipeline")
    assert layers_present() == {"discovery": False, "routing": False}


def test_the_probe_never_raises_when_a_layer_is_broken(blocked_import: set[str]) -> None:
    """A broken layer must degrade the report, never take the caller down."""
    blocked_import.add("searcher.sources.engine")
    blocked_import.add("searcher.ranking.buckets")
    blocked_import.add("searcher.retrieval.pipeline")
    present = layers_present()
    assert set(present) == {"discovery", "routing"}
    assert all(value is False for value in present.values())
