# Ported idea from Job Scraper frozen snapshot
# path: <home>/.searcher-donors/jobscraper-frozen-20260816/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.fetchers.resolve_fetcher / FETCHER_REGISTRY
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Name → adapter factory. Registers Searcher adapters, not ATS fetchers."""

from __future__ import annotations

from collections.abc import Callable

from searcher.sources.adapters.archive_org import ArchiveOrgAdapter
from searcher.sources.adapters.bunjang import BunjangAdapter
from searcher.sources.adapters.buyee import BuyeeAdapter
from searcher.sources.adapters.byronesque import ByronesqueAdapter
from searcher.sources.adapters.duckduckgo import DuckDuckGoAdapter
from searcher.sources.adapters.ebay_api import EbayApiAdapter
from searcher.sources.adapters.etsy_api import EtsyApiAdapter
from searcher.sources.adapters.farfetch import FarfetchAdapter
from searcher.sources.adapters.generic_page import GenericPageAdapter
from searcher.sources.adapters.goat import GoatAdapter
from searcher.sources.adapters.heroine import HeroineAdapter
from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.adapters.komehyo import KomehyoAdapter
from searcher.sources.adapters.marginalia import MarginaliaAdapter
from searcher.sources.adapters.mercari_jp import MercariJpAdapter
from searcher.sources.adapters.poshmark import PoshmarkAdapter
from searcher.sources.adapters.rebag import RebagAdapter
from searcher.sources.adapters.searx import SearxAdapter
from searcher.sources.adapters.sitemap import SitemapAdapter
from searcher.sources.adapters.ssense import SsenseAdapter
from searcher.sources.adapters.stockx import StockxAdapter
from searcher.sources.adapters.the_realreal import TheRealRealAdapter
from searcher.sources.adapters.vinted import VintedAdapter
from searcher.sources.adapters.wikimedia import WikimediaAdapter
from searcher.sources.adapters.yahoo_auctions import YahooAuctionsAdapter

Factory = Callable[[], object]

ADAPTER_REGISTRY: dict[str, Factory] = {
    "searx": SearxAdapter,
    "wikimedia": WikimediaAdapter,
    "marginalia": MarginaliaAdapter,
    "archive_org": ArchiveOrgAdapter,
    "generic_page": GenericPageAdapter,
    "sitemap": lambda: SitemapAdapter(sitemap_url="https://example.invalid/sitemap.xml"),
    "the_realreal": TheRealRealAdapter,
    "rebag": RebagAdapter,
    "komehyo": KomehyoAdapter,
    "kind": KindAdapter,
    "byronesque": ByronesqueAdapter,
    "heroine": HeroineAdapter,
    "ebay": EbayApiAdapter,
    "etsy": EtsyApiAdapter,
    "mercari_jp": MercariJpAdapter,
    "yahoo_auctions": YahooAuctionsAdapter,
    "buyee": BuyeeAdapter,
    "vinted": VintedAdapter,
    "bunjang": BunjangAdapter,
    "ssense": SsenseAdapter,
    "farfetch": FarfetchAdapter,
    "stockx": StockxAdapter,
    "goat": GoatAdapter,
    "poshmark": PoshmarkAdapter,
    "duckduckgo": DuckDuckGoAdapter,
}


def resolve_adapter(name: str) -> object:
    factory = ADAPTER_REGISTRY.get(name)
    if factory is None:
        raise KeyError(name)
    return factory()


def all_adapter_names() -> list[str]:
    return sorted(ADAPTER_REGISTRY)
