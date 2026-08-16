"""Cheap Stage A signals. Recall-oriented; never a blended public score."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.models import ItemHypothesis, ListingCandidate, VisualSignature
from searcher.reference.imaging import average_hash, colour_histogram, hamming
from searcher.reference.vocab import category_of
from searcher.retrieval.text import text_identity, tokenize


@dataclass
class CheapSignals:
    candidate_id: str
    text_identity: float = 0.0
    ocr_overlap: float = 0.0
    perceptual: float = 0.0
    colour: float = 0.0
    silhouette: float = 0.0
    category: float = 0.0
    brand: float = 0.0
    source_meta: float = 0.0
    embedding: float | None = None
    recall_score: float = 0.0
    notes: list[str] = field(default_factory=list)


def _hist_l1(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, 1.0 - 0.5 * sum(abs(x - y) for x, y in zip(a, b, strict=True)))


def _terms_from_hypothesis(hypothesis: ItemHypothesis) -> list[str]:
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
            parts.append(belief.value)
    for alias in hypothesis.aliases:
        parts.append(alias.alias)
    for code in hypothesis.product_codes:
        if code.value:
            parts.append(str(code.value))
    parts.extend(hypothesis.visual_signature.ocr_terms)
    return tokenize(" ".join(parts))


def _listing_terms(candidate: ListingCandidate, extra_ocr: list[str]) -> list[str]:
    blobs: list[str] = []
    if candidate.title and candidate.title.value:
        blobs.append(str(candidate.title.value))
    if candidate.description and candidate.description.value:
        blobs.append(str(candidate.description.value))
    if candidate.seller_reported_brand and candidate.seller_reported_brand.value:
        blobs.append(str(candidate.seller_reported_brand.value))
    if candidate.seller_reported_model and candidate.seller_reported_model.value:
        blobs.append(str(candidate.seller_reported_model.value))
    blobs.extend(extra_ocr)
    return tokenize(" ".join(blobs))


def compute_cheap_signals(
    *,
    candidate: ListingCandidate,
    hypothesis: ItemHypothesis,
    reference_signature: VisualSignature,
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, bytes],
    candidate_ocr: list[str] | None = None,
    embedding_similarity: float | None = None,
) -> CheapSignals:
    query_terms = _terms_from_hypothesis(hypothesis)
    listing_terms = _listing_terms(candidate, candidate_ocr or [])
    text = text_identity(query_terms, listing_terms)
    ocr_terms = tokenize(" ".join(reference_signature.ocr_terms))
    ocr = text_identity(ocr_terms, listing_terms) if ocr_terms else 0.0

    ref_hashes = [average_hash(png) for png in reference_pngs.values()]
    cand_hashes = [average_hash(png) for png in candidate_pngs.values()]
    perceptual = 0.0
    if ref_hashes and cand_hashes:
        best = 0.0
        for rh in ref_hashes:
            for ch in cand_hashes:
                best = max(best, max(0.0, 1.0 - hamming(rh, ch) / 64.0))
        perceptual = best

    ref_hists = [colour_histogram(png) for png in reference_pngs.values()]
    cand_hists = [colour_histogram(png) for png in candidate_pngs.values()]
    colour = 0.0
    if ref_hists and cand_hists:
        colour = max(_hist_l1(a, b) for a in ref_hists for b in cand_hists)

    silhouette = 0.0
    ref_sil = reference_signature.global_features.silhouette
    if ref_sil and candidate_pngs:
        from searcher.core.ids import sha256_hex
        from searcher.reference.imaging import silhouette_mask_png

        cand_sils = [sha256_hex(silhouette_mask_png(png)) for png in candidate_pngs.values()]
        silhouette = 1.0 if ref_sil in cand_sils else 0.35 * perceptual

    category = 0.0
    title = str(candidate.title.value) if candidate.title and candidate.title.value else ""
    listing_cat = None
    for token in tokenize(title):
        listing_cat = category_of(token)
        if listing_cat:
            break
    if hypothesis.category and listing_cat:
        category = 1.0 if listing_cat == hypothesis.category else 0.15
    elif hypothesis.category:
        category = 0.4

    brand = 0.0
    brand_val = (hypothesis.brand.value or "").lower()
    if brand_val:
        blob = " ".join(listing_terms)
        brand = 1.0 if brand_val.split()[0] in blob else 0.0

    source_meta = 0.4
    if candidate.source_adapter:
        source_meta = 0.55

    recall = (
        0.32 * text
        + 0.12 * ocr
        + 0.22 * perceptual
        + 0.14 * colour
        + 0.08 * silhouette
        + 0.07 * category
        + 0.05 * brand
    )
    if embedding_similarity is not None:
        recall = 0.85 * recall + 0.15 * embedding_similarity

    return CheapSignals(
        candidate_id=candidate.candidate_id,
        text_identity=round(text, 6),
        ocr_overlap=round(ocr, 6),
        perceptual=round(perceptual, 6),
        colour=round(colour, 6),
        silhouette=round(silhouette, 6),
        category=round(category, 6),
        brand=round(brand, 6),
        source_meta=round(source_meta, 6),
        embedding=embedding_similarity,
        recall_score=round(max(0.0, min(1.0, recall)), 6),
    )
