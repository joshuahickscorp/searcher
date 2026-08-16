"""Compatibility tests bind to the pinned SHA and fail if the contract moved."""

from __future__ import annotations

import pytest

from searcher.integrations.visionmcp.compatibility import (
    PINNED_SHA,
    PINNED_VERSION,
    REQUIRED_REPORT_KEYS,
    CompatibilityError,
    assert_core_contract,
    assert_report_shape,
    import_visionmcp,
)


def test_pinned_constants() -> None:
    assert PINNED_SHA == "18ee3c06d27f04937d1681dea5fa2650131e4b2a"
    assert PINNED_VERSION == "0.8.0a2"


def test_report_shape_fails_loudly() -> None:
    with pytest.raises(CompatibilityError, match="keys moved"):
        assert_report_shape({"available": []})


def test_core_contract_when_installed() -> None:
    if import_visionmcp() is None:
        pytest.skip("visionmcp not installed")
    info = assert_core_contract()
    assert info["version"] == PINNED_VERSION
    from visionmcp.capabilities import capabilities_report

    report = capabilities_report(profile="core")
    assert set(report) >= REQUIRED_REPORT_KEYS
