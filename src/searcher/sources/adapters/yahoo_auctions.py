"""Yahoo Auctions JP item pages. review_required: disabled by default."""

from __future__ import annotations

from searcher.sources.adapters.product import YAHOO_AUCTIONS, ProductPageAdapter


class YahooAuctionsAdapter(ProductPageAdapter):
    def __init__(self) -> None:
        super().__init__(YAHOO_AUCTIONS)
