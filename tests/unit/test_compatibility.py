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


def test_drifted_donor_sha_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A moved donor SHA must raise, not be accepted.

    The §32.9 "accept changed donor SHA" mutation survived the suite: swallowing
    a SHA mismatch inside `assert_core_contract` left every existing assertion
    green, because `test_pinned_constants` checks that the constants hold the
    expected values and never injects a drift. A pin nothing tests is decoration
    - the whole point is that it fires when the donor moves under us.
    """
    import searcher.integrations.visionmcp.compatibility as compat

    if compat.import_visionmcp() is None:
        pytest.skip("visionmcp is not installed in this environment")

    monkeypatch.setattr(compat, "donor_sha_from_install", lambda pkg=None: "0" * 40)
    with pytest.raises(compat.CompatibilityError) as excinfo:
        compat.assert_core_contract()
    assert "SHA" in str(excinfo.value)
    assert compat.PINNED_SHA in str(excinfo.value)
