#!/usr/bin/env -S uv run python
"""Index an admitted source's catalogue into the warm index, ahead of any search.

The warm index is otherwise a cache of past text searches: it is written by
`remember_campaign` from candidates a campaign already retrieved, so a listing
no query ever named was never stored, and the descriptor search reads an empty
shelf. This fills it.

Run it against a source, not against a search. A campaign must never trigger a
catalogue walk - every search would then pay for one - so this is an operator or
scheduled job, deliberately outside the campaign path.

    ./scripts/ingest_catalog.py --source kind --pages 9

Honours robots by using the adapter's own declared feed path, and stops at the
page count given. Prints counts rather than a verdict: a run that indexed
nothing must not read like a run that found nothing to index.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from searcher.campaigns.controller import CampaignController  # noqa: E402
from searcher.core.config import Settings  # noqa: E402
from searcher.evidence.content_store import ContentStore  # noqa: E402
from searcher.index.ingest import ingest_products  # noqa: E402
from searcher.index.keys import versions_from_settings  # noqa: E402
from searcher.index.store import WarmIndex, descriptor_from_bytes  # noqa: E402
from searcher.normalization.listing import normalize_raw  # noqa: E402
from searcher.sources.adapters import product as product_specs  # noqa: E402
from searcher.sources.adapters.product import parse_shopify_catalog  # noqa: E402
from searcher.storage.connection import Database  # noqa: E402
from searcher.storage.migrations import migrate  # noqa: E402

USER_AGENT = "SearcherBot/0.1 (+respects robots.txt)"


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=30).read()  # noqa: S310


def _spec(source: str) -> Any:
    spec = getattr(product_specs, source.upper(), None)
    if spec is None:
        raise SystemExit(f"no product spec named {source.upper()} in sources.adapters.product")
    if not getattr(spec, "catalog_feed_path", None):
        raise SystemExit(f"{source} declares no catalog_feed_path; nothing to walk")
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="source id, e.g. kind")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=250)
    parser.add_argument("--images", type=int, default=1, help="images described per product")
    parser.add_argument("--data-root", default=None)
    args = parser.parse_args()

    spec = _spec(args.source)
    settings = Settings.from_env(
        data_root=Path(args.data_root) if args.data_root else None
    )
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    controller = CampaignController(database, store, settings)
    index = WarmIndex(controller.repos)
    versions = versions_from_settings(settings)

    origin = f"https://{spec.domain}"
    totals: dict[str, int] = {}
    for page in range(1, args.pages + 1):
        url = f"{origin}{spec.catalog_feed_path}?limit={args.page_size}&page={page}"
        try:
            body = _fetch(url)
        except Exception as exc:  # noqa: BLE001 - one page failing is not the walk failing
            print(f"page {page}: fetch failed {type(exc).__name__}", file=sys.stderr)
            continue

        raws = parse_shopify_catalog(body, url, spec)
        if not raws:
            print(f"page {page}: no listings, stopping")
            break

        # `ingest_products` speaks the feed's own shape, so hand it the raw
        # products and let it own the fetch-describe-store loop and its failure
        # counting. The candidate conversion happens where the listing is put.
        payload = json.loads(body).get("products") or []
        by_handle = {str(item.get("handle")): item for item in payload}

        def put(
            item: dict[str, Any],
            descriptors: dict[str, list[float]],
            _raws: list[Any] = raws,
        ) -> None:
            # `_raws` is bound per page on purpose. A closure over the loop
            # variable would index every page against the last page's listings.
            handle = str(item.get("handle"))
            raw = next((r for r in _raws if handle and handle in str(r.url)), None)
            if raw is None:
                return
            index.put_listing(normalize_raw(raw), versions, descriptors=descriptors)

        report = ingest_products(
            (by_handle[h] for h in by_handle),
            put_listing=put,
            fetch_image=_fetch,
            describe=descriptor_from_bytes,
            max_images_per_product=args.images,
        )
        for key, value in report.as_payload().items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
        print(f"page {page}: {json.dumps(report.as_payload())}")

    print(json.dumps({"source": args.source, "totals": totals}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
