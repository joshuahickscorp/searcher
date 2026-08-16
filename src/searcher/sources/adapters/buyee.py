"""Buyee public catalog. review_required: disabled by default. Link only."""

from __future__ import annotations

from searcher.sources.adapters.product import BUYEE, ProductPageAdapter


class BuyeeAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(BUYEE)
