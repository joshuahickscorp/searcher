"""Index a source's catalogue independently of any query.

The warm index is populated by `remember_campaign` from candidates a campaign
already retrieved. That makes it a cache of past text searches: a listing no
query ever named was never indexed, so the descriptor search added alongside it
has nothing to find. Visual retrieval works and searches an empty shelf.

This fills the shelf. It walks a source's product feed and indexes each product
with the descriptors of its images, asking nothing about what anyone searched
for. A plain garment with a generic title is then findable by its photographs,
which is the only route that can reach it.

Deliberately not wired into the campaign path. A search must not pay for a
catalogue walk, and an ingest triggered per campaign would do exactly that. This
is for an operator or a scheduled job to run against an admitted source.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngestReport:
    """What an ingest actually did, in terms a reader can check."""

    products_seen: int = 0
    listings_indexed: int = 0
    images_described: int = 0
    skipped_no_images: int = 0
    skipped_no_descriptor: int = 0
    errors: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return {
            "products_seen": self.products_seen,
            "listings_indexed": self.listings_indexed,
            "images_described": self.images_described,
            "skipped_no_images": self.skipped_no_images,
            "skipped_no_descriptor": self.skipped_no_descriptor,
            "errors": list(self.errors),
        }


def ingest_products(
    products: Iterable[dict[str, Any]],
    *,
    put_listing: Callable[[dict[str, Any], dict[str, list[float]]], None],
    fetch_image: Callable[[str], bytes | None],
    describe: Callable[[bytes], list[float] | None],
    max_images_per_product: int = 3,
) -> IngestReport:
    """Index each product, with a descriptor per image that yields one.

    The callables are injected rather than imported so this can be exercised
    without a network, a model or a database. The alternative - reaching for the
    real fetcher and the real store inside the loop - is what makes an ingest
    testable only by running it against a live shop, and an ingest nobody can
    test in isolation is one whose failures are only ever seen in production.

    Only the first few images of a product are described. A listing is found by
    whichever of its photographs matches, so the tenth angle adds little and
    costs a fetch and a forward pass each time.
    """
    report = IngestReport()

    for product in products:
        report.products_seen += 1
        images = [
            str(row.get("src") or "").strip()
            for row in (product.get("images") or [])
            if isinstance(row, dict) and str(row.get("src") or "").strip()
        ]
        if not images:
            report.skipped_no_images += 1
            continue

        descriptors: dict[str, list[float]] = {}
        for url in images[:max_images_per_product]:
            try:
                data = fetch_image(url)
            except Exception as exc:  # noqa: BLE001 - one bad image is not fatal
                report.errors.append(f"fetch {url}: {type(exc).__name__}")
                continue
            if not data:
                continue
            try:
                vector = describe(data)
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"describe {url}: {type(exc).__name__}")
                continue
            if vector:
                descriptors[url] = vector

        if not descriptors:
            report.skipped_no_descriptor += 1
            continue

        try:
            put_listing(product, descriptors)
        except Exception as exc:  # noqa: BLE001 - keep walking the catalogue
            report.errors.append(f"index {product.get('handle')}: {type(exc).__name__}")
            continue

        report.listings_indexed += 1
        report.images_described += len(descriptors)

    return report
