"""Robots parsing: Crawl-delay, wildcards, fail-closed."""

from __future__ import annotations

from searcher.sources.robots import RobotsCache, extract_crawl_delay, path_matches_prefix

ROBOTS = """
User-agent: Searcher
Disallow: /search
Crawl-delay: 2.5

User-agent: *
Disallow: /admin
Allow: /
Crawl-delay: 1
"""


def test_crawl_delay_for_product_token() -> None:
    delay = extract_crawl_delay(ROBOTS, "Searcher/0.1.0 (+https://example.invalid)")
    assert delay == 2.5


def test_wildcard_disallow() -> None:
    cache = RobotsCache(user_agent="Searcher/0.1.0")
    assert cache.allows("https://shop.example/search?q=x", ROBOTS) is False
    assert cache.allows("https://shop.example/products/a", ROBOTS) is True


def test_star_group_disallow() -> None:
    cache = RobotsCache(user_agent="OtherBot/1.0")
    assert cache.allows("https://shop.example/admin", ROBOTS) is False


def test_path_prefix_wildcard() -> None:
    assert path_matches_prefix("https://x.test/sch/i.html?_nkw=a", ["/sch/"])
    assert not path_matches_prefix("https://x.test/itm/1", ["/sch/"])


def test_failed_robots_is_disallowed() -> None:
    cache = RobotsCache()
    snapshot = cache.remember_failure("https://x.test")
    assert snapshot.allowed is False
    assert snapshot.status == "fetch_failed"
