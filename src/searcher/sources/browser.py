"""§15.4 honest browser lifecycle. No personal profile, no stealth, reap always."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import Any

from searcher.core.config import HONEST_USER_AGENT
from searcher.core.errors import ErrorClass, SearcherError

HARD_CAP = 3
DEFAULT_BROWSERS = 1


class BrowserUnavailable(SearcherError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_class=ErrorClass.BROWSER)


@dataclass
class BrowserLease:
    kind: str
    content: str
    final_url: str
    status: int | None


class BrowserPool:
    """At most HARD_CAP browser processes. Close-and-reap on every terminal path."""

    def __init__(self, *, user_agent: str = HONEST_USER_AGENT, cap: int = DEFAULT_BROWSERS) -> None:
        self.user_agent = user_agent
        self.cap = min(max(cap, 1), HARD_CAP)
        self._lock = threading.Lock()
        self._live = 0
        self._playwright: Any = None
        self._browsers: list[Any] = []

    def live_count(self) -> int:
        with self._lock:
            return self._live

    def _ensure(self) -> Any:
        try:
            from playwright.sync_api import (  # type: ignore[import-not-found, unused-ignore]
                sync_playwright,
            )
        except ImportError as exc:
            raise BrowserUnavailable("playwright is not installed") from exc
        if self._playwright is None:
            started = sync_playwright().start()
            self._playwright = started
        with self._lock:
            if len(self._browsers) >= self.cap:
                return self._browsers[0]
            browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-extensions", "--disable-notifications"],
            )
            self._browsers.append(browser)
            self._live += 1
            return browser

    @contextmanager
    def page(
        self, url: str, *, timeout_ms: int = 15000, light: bool = True
    ) -> Iterator[BrowserLease]:  # noqa: E501
        browser = self._ensure()
        context = None
        page = None
        try:
            context = browser.new_context(
                user_agent=self.user_agent,
                java_script_enabled=True,
                accept_downloads=False,
                bypass_csp=False,
            )
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            response = page.goto(url, wait_until="domcontentloaded" if light else "networkidle")
            status = response.status if response is not None else None
            content = page.content()
            yield BrowserLease(
                kind="light" if light else "full",
                content=content,
                final_url=page.url,
                status=status,
            )
        finally:
            if page is not None:
                with suppress(Exception):
                    page.close()
            if context is not None:
                with suppress(Exception):
                    context.close()

    def close(self) -> None:
        with self._lock:
            for browser in self._browsers:
                with suppress(Exception):
                    browser.close()
            self._browsers.clear()
            self._live = 0
            if self._playwright is not None:
                with suppress(Exception):
                    self._playwright.stop()
                self._playwright = None

    def __enter__(self) -> BrowserPool:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def chromium_pids() -> set[int]:
    """Best-effort PID set of Chromium/Playwright children of this process tree."""
    found: set[int] = set()
    try:
        import subprocess

        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return found
    for line in proc.stdout.splitlines():
        lowered = line.lower()
        if "chrom" in lowered or "playwright" in lowered or "headless_shell" in lowered:
            parts = line.split(None, 1)
            if parts and parts[0].isdigit():
                found.add(int(parts[0]))
    found.discard(os.getpid())
    return found
