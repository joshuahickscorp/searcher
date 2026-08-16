"""Per-host token buckets and a global bandwidth ceiling (§15.5)."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    rate_per_second: float
    burst: float
    tokens: float = 0.0
    updated: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def wait(self) -> float:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.updated
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate_per_second)
            self.updated = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            missing = 1.0 - self.tokens
            delay = missing / self.rate_per_second if self.rate_per_second > 0 else 1.0
            jitter = random.uniform(0.0, 0.15 * delay)
            sleep_for = delay + jitter
            self.tokens = 0.0
            self.updated = now + sleep_for
            return sleep_for


@dataclass
class BandwidthLimiter:
    bytes_per_second: int
    used: int = 0
    window_start: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def charge(self, nbytes: int) -> float:
        if self.bytes_per_second <= 0:
            return 0.0
        with self.lock:
            now = time.monotonic()
            if now - self.window_start >= 1.0:
                self.used = 0
                self.window_start = now
            self.used += nbytes
            if self.used <= self.bytes_per_second:
                return 0.0
            overflow = self.used - self.bytes_per_second
            return overflow / self.bytes_per_second


class HostLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def bucket(self, host: str, *, rpm: int, burst: int) -> TokenBucket:
        with self._lock:
            held = self._buckets.get(host)
            if held is None:
                rate = max(rpm, 1) / 60.0
                held = TokenBucket(
                    rate_per_second=rate, burst=float(max(burst, 1)), tokens=float(max(burst, 1))
                )  # noqa: E501
                self._buckets[host] = held
            return held

    def wait(self, host: str, *, rpm: int, burst: int) -> float:
        delay = self.bucket(host, rpm=rpm, burst=burst).wait()
        if delay > 0:
            time.sleep(delay)
        return delay
