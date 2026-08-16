"""Live KIND collection expansion. Run only when the full package is on disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from searcher.campaigns.controller import CampaignController
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.sources.live_runner import LiveDiscoveryRunner
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


def main() -> int:
    root = Path("artifacts/listing-expansion/live-data")
    root.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env(data_root=root)
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    controller = CampaignController(database, store, settings)
    runner = LiveDiscoveryRunner(controller)
    intent = runner.create(
        "Willy Chavarria",
        language="en",
        extra_queries=[("ja", "ウィリーチャバリア")],
        wall_seconds=180,
        page_limit=40,
        source_limit=2,
        byte_limit=8_000_000,
    )
    summary = runner.run(intent.search_id, source_names=["kind"])
    campaign = controller.get(intent.search_id)
    candidates = controller.repos.list_candidates(intent.search_id)
    runtime = controller.repos.get_runtime(intent.search_id)
    expansions = list(runtime.get("index_expansions") or [])
    if summary is not None and summary.expansions:
        expansions = list(summary.expansions)
    sample = []
    for item in candidates[:12]:
        sample.append(
            {
                "url": item.canonical_url,
                "title": None if item.title is None else item.title.value,
                "images": len(item.images),
                "images_missing_reason": (item.structured_data or {}).get(
                    "images_missing_reason"
                ),
            }
        )
    index_urls = [
        item.canonical_url
        for item in candidates
        if "products.json" in item.canonical_url
        or "/collections/" in item.canonical_url
        or "sitemap" in item.canonical_url.lower()
    ]
    out = {
        "search_id": intent.search_id,
        "terminal_state": campaign.state.value,
        "terminal_status": (
            None if campaign.terminal_status is None else campaign.terminal_status.value
        ),
        "terminal_reason": campaign.terminal_reason,
        "candidates": len(candidates),
        "product_urls": sum(1 for item in candidates if "/products/" in item.canonical_url),
        "with_images": sum(1 for item in candidates if item.images),
        "index_canonical_urls": index_urls,
        "sample": sample,
        "expansions": expansions,
        "coverage": runtime.get("coverage"),
        "pages_fetched": (runtime.get("coverage") or {}).get("pages_fetched")
        if isinstance(runtime.get("coverage"), dict)
        else None,
    }
    dest = Path("artifacts/listing-expansion/live-kind.json")
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    database.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
