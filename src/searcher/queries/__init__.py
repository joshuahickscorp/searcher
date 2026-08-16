"""Query compiler."""

from __future__ import annotations

from searcher.queries.compiler import compile_queries
from searcher.queries.dedupe import dedupe_queries
from searcher.queries.information_gain import order_by_gain

__all__ = ["compile_queries", "dedupe_queries", "order_by_gain"]
