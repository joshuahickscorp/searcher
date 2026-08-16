"""Browser processes must not survive a fetch that raises."""

from __future__ import annotations

import pytest

from searcher.sources.browser import BrowserPool, BrowserUnavailable, chromium_pids


@pytest.mark.timeout(90)
def test_browser_pool_reaps_after_failed_navigation() -> None:
    before = chromium_pids()
    try:
        pool = BrowserPool(cap=1)
    except BrowserUnavailable:
        pytest.skip("playwright is not installed")
    try:
        try:
            with pool.page("http://127.0.0.1:1", timeout_ms=2000, light=True):
                raise AssertionError("navigation to a closed port should fail")
        except Exception:
            pass
    finally:
        pool.close()
    after = chromium_pids()
    orphans = after - before
    assert not orphans, f"orphaned browser processes after failed fetch: {orphans}"
