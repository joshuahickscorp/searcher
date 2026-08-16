# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.http_client:RobotsCache / RobotsBlocked
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Robots.txt cache. Fail-closed on fetch error. Honour Crawl-delay."""

from __future__ import annotations

import re
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

from searcher.core.config import HONEST_USER_AGENT
from searcher.core.errors import PolicyBlocked
from searcher.core.time import parse_utc, utc_now
from searcher.storage.repositories import Repositories

_CRAWL_DELAY_RE = re.compile(r"(?i)^\s*crawl-delay\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$")
_SITEMAP_RE = re.compile(r"(?i)^\s*sitemap\s*:\s*(\S+)\s*$")


class RobotsBlocked(PolicyBlocked):
    def __init__(self, url: str, reason: str = "robots.txt disallows this path") -> None:
        super().__init__(reason, url=url)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class RobotsSnapshot:
    origin: str
    body: str
    allowed: bool
    crawl_delay: float | None
    sitemaps: tuple[str, ...]
    status: str
    fetched_at: float


class RobotsCache:
    """Per-origin cache with TTL. A failed robots fetch is treated as disallowed."""

    def __init__(
        self,
        *,
        user_agent: str = HONEST_USER_AGENT,
        ttl_seconds: int = 3600,
        repos: Repositories | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.ttl_seconds = ttl_seconds
        self.repos = repos
        self._memory: dict[str, tuple[float, RobotsSnapshot]] = {}

    def origin_of(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    def parse_body(self, origin: str, body: str, *, status: str = "ok") -> RobotsSnapshot:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.splitlines())
        allowed = bool(parser.can_fetch(self.user_agent, origin + "/"))
        return RobotsSnapshot(
            origin=origin,
            body=body,
            allowed=allowed,
            crawl_delay=extract_crawl_delay(body, self.user_agent),
            sitemaps=tuple(extract_sitemaps(body)),
            status=status,
            fetched_at=time.time(),
        )

    def allows(self, url: str, body: str) -> bool:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.splitlines())
        return bool(parser.can_fetch(self.user_agent, url))

    def get_cached(self, origin: str) -> RobotsSnapshot | None:
        now = time.time()
        held = self._memory.get(origin)
        if held is not None and now - held[0] < self.ttl_seconds:
            return held[1]
        if self.repos is None:
            return None
        row = self.repos.get_robots_cache(origin)
        if row is None:
            return None
        fetched = parse_utc(str(row["fetched_at"]))
        age = (utc_now() - fetched).total_seconds()
        if age > self.ttl_seconds:
            return None
        snapshot = RobotsSnapshot(
            origin=origin,
            body=str(row["body"]),
            allowed=str(row["status"]) == "ok",
            crawl_delay=row["crawl_delay"],
            sitemaps=tuple(extract_sitemaps(str(row["body"]))),
            status=str(row["status"]),
            fetched_at=fetched.timestamp(),
        )
        self._memory[origin] = (time.time(), snapshot)
        return snapshot

    def store(self, snapshot: RobotsSnapshot) -> None:
        self._memory[snapshot.origin] = (time.time(), snapshot)
        if self.repos is not None:
            self.repos.upsert_robots_cache(
                snapshot.origin,
                snapshot.body,
                snapshot.status,
                snapshot.crawl_delay,
            )

    def remember_failure(self, origin: str) -> RobotsSnapshot:
        snapshot = RobotsSnapshot(
            origin=origin,
            body="",
            allowed=False,
            crawl_delay=None,
            sitemaps=(),
            status="fetch_failed",
            fetched_at=time.time(),
        )
        self.store(snapshot)
        return snapshot


def extract_crawl_delay(body: str, user_agent: str) -> float | None:
    """Parse Crawl-delay for our UA, then *, then any group."""
    product = user_agent.split("/")[0]
    current_agents: list[str] = []
    delays: dict[str, float] = {}
    star_delay: float | None = None
    any_delay: float | None = None
    saw_rule = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            current_agents = []
            saw_rule = False
            continue
        lowered = line.lower()
        if lowered.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            if saw_rule:
                current_agents = [agent]
                saw_rule = False
            else:
                current_agents.append(agent)
            continue
        match = _CRAWL_DELAY_RE.match(line)
        if match:
            delay = float(match.group(1))
            any_delay = delay if any_delay is None else any_delay
            for agent in current_agents or ["*"]:
                delays[agent.lower()] = delay
                if agent == "*":
                    star_delay = delay
            saw_rule = True
            continue
        if lowered.startswith("disallow:") or lowered.startswith("allow:"):
            saw_rule = True
            continue
        if lowered.startswith("user-agent:"):
            continue
        if not lowered.startswith("crawl-delay") and not lowered.startswith("user-agent"):
            # A new record starts on blank; already handled.
            pass
    product_l = product.lower()
    ua_l = user_agent.lower()
    if ua_l in delays:
        return delays[ua_l]
    if product_l in delays:
        return delays[product_l]
    if star_delay is not None:
        return star_delay
    return any_delay


def extract_sitemaps(body: str) -> list[str]:
    found: list[str] = []
    for raw in body.splitlines():
        match = _SITEMAP_RE.match(raw.split("#", 1)[0])
        if match:
            found.append(match.group(1))
    return found


def path_matches_prefix(url: str, prefixes: list[str]) -> bool:
    path = urlparse(url).path or "/"
    query = urlparse(url).query
    target = path if not query else f"{path}?{query}"
    for prefix in prefixes:
        if not prefix:
            continue
        if prefix.endswith("*"):
            if path.startswith(prefix[:-1]) or target.startswith(prefix[:-1]):
                return True
        elif path.startswith(prefix) or target.startswith(prefix):
            return True
    return False
