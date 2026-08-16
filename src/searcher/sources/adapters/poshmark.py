"""Poshmark listing pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import POSHMARK, ProductPageAdapter


class PoshmarkAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(POSHMARK)
