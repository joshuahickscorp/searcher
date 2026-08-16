"""Inverted-index terms. Listing text is untrusted data, never instructions."""

from __future__ import annotations

from collections import Counter

from searcher.contracts.models import ItemHypothesis, ListingCandidate, SearchIntent
from searcher.retrieval.text import tokenize


def field_terms(*blobs: str | None) -> list[str]:
    return tokenize(" ".join(part for part in blobs if part))


def term_frequencies(terms: list[str]) -> dict[str, int]:
    return dict(Counter(terms))


def listing_title_terms(candidate: ListingCandidate) -> list[str]:
    value = candidate.title.value if candidate.title is not None else None
    brand = candidate.seller_reported_brand.value if candidate.seller_reported_brand else None
    model = candidate.seller_reported_model.value if candidate.seller_reported_model else None
    return field_terms(
        str(value) if value is not None else None,
        str(brand) if brand is not None else None,
        str(model) if model is not None else None,
    )


def listing_description_terms(candidate: ListingCandidate) -> list[str]:
    value = candidate.description.value if candidate.description is not None else None
    return field_terms(str(value) if value is not None else None)


def intent_terms(intent: SearchIntent) -> list[str]:
    return field_terms(intent.text, " ".join(intent.tags))


def hypothesis_terms(hypothesis: ItemHypothesis) -> list[str]:
    parts: list[str] = []
    for belief in (
        hypothesis.brand,
        hypothesis.model_name,
        hypothesis.line,
        hypothesis.designer,
        hypothesis.season,
        hypothesis.year,
        hypothesis.colourway,
    ):
        if belief.value:
            parts.append(str(belief.value))
    for alias in hypothesis.aliases:
        parts.append(alias.alias)
    for code in hypothesis.product_codes:
        if code.value:
            parts.append(str(code.value))
    parts.extend(hypothesis.visual_signature.ocr_terms)
    return field_terms(*parts)


def query_terms(intent: SearchIntent, hypotheses: list[ItemHypothesis]) -> list[str]:
    terms = list(intent_terms(intent))
    for hyp in hypotheses:
        terms.extend(hypothesis_terms(hyp))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            out.append(term)
    return out
