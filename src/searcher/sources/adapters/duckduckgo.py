"""DuckDuckGo HTML. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import DUCKDUCKGO, ProductPageAdapter


class DuckDuckGoAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(DUCKDUCKGO)
