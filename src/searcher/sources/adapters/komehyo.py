"""Komehyo: admitted JP consignment product pages."""

from __future__ import annotations

from searcher.sources.adapters.product import KOMEHYO, ProductPageAdapter


class KomehyoAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(KOMEHYO)
