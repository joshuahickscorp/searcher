"""Query deduplication and contamination controls."""

from __future__ import annotations

import re

from searcher.contracts.models import QueryVariant

_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[\"'`]+")


def normalize_query_text(text: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub("", text)).strip().lower()


def token_set(text: str) -> frozenset[str]:
    return frozenset(normalize_query_text(text).split())


def jaccard(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def dedupe_queries(queries: list[QueryVariant], *, similarity: float = 0.86) -> list[QueryVariant]:
    kept: list[QueryVariant] = []
    seen: set[str] = set()
    for query in queries:
        key = normalize_query_text(query.query_text)
        if not key or key in seen:
            continue
        if any(jaccard(query.query_text, other.query_text) >= similarity for other in kept):
            continue
        seen.add(key)
        kept.append(query)
    return kept


def drop_demoted(queries: list[QueryVariant], demoted: set[str]) -> list[QueryVariant]:
    banned = {normalize_query_text(term) for term in demoted}
    if not banned:
        return queries
    kept: list[QueryVariant] = []
    for query in queries:
        tokens = token_set(query.query_text)
        if any(term in tokens or term in normalize_query_text(query.query_text) for term in banned):
            continue
        kept.append(query)
    return kept
