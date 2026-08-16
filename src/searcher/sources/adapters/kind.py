"""KIND (shop.kind.co.jp): product/collection allowed; /search disallowed."""

from __future__ import annotations

from searcher.sources.adapters.product import KIND, ProductPageAdapter


class KindAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(KIND)
