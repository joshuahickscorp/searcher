"""Byronesque: admitted archival designer pages."""

from __future__ import annotations

from searcher.sources.adapters.product import BYRONESQUE, ProductPageAdapter


class ByronesqueAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(BYRONESQUE)
