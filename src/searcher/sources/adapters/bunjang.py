"""Bunjang public pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import BUNJANG, ProductPageAdapter


class BunjangAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(BUNJANG)
