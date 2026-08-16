"""Farfetch product pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import FARFETCH, ProductPageAdapter


class FarfetchAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(FARFETCH)
