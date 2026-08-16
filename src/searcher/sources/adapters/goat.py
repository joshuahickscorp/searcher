"""GOAT product pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import GOAT, ProductPageAdapter


class GoatAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(GOAT)
