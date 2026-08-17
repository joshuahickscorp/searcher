# ruff: noqa: E501
"""Live campaign against shop.rebag.com only. Fails if no listing is returned."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import SourceOutcome
from searcher.core.config import HONEST_USER_AGENT, Settings
from searcher.evidence.content_store import ContentStore
from searcher.sources.live_runner import LiveDiscoveryRunner
from searcher.sources.platform import requires_operator_credential
from searcher.sources.strategies import CATALOG_FEED
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


def _pick_rebag_product() -> tuple[str, str, str]:
    import json as json_mod
    import urllib.request

    request = urllib.request.Request(
        "https://shop.rebag.com/products.json?limit=10&page=1",
        headers={"User-Agent": HONEST_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json_mod.loads(response.read().decode("utf-8"))
    for product in payload.get("products") or []:
        if not isinstance(product, dict):
            continue
        vendor = str(product.get("vendor") or "").strip()
        handle = str(product.get("handle") or "").strip()
        title = str(product.get("title") or "").strip()
        if vendor and handle:
            return vendor, handle, title
    raise RuntimeError("shop.rebag.com page 1 had no products")

OUT = Path("artifacts/grading-round4/live_rebag.json")


def main() -> int:
    started = time.perf_counter()
    root = Path("artifacts/grading-round4/live-rebag-data")
    root.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env(data_root=root)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db)
    store = ContentStore(settings.data_root)
    controller = CampaignController(db, store, settings)
    from searcher.sources.adapters.rebag import RebagAdapter

    cred = requires_operator_credential(RebagAdapter().manifest())
    previous_pages = os.environ.get("SEARCHER_CATALOG_PAGES_PER_SOURCE")
    previous_promote = os.environ.get("SEARCHER_CATALOG_PROMOTE_PER_SOURCE")
    os.environ["SEARCHER_CATALOG_PAGES_PER_SOURCE"] = "2"
    os.environ["SEARCHER_CATALOG_PROMOTE_PER_SOURCE"] = "8"
    try:
        vendor, handle, title = _pick_rebag_product()
        runner = LiveDiscoveryRunner(controller)
        intent = runner.create(
            vendor,
            language="en",
            wall_seconds=180,
            page_limit=24,
            source_limit=2,
            byte_limit=6_000_000,
        )
        summary = runner.run(intent.search_id, source_names=["rebag"])
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(json.dumps(payload, indent=2))
        return 2
    finally:
        if previous_pages is None:
            os.environ.pop("SEARCHER_CATALOG_PAGES_PER_SOURCE", None)
        else:
            os.environ["SEARCHER_CATALOG_PAGES_PER_SOURCE"] = previous_pages
        if previous_promote is None:
            os.environ.pop("SEARCHER_CATALOG_PROMOTE_PER_SOURCE", None)
        else:
            os.environ["SEARCHER_CATALOG_PROMOTE_PER_SOURCE"] = previous_promote
        db.close()
    urls = [item.canonical_url for item in summary.listings]
    strategies = summary.strategy_coverage.get("rebag") or []
    by_name = {str(item.get("name")): item for item in strategies}
    catalog_urls = [str(url) for url in (by_name.get(CATALOG_FEED, {}).get("urls") or [])]
    ok = (
        cred is False
        and summary.coverage.get("rebag") == SourceOutcome.SEARCHED_MATCHES_FOUND.value
        and any("rebag.com" in url and "/products/" in url for url in urls)
        and any("shop.rebag.com/products.json" in url for url in catalog_urls)
        and "kind" not in summary.coverage
    )
    payload = {
        "ok": ok,
        "requires_credential": cred,
        "vendor": vendor,
        "handle": handle,
        "title": title,
        "coverage": summary.coverage,
        "coverage_details": summary.coverage_details,
        "strategy_coverage": summary.strategy_coverage,
        "urls": urls[:12],
        "catalog_urls": catalog_urls,
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps(payload, indent=2, default=str)[:4000])
    print("CLAIM_HOLD" if ok else "CLAIM_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
