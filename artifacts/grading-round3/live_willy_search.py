# ruff: noqa: E501
"""Live Willy campaign for the third regrade. Writes live-willy.json."""

from __future__ import annotations

import json
import time
from pathlib import Path

from searcher.api.views import list_public_results
from searcher.campaigns.controller import CampaignController
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.workers.api_campaign import create_api_campaign
from searcher.workers.bounded_discovery import install_bounded_discovery

TARGET = "https://shop.kind.co.jp/products/8001001141404"
IMAGES = [
    Path("fixtures/known_item_kind/images/8001001141404_1.jpg"),
    Path("fixtures/known_item_kind/images/8001001141404_2.jpg"),
    Path("fixtures/known_item_kind/images/8001001141404_3.jpg"),
]
TEXT = "WILLY CHAVARRIA 無地 ロングスリーブカットソー ブラック"
TAGS = ["WILLY CHAVARRIA", "ロングスリーブ", "black"]
OUT = Path("artifacts/grading-round3/live-willy.json")
DATA = Path("artifacts/grading-round3/live-willy-data")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env(data_root=DATA)
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    controller = CampaignController(database, store, settings)
    uploads = [(path.read_bytes(), path.name) for path in IMAGES]
    started = time.monotonic()
    search_id = create_api_campaign(
        controller,
        uploads=uploads,
        text=TEXT,
        tags=TAGS,
        client_search_id=None,
        settings=settings,
    )
    install_bounded_discovery()
    CampaignOrchestrator(
        controller,
        source_names=[
            "wikimedia",
            "kind",
            "komehyo",
            "the_realreal",
            "byronesque",
            "heroine",
            "ebay",
        ],
        max_rounds=2,
        max_work=8,
        batch_size=3,
    ).run(search_id)
    elapsed = time.monotonic() - started
    campaign = controller.get(search_id)
    candidates = controller.repos.list_candidates(search_id)
    results = controller.repos.list_results(search_id)
    runtime = controller.repos.get_runtime(search_id)
    published = []
    for row in results:
        candidate = controller.repos.get_candidate(search_id, row["candidate_id"])
        url = candidate.canonical_url if candidate is not None else None
        published.append(
            {
                "bucket": row["public_bucket"],
                "url": url,
                "title": None
                if candidate is None or candidate.title is None
                else candidate.title.value,
                "images": 0 if candidate is None else len(candidate.images),
            }
        )
    possible = [p for p in published if p["bucket"] == "possibly_real"]
    real = [p for p in published if p["bucket"] == "real"]
    replica = [p for p in published if p["bucket"] == "replica"]
    target_rank = None
    for i, item in enumerate(possible, start=1):
        if item["url"] == TARGET:
            target_rank = i
            break
    projected = list_public_results(controller, search_id, None)
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "flagship_acceptance", Path("scripts/flagship_acceptance.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scripts/flagship_acceptance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    evaluate = mod.evaluate

    events = []
    for ev in controller.repos.list_events(search_id):
        name = ev.get("event_name") or ev.get("event") or ev.get("name")
        payload = ev.get("payload") or ev.get("data") or {}
        events.append({"event": name, "data": payload})
    state = {
        "state": campaign.state.value,
        "terminal_status": None
        if campaign.terminal_status is None
        else campaign.terminal_status.value,
        "terminal_reason": campaign.terminal_reason,
        "counts": runtime.get("counts"),
        "coverage": runtime.get("coverage"),
    }
    try:
        flagship = evaluate(state, projected, events, DATA, [p.name for p in IMAGES])
        summary = {
            "met": sum(1 for r in flagship if r["verdict"] == "met"),
            "not_met": sum(1 for r in flagship if r["verdict"] == "not met"),
            "not_evaluable": sum(1 for r in flagship if r["verdict"] == "not evaluable"),
            "of": len(flagship),
        }
    except Exception as exc:
        flagship = []
        summary = {"error": str(exc)}
    out = {
        "search_id": search_id,
        "elapsed_s": round(elapsed, 2),
        "terminal_status": state["terminal_status"],
        "terminal_reason": campaign.terminal_reason,
        "candidates": len(candidates),
        "product_urls": sum(1 for c in candidates if "/products/" in c.canonical_url),
        "with_images": sum(1 for c in candidates if c.images),
        "image_count": sum(len(c.images) for c in candidates),
        "index_urls": [
            c.canonical_url
            for c in candidates
            if "products.json" in c.canonical_url or "/collections/" in c.canonical_url
        ],
        "counts": {
            "real": len(real),
            "possibly_real": len(possible),
            "replica": len(replica),
            "hidden": sum(1 for p in published if p["bucket"] == "hidden"),
        },
        "target_url": TARGET,
        "target_in_possibly_real_rank": target_rank,
        "possibly_real": possible,
        "real": real,
        "projected_possible": [
            {
                "listing_url": r.get("listing_url"),
                "tab_reason": (r.get("why") or {}).get("tab_reason"),
                "images_compared": r.get("images_compared"),
                "bucket": r.get("bucket"),
            }
            for r in (projected.get("possibly_real") or [])
        ],
        "coverage": runtime.get("coverage"),
        "runtime_counts": runtime.get("counts"),
        "flagship_summary": summary,
        "flagship": flagship,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in (
        "search_id", "elapsed_s", "terminal_status", "terminal_reason",
        "candidates", "product_urls", "with_images", "image_count",
        "index_urls", "counts", "target_in_possibly_real_rank",
        "flagship_summary",
    )}, indent=2, ensure_ascii=False))
    print("wrote", OUT)
    database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
