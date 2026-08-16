"""Vinted items. review_required: disabled by default. Content-Signal search=yes."""

from __future__ import annotations

from searcher.sources.adapters.product import VINTED, ProductPageAdapter


class VintedAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(VINTED)
