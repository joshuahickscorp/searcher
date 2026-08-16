"""Stages B–G: isolate, parts, correspondence, geometry, explain."""

from __future__ import annotations

from searcher.contracts.enums import Availability, EvidencePolarity, FactClass, FactOrigin
from searcher.contracts.models import (
    ItemHypothesis,
    ListingCandidate,
    ListingImage,
    MatchEvidence,
    SearchConstraints,
)
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.core.ids import new_id
from searcher.matching.broad import global_visual
from searcher.matching.combine import combine_item_match, make_part_match, part_matches_mean, tight
from searcher.matching.contradictions import item_contradictions
from searcher.matching.correspondence import correspond_pair
from searcher.matching.cross_image import cross_view_consistency
from searcher.matching.explanations import build_match_explanation, cite
from searcher.matching.geometry import compare_geometry
from searcher.matching.materials import colour_consistency
from searcher.matching.ontology import CategoryOntology, ontology_for
from searcher.matching.parts import build_descriptors, extract_parts
from searcher.matching.scores import scored
from searcher.matching.segmentation import gallery_images, isolate_subjects
from searcher.matching.structure import extract_structure
from searcher.matching.types import EnrichedCandidate, StructuredDescriptor
from searcher.matching.views import classify_subjects, refine_views
from searcher.retrieval.cost import CostLedger, CostStage
from searcher.retrieval.signals import compute_cheap_signals
from searcher.retrieval.text import text_identity, tokenize


def enrich_candidate(
    candidate: ListingCandidate,
    pngs: dict[str, bytes],
    *,
    ocr_terms: list[str] | None = None,
    ontology: CategoryOntology | None = None,
    ledger: CostLedger | None = None,
) -> EnrichedCandidate:
    images: list[tuple[ListingImage, bytes]] = []
    for image in candidate.images:
        raw = pngs.get(image.listing_image_id)
        if raw is None:
            continue
        images.append((image, raw))
    if ledger is not None:
        ledger.record(CostStage.LOCAL_PARTS, detail=f"isolate n={len(images)}")
    isolated = isolate_subjects(images)
    gallery = gallery_images(isolated)
    views = classify_subjects(gallery)
    descriptors = build_descriptors(gallery)
    views = refine_views(views, descriptors)
    parts = extract_parts(
        ontology=ontology or ontology_for("footwear"),
        subjects=gallery,
        views=views,
        descriptors=descriptors,
    )
    families = [
        img.duplicate_family_id or img.content_digest or img.listing_image_id
        for img in candidate.images
    ]
    return EnrichedCandidate(
        candidate=candidate,
        pngs=pngs,
        ocr_terms=list(ocr_terms or []),
        isolated=gallery,
        views=views,
        parts=parts,
        descriptors=descriptors,
        cluster_id=candidate.cluster_id,
        image_family_ids=[item for item in families if item],
    )


def _primary_descriptor(
    descriptors: dict[str, StructuredDescriptor],
) -> StructuredDescriptor | None:
    if not descriptors:
        return None
    # Prefer the most "lateral-like" (highest aspect among product shots).
    return max(
        descriptors.values(),
        key=lambda item: (item.eyelet_count, item.panel_count, item.aspect),
    )


def _text_score(
    hypothesis: ItemHypothesis, candidate: ListingCandidate, extra: list[str]
) -> ScoreWithEvidence:
    query: list[str] = []
    for belief in (hypothesis.brand, hypothesis.model_name, hypothesis.line, hypothesis.year):
        if belief.value:
            query.extend(tokenize(belief.value))
    query.extend(tokenize(" ".join(hypothesis.visual_signature.ocr_terms)))
    blobs: list[str] = []
    for fact in (candidate.title, candidate.description, candidate.seller_reported_model):
        if fact and fact.value:
            blobs.append(str(fact.value))
    blobs.extend(extra)
    mean = text_identity(query, tokenize(" ".join(blobs)))
    return scored(mean, spread=0.06, support=[cite("text", "identity")])


