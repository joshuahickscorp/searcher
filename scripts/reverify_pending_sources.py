#!/usr/bin/env python3
"""Re-verify pending marketplace admission with honest HTTP and optional render.

Never solves a challenge. Never fetches a robots-disallowed product URL.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from searcher.core.config import HONEST_USER_AGENT  # noqa: E402
from searcher.sources.browser import (  # noqa: E402
    BrowserPool,
    BrowserUnavailable,
    browser_extra_available,
)
from searcher.sources.challenge import challenge_marker, looks_like_challenge  # noqa: E402
from searcher.sources.http import HonestHttpClient  # noqa: E402
from searcher.sources.robots import RobotsCache  # noqa: E402

# Typical public product paths. Fetched only when robots allow them.
PROBES: dict[str, dict[str, Any]] = {
    "depop": {
        "origin": "https://www.depop.com",
        "product": "https://www.depop.com/products/example-item/",
    },
    "grailed": {
        "origin": "https://www.grailed.com",
        "product": "https://www.grailed.com/listings/1",
    },
    "vestiaire": {
        "origin": "https://www.vestiairecollective.com",
        "product": "https://www.vestiairecollective.com/women/",
    },
    "taobao": {
        "origin": "https://www.taobao.com",
        "product": "https://item.taobao.com/item.htm?id=1",
    },
    "weidian": {
        "origin": "https://weidian.com",
        "product": "https://weidian.com/item.html?itemID=1",
    },
    "yupoo": {
        "origin": "https://www.yupoo.com",
        "product": "https://www.yupoo.com/albums/",
    },
}


def _summarize_robots(body: str, product: str, user_agent: str) -> dict[str, Any]:
    cache = RobotsCache(user_agent=user_agent)
    allowed = cache.allows(product, body) if body else False
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    relevant = [
        line
        for line in lines
        if line.lower().startswith(("user-agent", "allow", "disallow", "crawl-delay", "sitemap"))
    ]
    return {
        "product_allowed": allowed,
        "rule_lines": relevant[:40],
        "body_chars": len(body),
    }


def _http_get(http: HonestHttpClient, url: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = http.get(url, base_delay=0.4, pace=True)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    text = response.text
    return {
        "ok": True,
        "status": response.status,
        "final_url": response.final_url,
        "bytes": len(response.body),
        "elapsed_ms": response.elapsed_ms,
        "challenge": looks_like_challenge(text),
        "challenge_marker": challenge_marker(text),
        "body_preview": text[:400],
        "text": text,
    }


def _browser_get(pool: BrowserPool, url: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with pool.page(url, timeout_ms=20000, light=True) as lease:
            text = lease.content
            elapsed = int((time.perf_counter() - started) * 1000)
            return {
                "ok": True,
                "status": lease.status,
                "final_url": lease.final_url,
                "bytes": len(text.encode("utf-8")),
                "elapsed_ms": elapsed,
                "challenge": looks_like_challenge(text),
                "challenge_marker": challenge_marker(text),
                "body_preview": text[:400],
                "text": text,
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def _admission(
    *,
    robots_ok: bool | None,
    challenge: bool,
    product_allowed: bool | None,
    notes: str,
) -> dict[str, str]:
    if challenge:
        status = "review_required"
        reason = "anti-automation challenge on robots or product URL; not admitted"
    elif robots_ok is False:
        status = "review_required"
        reason = "robots.txt could not be fetched; fail-closed"
    elif product_allowed is False:
        status = "review_required"
        reason = "robots.txt disallows typical product URLs"
    else:
        status = "review_required"
        reason = (
            "robots appear to allow the product path, but the existing "
            "adapter lock keeps the source disabled until a dedicated review "
            "changes test_pending_scope_adapters_are_disabled_review_required"
        )
    return {"status": status, "reason": reason, "notes": notes}


def probe_one(
    name: str,
    spec: dict[str, Any],
    http: HonestHttpClient,
    pool: BrowserPool | None,
) -> dict[str, Any]:
    robots_url = spec["origin"].rstrip("/") + "/robots.txt"
    product = spec["product"]
    http_robots = _http_get(http, robots_url)
    browser_robots = _browser_get(pool, robots_url) if pool is not None else None
    chosen = None
    source = None
    for label, result in (("browser", browser_robots), ("http", http_robots)):
        if result and result.get("ok") and not result.get("challenge"):
            chosen = result
            source = label
            break
    if chosen is None:
        chosen = browser_robots or http_robots
        source = "browser" if browser_robots else "http"
    challenge = bool(chosen.get("challenge"))
    body = str(chosen.get("text") or "") if chosen.get("ok") and not challenge else ""
    robots_summary = (
        _summarize_robots(body, product, HONEST_USER_AGENT) if body else None
    )
    product_http = None
    product_browser = None
    product_allowed = robots_summary["product_allowed"] if robots_summary else None
    if body and product_allowed and not challenge:
        product_http = _http_get(http, product)
        if product_http.get("challenge"):
            product_http = {k: v for k, v in product_http.items() if k != "text"}
        else:
            product_http.pop("text", None)
        if pool is not None:
            product_browser = _browser_get(pool, product)
            if product_browser.get("challenge"):
                product_browser = {
                    k: v for k, v in product_browser.items() if k != "text"
                }
            else:
                product_browser.pop("text", None)
    http_robots_out = {k: v for k, v in http_robots.items() if k != "text"}
    browser_robots_out = (
        {k: v for k, v in browser_robots.items() if k != "text"}
        if browser_robots
        else None
    )
    product_challenge = bool(
        (product_http or {}).get("challenge") or (product_browser or {}).get("challenge")
    )
    admission = _admission(
        robots_ok=bool(chosen.get("ok")) and not challenge,
        challenge=challenge or product_challenge,
        product_allowed=product_allowed,
        notes=f"robots body taken from {source}" if source else "no robots body",
    )
    return {
        "source": name,
        "origin": spec["origin"],
        "product_url_probed": product,
        "http_robots": http_robots_out,
        "browser_robots": browser_robots_out,
        "robots_source": source,
        "robots": robots_summary,
        "product_http": product_http,
        "product_browser": product_browser,
        "challenge_appeared": challenge or product_challenge,
        "admission": admission,
    }


def main() -> int:
    out_dir = ROOT / "artifacts" / "deepverify"
    out_dir.mkdir(parents=True, exist_ok=True)
    http = HonestHttpClient()
    pool: BrowserPool | None = None
    if browser_extra_available():
        try:
            pool = BrowserPool(cap=1)
        except BrowserUnavailable:
            pool = None
    results: list[dict[str, Any]] = []
    try:
        for name, spec in PROBES.items():
            results.append(probe_one(name, spec, http, pool))
    finally:
        if pool is not None:
            pool.close()
        http.close()
    payload = {
        "user_agent": HONEST_USER_AGENT,
        "browser_extra": pool is not None,
        "sources": results,
    }
    path = out_dir / "source-reverify.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    for item in results:
        robots = item.get("robots") or {}
        print(
            f"{item['source']}: allowed={robots.get('product_allowed')} "
            f"challenge={item['challenge_appeared']} "
            f"admission={item['admission']['status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
