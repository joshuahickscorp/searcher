"""The RealReal: admitted item pages and sitemap."""

from __future__ import annotations

from searcher.sources.adapters.product import REALREAL, ProductPageAdapter


class TheRealRealAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(REALREAL)