def match_candidate(
    *,
    hypothesis: ItemHypothesis,
    candidate: EnrichedCandidate,
    reference_pngs: dict[str, bytes],
    reference_descriptors: dict[str, StructuredDescriptor],
    constraints: SearchConstraints | None = None,
    ledger: CostLedger | None = None,
) -> MatchEvidence:
    ontology = ontology_for(hypothesis.category)
    del ontology
    exact_colour = bool(constraints and constraints.colour)
    ref_desc = _primary_descriptor(reference_descriptors)
    cand_desc = _primary_descriptor(candidate.descriptors)
    ref_png = next(iter(reference_pngs.values())) if reference_pngs else None
    cand_png = next(iter(candidate.pngs.values())) if candidate.pngs else None

    text = _text_score(hypothesis, candidate.candidate, candidate.ocr_terms)
    if ref_desc and cand_desc and ref_png and cand_png:
        glob = global_visual(ref_desc, cand_desc, reference_png=ref_png, candidate_png=cand_png)
        geom_raw = compare_geometry(ref_desc, cand_desc)
        used_mirror = False
        flipped_desc = _flipped_descriptor(cand_png, cand_desc.image_id)
        if flipped_desc is not None:
            geom_flip = compare_geometry(ref_desc, flipped_desc)
            if geom_flip.score > geom_raw.score:
                geom_raw = geom_flip
                cand_desc = flipped_desc
                used_mirror = True
        geometry = tight(
            geom_raw.score,
            support=[cite("geometry", note) for note in geom_raw.notes] or [cite("geometry", "ok")],
        )
        colour_score, colour_contra, _ = colour_consistency(
            ref_desc, cand_desc, exact_colour_required=exact_colour
        )
        material = scored(
            colour_score,
            spread=0.08,
            support=[] if colour_contra else [cite("colour", "hist")],
            contradictions=colour_contra,
            polarity=(
                EvidencePolarity.CONTRADICTORY if colour_contra else EvidencePolarity.SUPPORTING
            ),
        )
        corr = correspond_pair(ref_png, cand_png, ledger=ledger)
        ref_label = next(
            (d.label_hash for d in reference_descriptors.values() if d.label_hash), None
        )
        cand_label = next(
            (d.label_hash for d in candidate.descriptors.values() if d.label_hash), None
        )
        label_mismatch = bool(
            ref_label and cand_label and ref_label != cand_label and not used_mirror
        )
        hard, soft = item_contradictions(
            reference=ref_desc,
            candidate=cand_desc,
            geometry=geom_raw,
            exact_colour_required=exact_colour,
            colour_hard="colourway-mismatch" in colour_contra,
            label_hash_mismatch=label_mismatch,
        )
        part_records = []
        outsole_delta = 1 if "outsole" in " ".join(hard) else 0
        heel_delta = 1 if any("heel" in item for item in hard) else 0
        logo_delta = 1 if any("logo" in item for item in hard + soft) else 0
        for name, delta, ref_v, cand_v in (
            ("eyelets", geom_raw.eyelet_delta, ref_desc.eyelet_count, cand_desc.eyelet_count),
            ("lateral_panels", geom_raw.panel_delta, ref_desc.panel_count, cand_desc.panel_count),
            ("outsole", outsole_delta, ref_desc.outsole_ratio, cand_desc.outsole_ratio),
            ("heel", heel_delta, ref_desc.heel_cut, cand_desc.heel_cut),
            ("logo", logo_delta, ref_desc.logo_kind, cand_desc.logo_kind),
        ):
            step = float(delta if isinstance(delta, int) else 1)
            mean = 0.95 if delta == 0 else max(0.1, 0.55 - 0.2 * step)
            part_records.append(
                make_part_match(name, mean, explanation=f"ref={ref_v} cand={cand_v}")
            )
        parts_mean = part_matches_mean(part_records)
        # Correspondence is supporting geometry, not a substitute score.
        if corr.inlier_ratio > 0.4:
            geometry = tight(
                min(1.0, geometry.interval.mean + 0.04),
                support=list(geometry.support) + [cite("correspondence", corr.method)],
            )
    else:
        cheap = compute_cheap_signals(
            candidate=candidate.candidate,
            hypothesis=hypothesis,
            reference_signature=hypothesis.visual_signature,
            reference_pngs=reference_pngs,
            candidate_pngs=candidate.pngs,
            candidate_ocr=candidate.ocr_terms,
        )
        glob = scored(cheap.perceptual, spread=0.12, missing=["structure"])
        geometry = scored(0.45, spread=0.2, missing=["geometry"])
        material = scored(cheap.colour, spread=0.14)
        part_records = []
        parts_mean = 0.4
        hard, soft = [], []
        colour_contra = []
        label_mismatch = False

    gallery = list(candidate.descriptors.values())
    cross_score, cross_hard, cross_missing = cross_view_consistency(gallery)
    cross = scored(
        cross_score,
        spread=0.1,
        support=[cite("cross", "gallery")] if not cross_hard else [],
        contradictions=cross_hard,
        missing=cross_missing,
    )
    hard.extend(cross_hard)

    missing_views: list[str] = []
    present = {v.view.value for v in candidate.views}
    for expected in ("lateral", "heel", "sole", "label"):
        if expected not in present:
            missing_views.append(expected)

    interval = combine_item_match(
        text=text,
        global_visual=glob,
        parts_mean=parts_mean,
        geometry=geometry,
        material=material,
        cross=cross,
        hard_count=len(hard),
        missing_count=len(missing_views),
    )
    seller_fields = []
    if candidate.candidate.title:
        seller_fields.append("title")
    if candidate.candidate.description:
        seller_fields.append("description")
    support = [
        cite("text", "identity"),
        cite("global", "visual"),
        cite("parts", "ontology"),
        cite("geometry", "relations"),
    ]
    explanation = build_match_explanation(
        support=support,
        contradictions=hard + soft,
        missing=missing_views,
        live=candidate.candidate.availability or Availability.UNKNOWN,
        checked_at=candidate.candidate.last_checked_at,
        compared=list(candidate.pngs.keys())[:8],
        families=candidate.image_family_ids,
        seller_fields=seller_fields,
    )
    metadata = scored(
        0.55,
        spread=0.12,
        support=[cite("meta", "source")],
        missing=[],
    )
    # Seller origin facts stay reported.
    if candidate.candidate.title and candidate.candidate.title.origin is FactOrigin.SELLER:
        metadata = ScoreWithEvidence(
            interval=metadata.interval,
            support=metadata.support,
            contradictions=metadata.contradictions,
            missing=metadata.missing,
            fact_class=FactClass.REPORTED_BY_SELLER,
            polarity=metadata.polarity,
        )
    return MatchEvidence(
        match_evidence_id=new_id(),
        candidate_id=candidate.candidate.candidate_id,
        hypothesis_id=hypothesis.hypothesis_id,
        global_visual=glob,
        text_identity=text,
        part_correspondence=part_records,
        geometry=geometry,
        material=material,
        colourway=material,
        cross_image_consistency=cross,
        metadata_consistency=metadata,
        hard_support=[s for s in support if not hard],
        soft_support=soft and [] or support,
        hard_contradictions=hard,
        soft_contradictions=soft,
        missing_views=missing_views,
        item_match_distribution=interval,
        explanation=explanation,
    )


def _flipped_descriptor(png: bytes, image_id: str) -> StructuredDescriptor | None:
    from io import BytesIO

    from PIL import Image as PILImage

    from searcher.reference.imaging import open_rgb

    try:
        image = open_rgb(png).transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
    except Exception:
        return None
    buf = BytesIO()
    image.save(buf, format="PNG")
    return extract_structure(buf.getvalue(), image_id=f"{image_id}-mirror")


def prepare_reference(
    pngs: dict[str, bytes],
    *,
    ledger: CostLedger | None = None,
) -> dict[str, StructuredDescriptor]:
    if ledger is not None:
        ledger.record(CostStage.LOCAL_PARTS, detail="reference_structure")
    return {image_id: extract_structure(png, image_id=image_id) for image_id, png in pngs.items()}
