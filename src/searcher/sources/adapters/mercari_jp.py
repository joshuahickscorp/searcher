"""Mercari JP item pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import MERCARI_JP, ProductPageAdapter


class MercariJpAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(MERCARI_JP)
