"""Heroine (shopheroine.com). Storefront identity is an open question."""

from __future__ import annotations

from searcher.sources.adapters.product import HEROINE, ProductPageAdapter


class HeroineAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(HEROINE)
