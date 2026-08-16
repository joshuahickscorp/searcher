"""Rebag: admitted product pages."""

from __future__ import annotations

from searcher.sources.adapters.product import REBAG, ProductPageAdapter


class RebagAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(REBAG)
