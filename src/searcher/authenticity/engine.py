"""Authenticity evidence engine. Independent of item match."""

from __future__ import annotations

from decimal import Decimal

from searcher.authenticity.calibration import load_table, locate_default_table
from searcher.authenticity.completeness import completeness
from searcher.authenticity.construction import assess_construction
from searcher.authenticity.decision import combine_authenticity
from searcher.authenticity.labels import assess_labels
from searcher.authenticity.logos import assess_logos
from searcher.authenticity.materials import assess_materials
from searcher.authenticity.originality import assess_originality
from searcher.authenticity.photo_integrity import assess_photo_set
from searcher.authenticity.profiles import profile_for
from searcher.authenticity.provenance import assess_provenance
from searcher.authenticity.source_signals import assess_source
from searcher.contracts.enums import Availability
from searcher.contracts.models import AuthenticityEvidence, ItemHypothesis, SearchConstraints
from searcher.contracts.primitives import PublicExplanation, ScoreWithEvidence
from searcher.core.ids import new_id
from searcher.core.policy import apply_price_to_authenticity
from searcher.evidence.records import EvidenceRecord
from searcher.matching.explanations import cite
from searcher.matching.scores import scored
from searcher.matching.types import EnrichedCandidate, StructuredDescriptor
from searcher.ranking.vetoes import url_is_malicious
from searcher.retrieval.cost import CostLedger, CostStage


def _price_score(
    candidate: EnrichedCandidate,
    constraints: SearchConstraints | None,
) -> ScoreWithEvidence:
    price = candidate.candidate.price_original
    cap = constraints.price_max if constraints else None
    # Neutral 0.5. High price does not help; unusually low may pull down later.
    mean = 0.5
    if price is not None and cap is not None and cap > 0:
        ratio = float(price / cap) if isinstance(price, Decimal) else float(price) / float(cap)
        if ratio < 0.25:
            mean = 0.35
    # Guard: even a "good" price stays at 0.5 so it cannot raise authenticity.
    mean = apply_price_to_authenticity(0.5, max(0.0, mean - 0.5) if mean > 0.5 else mean - 0.5)
    return scored(mean, spread=0.05, support=[cite("price", "anomaly-only")])


def assess_authenticity(
    *,
    hypothesis: ItemHypothesis,
    candidate: EnrichedCandidate,
    reference_descriptors: dict[str, StructuredDescriptor],
    constraints: SearchConstraints | None = None,
    image_records: list[EvidenceRecord] | None = None,
    stolen_photo: bool = False,
    stock_mixed: bool = False,
    ledger: CostLedger | None = None,
    deep: bool = False,
) -> AuthenticityEvidence:
    if ledger is not None and deep:
        ledger.record(CostStage.DEEP_AUTHENTICITY, detail="deep")
    profile = profile_for(hypothesis.category)
    present = {view.view.value for view in candidate.views}
    complete, missing_views = completeness(profile=profile, present_views=present)
    ref = _pick(reference_descriptors)
    cand = _pick(candidate.descriptors)
    if ref is not None and cand is not None:
        from searcher.matching.geometry import compare_geometry
        from searcher.matching.pipeline import _flipped_descriptor

        primary_png = candidate.pngs.get(cand.image_id)
        if primary_png:
            flipped = _flipped_descriptor(primary_png, cand.image_id)
            if (
                flipped is not None
                and compare_geometry(ref, flipped).score > compare_geometry(ref, cand).score
            ):
                cand = flipped
    ref_label = _pick_label(reference_descriptors)
    cand_label = _pick_label(candidate.descriptors)
    construction, ch, _cs = assess_construction(profile=profile, reference=ref, candidate=cand)
    labels, lh, lm = assess_labels(
        reference=ref_label,
        candidate=cand_label,
        listing_text=(
            str(candidate.candidate.description.value)
            if candidate.candidate.description and candidate.candidate.description.value
            else None
        ),
        reference_code=hypothesis.product_codes[0].value if hypothesis.product_codes else None,
    )
    logos, gh, gm = assess_logos(reference=ref, candidate=cand)
    materials, mh, _ms = assess_materials(
        reference=ref,
        candidate=cand,
        exact_colour_required=bool(constraints and constraints.colour),
    )
    photo, ph, pm = assess_photo_set(list(candidate.descriptors.values()), stock_mixed=stock_mixed)
    original, oh, _om = assess_originality(
        image_records=image_records or [],
        stolen_photo=stolen_photo,
        known_stock_hit=stolen_photo,
    )
    source, sh, _sm = assess_source(
        candidate.candidate,
        malicious_url=url_is_malicious(candidate.candidate.canonical_url),
    )
    provenance, pmiss = assess_provenance(candidate.candidate)
    price = _price_score(candidate, constraints)
    hard = ch + lh + gh + mh + ph + oh + sh
    soft: list[str] = []
    missing = list(dict.fromkeys(missing_views + lm + gm + pm + pmiss))
    table = load_table(locate_default_table())
    signals = combine_authenticity(
        construction=construction,
        labels=labels,
        logos=logos,
        materials=materials,
        photo_set=photo,
        originality=original,
        source=source,
        provenance=provenance,
        price=price,
        hard=hard,
        soft=soft,
        missing=missing,
        completeness_value=complete,
        table=table,
    )
    assert signals.interval is not None
    explanation = PublicExplanation(
        support=[cite("auth", "categories")] if not hard else [],
        contradictions=hard,
        missing_evidence=missing,
        live_status=candidate.candidate.availability or Availability.UNKNOWN,
        last_checked_at=candidate.candidate.last_checked_at,
        compared_images=list(candidate.pngs.keys())[:8],
        duplicate_image_families=candidate.image_family_ids,
        seller_reported_fields=["title"] if candidate.candidate.title else [],
    )
    return AuthenticityEvidence(
        authenticity_evidence_id=new_id(),
        candidate_id=candidate.candidate.candidate_id,
        reference_class=profile.profile_id,
        construction_consistency=construction,
        label_and_code_consistency=labels,
        logo_and_hardware_consistency=logos,
        material_consistency=materials,
        photo_set_consistency=photo,
        image_originality=original,
        source_and_seller_signal=source,
        provenance_signal=provenance,
        price_anomaly=price,
        hard_support=[],
        hard_contradictions=hard,
        missing_evidence=missing,
        authenticity_distribution=signals.interval,
        authority_ceiling=signals.authority_ceiling,
        explanation=explanation,
    )


def _pick(items: dict[str, StructuredDescriptor]) -> StructuredDescriptor | None:
    if not items:
        return None
    return max(items.values(), key=lambda item: (item.eyelet_count, item.panel_count))


def _pick_label(items: dict[str, StructuredDescriptor]) -> StructuredDescriptor | None:
    labeled = [item for item in items.values() if item.label_hash]
    if not labeled:
        return None
    return labeled[0]
