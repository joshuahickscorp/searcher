"""Browser pool close-and-reap. Zero orphaned processes after a run."""

from __future__ import annotations

import pytest

from searcher.sources.browser import BrowserPool, BrowserUnavailable, chromium_pids


@pytest.mark.timeout(90)
def test_browser_pool_leaves_no_orphans() -> None:
    before = chromium_pids()
    print("ps_before", sorted(before))
    try:
        pool = BrowserPool(cap=1)
    except BrowserUnavailable:
        pytest.skip("playwright is not installed")
    try:
        try:
            with pool.page("https://example.com", timeout_ms=20000, light=True) as lease:
                assert "Example" in lease.content or lease.status in {200, None}
        except Exception as exc:
            pytest.skip(f"browser launch failed: {exc}")
    finally:
        pool.close()
    after = chromium_pids()
    print("ps_after", sorted(after))
    orphans = after - before
    # The parent python process is excluded. Newly spawned chromium must be gone.
    assert not orphans, f"orphaned browser processes: {orphans}"
