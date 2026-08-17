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
from searcher.matching.parts import build_descriptors, compare_extracted_parts, extract_parts
from searcher.matching.scores import scored
from searcher.matching.segmentation import gallery_images, isolate_subjects
from searcher.matching.structure import extract_structure
from searcher.matching.types import (
    CorrespondenceResult,
    EnrichedCandidate,
    GeometryResult,
    StructuredDescriptor,
)
from searcher.matching.views import classify_subjects, refine_views
from searcher.retrieval.cost import CostLedger, CostStage
from searcher.retrieval.embeddings import OPERATING_THRESHOLD, pair_similarity
from searcher.retrieval.signals import compute_cheap_signals
from searcher.retrieval.text import text_identity, tokenize

# Calibrated on fixtures/user_snapshots with the opencv detector: every true
# pair scored at or above 14 inliers and no different-listing pair exceeded 7.
# Ten sits in that gap. Absent opencv the detector is noise and never reaches
# this, which is why the fallback labels itself degraded.
CORRESPONDENCE_STRONG_INLIERS = 10


def enrich_candidate(
    candidate: ListingCandidate,
    pngs: dict[str, bytes],
    *,
    ocr_terms: list[str] | None = None,
    ontology: CategoryOntology | None = None,
    ledger: CostLedger | None = None,
    category: str | None = None,
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
    chosen_category = category or (ontology.category if ontology else None)
    views = classify_subjects(gallery, category=chosen_category)
    descriptors = build_descriptors(gallery)
    views = refine_views(views, descriptors, category=chosen_category)
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


def apply_category(candidate: EnrichedCandidate, category: str | None) -> EnrichedCandidate:
    """Re-read views and parts once the hypothesis category is known.

    The orchestrator enriches without a category, so the first pass either
    keeps a garment as front or, historically, refined it into a heel. Fine
    matching and authenticity both know the hypothesis; they re-apply it here
    rather than depending on the caller to pass ontology through.
    """
    if not category:
        return candidate
    views = classify_subjects(candidate.isolated, category=category)
    views = refine_views(views, candidate.descriptors, category=category)
    candidate.views = views
    candidate.parts = extract_parts(
        ontology=ontology_for(category),
        subjects=candidate.isolated,
        views=views,
        descriptors=candidate.descriptors,
    )
    return candidate


def _primary_descriptor(
    descriptors: dict[str, StructuredDescriptor],
    *,
    footwear: bool = True,
) -> StructuredDescriptor | None:
    if not descriptors:
        return None
    if footwear:
        return max(
            descriptors.values(),
            key=lambda item: (item.eyelet_count, item.panel_count, item.aspect),
        )
    return max(
        descriptors.values(),
        key=lambda item: (item.subject_area, item.keypoints, item.aspect),
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
    for fact in (
        candidate.title,
        candidate.description,
        candidate.seller_reported_brand,
        candidate.seller_reported_model,
    ):
        if fact and fact.value:
            blobs.append(str(fact.value))
    blobs.extend(extra)
    mean = text_identity(query, tokenize(" ".join(blobs)))
    return scored(mean, spread=0.06, support=[cite("text", "identity")])


def _blend_embedding(glob: ScoreWithEvidence, similarity: float | None) -> ScoreWithEvidence:
    if similarity is None:
        return glob
    if similarity >= OPERATING_THRESHOLD:
        mean = 0.35 * glob.interval.mean + 0.65 * similarity
        return scored(
            mean,
            spread=0.05,
            support=list(glob.support)
            + [cite("embedding", "cosine"), cite("embedding", "OBSERVED-pixels")],
            fact_class=FactClass.OBSERVED,
        )
    mean = 0.90 * glob.interval.mean + 0.10 * similarity
    return scored(
        mean,
        spread=0.08,
        support=list(glob.support) + [cite("embedding", "below-threshold")],
        missing=list(glob.missing),
        polarity=glob.polarity,
    )


def _png_for(image_id: str, pngs: dict[str, bytes]) -> bytes | None:
    return pngs.get(image_id)


def _pair_rank(
    ref_desc: StructuredDescriptor,
    cand_desc: StructuredDescriptor,
    visual: float,
    *,
    footwear: bool,
) -> tuple[float, float, float]:
    """Rank a pair the way correspondence ranks inliers: best evidence first.

    On footwear the identity-bearing view is the one where both photographs
    still have eyelets and panels. A heel-to-heel ahash can look strong while
    those counts are never compared. Bags have no such counts, so the rank
    is just the visual score — the same max-over-pairs rule as embeddings.
    """
    if footwear:
        return (
            float(min(ref_desc.eyelet_count, cand_desc.eyelet_count)),
            float(min(ref_desc.panel_count, cand_desc.panel_count)),
            visual,
        )
    return (visual, 0.0, 0.0)


def _capped_view_pairs(
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, bytes],
    reference_descriptors: dict[str, StructuredDescriptor],
    candidate_descriptors: dict[str, StructuredDescriptor],
    *,
    footwear: bool = False,
    max_pairs: int = 9,
) -> list[
    tuple[tuple[float, float, float], StructuredDescriptor, StructuredDescriptor, bytes, bytes]
]:
    """The pairs `_best_view_pair` ranks, same order and 9-pair budget.

    Identity may take the max. Colour, material, construction and geometry
    walk this same list.
    """
    considered: list[
        tuple[tuple[float, float, float], StructuredDescriptor, StructuredDescriptor, bytes, bytes]
    ] = []
    references = list(reference_descriptors.items())
    candidates = list(candidate_descriptors.items())
    if footwear:
        # Spend the 9-pair budget on laterals first, same ranking
        # `_primary_descriptor` used, so a 5×5 gallery still compares
        # the constructed views instead of burning the cap on soles.
        references.sort(
            key=lambda item: (item[1].eyelet_count, item[1].panel_count, item[1].aspect),
            reverse=True,
        )
        candidates.sort(
            key=lambda item: (item[1].eyelet_count, item[1].panel_count, item[1].aspect),
            reverse=True,
        )
    for ref_id, ref_desc in references:
        ref_png = _png_for(ref_id, reference_pngs) or _png_for(ref_desc.image_id, reference_pngs)
        if ref_png is None:
            continue
        for cand_id, cand_desc in candidates:
            cand_png = _png_for(cand_id, candidate_pngs) or _png_for(
                cand_desc.image_id, candidate_pngs
            )
            if cand_png is None:
                continue
            if len(considered) >= max_pairs:
                return considered
            visual = global_visual(
                ref_desc, cand_desc, reference_png=ref_png, candidate_png=cand_png
            ).interval.mean
            rank = _pair_rank(ref_desc, cand_desc, visual, footwear=footwear)
            considered.append((rank, ref_desc, cand_desc, ref_png, cand_png))
        if len(considered) >= max_pairs:
            break
    return considered


def _best_view_pair(
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, bytes],
    reference_descriptors: dict[str, StructuredDescriptor],
    candidate_descriptors: dict[str, StructuredDescriptor],
    *,
    footwear: bool = False,
    max_pairs: int = 9,
) -> tuple[
    StructuredDescriptor | None,
    StructuredDescriptor | None,
    bytes | None,
    bytes | None,
]:
    """The strongest visual pair for this candidate, not the first of each.

    Descriptor and pixels are always taken from the same photograph. A single
    globally chosen reference view is the wrong object to compare when the
    seller's matching photograph is the third frame. Bounded because this is
    the same budget as correspondence.
    """
    considered = _capped_view_pairs(
        reference_pngs,
        candidate_pngs,
        reference_descriptors,
        candidate_descriptors,
        footwear=footwear,
        max_pairs=max_pairs,
    )
    if not considered:
        return None, None, None, None
    _rank, ref_desc, cand_desc, ref_png, cand_png = max(considered, key=lambda item: item[0])
    return ref_desc, cand_desc, ref_png, cand_png


def _colour_pair_eligible(
    ref_desc: StructuredDescriptor,
    cand_desc: StructuredDescriptor,
    *,
    footwear: bool,
) -> bool:
    """Whether this pair is a colour reading of the item, not of a label card.

    A cream label next to a lateral of the same shoe is not a colourway
    contradiction. A true item has none to accumulate once mixed
    label/product pairs are set aside. Footwear further requires both
    photographs to still show eyelets: that is the same identity-bearing
    upper `_pair_rank` prefers, so a cooler extra lateral stays eligible.
    """
    if bool(ref_desc.label_hash) ^ bool(cand_desc.label_hash):
        return False
    return not (footwear and min(ref_desc.eyelet_count, cand_desc.eyelet_count) <= 0)


def _colour_across_pairs(
    considered: list[
        tuple[tuple[float, float, float], StructuredDescriptor, StructuredDescriptor, bytes, bytes]
    ],
    *,
    exact_colour: bool,
    chosen_ref: StructuredDescriptor,
    chosen_cand: StructuredDescriptor,
    footwear: bool,
) -> tuple[float, list[str]]:
    """Worst colour contradiction among considered pairs, else the chosen pair.

    Identity may keep the flattering pair. A contradiction on any other
    considered pair is not erasable by that choice.
    """
    chosen_score, chosen_contra, _ = colour_consistency(
        chosen_ref, chosen_cand, exact_colour_required=exact_colour
    )
    worst_contra_score: float | None = None
    found: list[str] = []
    for _rank, ref_desc, cand_desc, _ref_png, _cand_png in considered:
        if not _colour_pair_eligible(ref_desc, cand_desc, footwear=footwear):
            continue
        score, contra, _ = colour_consistency(
            ref_desc, cand_desc, exact_colour_required=exact_colour
        )
        # Soft view-to-view tint is not a colourway. A genuine bag's
        # fill-frame detail versus its front can trip colour-soft-difference
        # and would lower a true match. colourway-mismatch cannot: it is
        # the contradiction pairing erases by picking a cooler extra.
        hard = [item for item in contra if item == "colourway-mismatch"]
        if not hard:
            continue
        if worst_contra_score is None or score < worst_contra_score:
            worst_contra_score = score
        for item in hard:
            if item not in found:
                found.append(item)
    if not found:
        return chosen_score, chosen_contra
    merged = list(found)
    for item in chosen_contra:
        if item not in merged:
            merged.append(item)
    score = chosen_score if worst_contra_score is None else min(chosen_score, worst_contra_score)
    return score, merged


def _construction_pair_eligible(
    ref_desc: StructuredDescriptor,
    cand_desc: StructuredDescriptor,
    *,
    footwear: bool,
) -> bool:
    """Whether this pair is a construction reading of the same view.

    A cream label next to a lateral of the same shoe is not a construction
    contradiction. A true item has none to accumulate once mixed
    label/product pairs and cross-view pairs are set aside. Footwear uses
    outsole ratio as the view-class signal: laterals of the same shoe sit
    together, a lateral versus a front does not. 0.07 is the existing
    outsole hard-mismatch threshold, so a cooler extra lateral stays
    eligible and a missing-eyelet lateral still compares to the reference
    lateral that shows the eyelets.
    """
    if bool(ref_desc.label_hash) ^ bool(cand_desc.label_hash):
        return False
    if not footwear:
        return True
    return abs(ref_desc.outsole_ratio - cand_desc.outsole_ratio) < 0.07


def _construction_across_pairs(
    considered: list[
        tuple[tuple[float, float, float], StructuredDescriptor, StructuredDescriptor, bytes, bytes]
    ],
    *,
    chosen_ref: StructuredDescriptor,
    chosen_cand: StructuredDescriptor,
    chosen_geom: GeometryResult,
    footwear: bool,
) -> tuple[GeometryResult, list[str]]:
    """Worst construction contradiction among considered pairs, else the chosen pair.

    Identity may keep the flattering pair. A contradiction on any other
    considered pair is not erasable by that choice.
    """
    chosen_hard, _ = item_contradictions(
        reference=chosen_ref,
        candidate=chosen_cand,
        geometry=chosen_geom,
        exact_colour_required=False,
        colour_hard=False,
        label_hash_mismatch=False,
        apply_footwear_rules=footwear,
    )
    chosen_construction = [item for item in chosen_hard if item != "colourway-hard-mismatch"]
    worst_geom: GeometryResult | None = None
    found: list[str] = []
    for _rank, ref_desc, cand_desc, _ref_png, cand_png in considered:
        if not _construction_pair_eligible(ref_desc, cand_desc, footwear=footwear):
            continue
        geom = compare_geometry(ref_desc, cand_desc, apply_footwear_rules=footwear)
        # Same flip the chosen pair already tries. A mirrored true lateral
        # looks like a heel-cut / eyelet change until it is flipped back;
        # that is not a construction contradiction.
        flipped = _flipped_descriptor(cand_png, cand_desc.image_id)
        if flipped is not None:
            geom_flip = compare_geometry(ref_desc, flipped, apply_footwear_rules=footwear)
            if geom_flip.score > geom.score:
                geom = geom_flip
                cand_desc = flipped
        hard, _soft = item_contradictions(
            reference=ref_desc,
            candidate=cand_desc,
            geometry=geom,
            exact_colour_required=False,
            colour_hard=False,
            label_hash_mismatch=False,
            apply_footwear_rules=footwear,
        )
        # Soft view-to-view drift is not a construction change. A genuine
        # shoe's front versus its lateral can trip eyelet-count-soft and
        # would lower a true match. The hard count mismatches cannot: they
        # are the contradiction pairing erases by picking a front.
        construction = [item for item in hard if item != "colourway-hard-mismatch"]
        if not construction:
            continue
        if worst_geom is None or geom.score < worst_geom.score:
            worst_geom = geom
        for item in construction:
            if item not in found:
                found.append(item)
    if not found:
        return chosen_geom, chosen_construction
    merged = list(found)
    for item in chosen_construction:
        if item not in merged:
            merged.append(item)
    if worst_geom is not None and worst_geom.score < chosen_geom.score:
        return worst_geom, merged
    return chosen_geom, merged


def _best_correspondence(
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, bytes],
    *,
    ledger: CostLedger | None = None,
    max_pairs: int = 9,
) -> CorrespondenceResult:
    """The strongest surface match across the photographs, not the first pair.

    A user photographs the front; the seller's first image is a flat-lay and the
    third is the detail that overlaps it. Comparing only the first of each threw
    that evidence away, and correspondence went uncited on a candidate whose
    images matched at 35 inliers when the right pair was compared.

    One overlapping view is enough to place two photographs on the same object,
    so the best pair is the answer and the rest need not agree. Bounded because
    this is the expensive stage.
    """
    best: CorrespondenceResult | None = None
    pairs = 0
    for ref_png in reference_pngs.values():
        for cand_png in candidate_pngs.values():
            if pairs >= max_pairs:
                break
            pairs += 1
            found = correspond_pair(ref_png, cand_png, ledger=ledger)
            if best is None or found.inlier_count > best.inlier_count:
                best = found
        if pairs >= max_pairs:
            break
    if best is None:
        return CorrespondenceResult(
            inlier_ratio=0.0,
            match_count=0,
            inlier_count=0,
            method="none",
            mirrored=False,
            residual=0.0,
            notes=["no_image_pair"],
        )
    return best


def match_candidate(
    *,
    hypothesis: ItemHypothesis,
    candidate: EnrichedCandidate,
    reference_pngs: dict[str, bytes],
    reference_descriptors: dict[str, StructuredDescriptor],
    constraints: SearchConstraints | None = None,
    ledger: CostLedger | None = None,
) -> MatchEvidence:
    apply_category(candidate, hypothesis.category)
    ontology = ontology_for(hypothesis.category)
    footwear = ontology.category == "footwear"
    exact_colour = bool(constraints and constraints.colour)
    embedding_sim = pair_similarity(reference_pngs, candidate.pngs)
    considered = _capped_view_pairs(
        reference_pngs,
        candidate.pngs,
        reference_descriptors,
        candidate.descriptors,
        footwear=footwear,
    )
    if considered:
        _rank, ref_desc, cand_desc, ref_png, cand_png = max(considered, key=lambda item: item[0])
    else:
        ref_desc, cand_desc, ref_png, cand_png = None, None, None, None
    corr = (
        _best_correspondence(reference_pngs, candidate.pngs, ledger=ledger)
        if reference_pngs and candidate.pngs
        else CorrespondenceResult(
            inlier_ratio=0.0,
            match_count=0,
            inlier_count=0,
            method="none",
            mirrored=False,
            residual=0.0,
            notes=["no_image_pair"],
        )
    )
    corr_cite = cite("correspondence", f"{corr.method}:{corr.inlier_count}-inliers")

    text = _text_score(hypothesis, candidate.candidate, candidate.ocr_terms)
    if ref_desc and cand_desc and ref_png and cand_png:
        glob = _blend_embedding(
            global_visual(ref_desc, cand_desc, reference_png=ref_png, candidate_png=cand_png),
            embedding_sim,
        )
        geom_raw = compare_geometry(ref_desc, cand_desc, apply_footwear_rules=footwear)
        used_mirror = False
        flipped_desc = _flipped_descriptor(cand_png, cand_desc.image_id)
        if flipped_desc is not None:
            geom_flip = compare_geometry(ref_desc, flipped_desc, apply_footwear_rules=footwear)
            if geom_flip.score > geom_raw.score:
                geom_raw = geom_flip
                cand_desc = flipped_desc
                used_mirror = True
        colour_score, colour_contra = _colour_across_pairs(
            considered,
            exact_colour=exact_colour,
            chosen_ref=ref_desc,
            chosen_cand=cand_desc,
            footwear=footwear,
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
            apply_footwear_rules=footwear,
        )
        geom_raw, construction_hard = _construction_across_pairs(
            considered,
            chosen_ref=ref_desc,
            chosen_cand=cand_desc,
            chosen_geom=geom_raw,
            footwear=footwear,
        )
        for item in construction_hard:
            if item not in hard:
                hard.append(item)
        geometry = tight(
            geom_raw.score,
            support=[cite("geometry", note) for note in geom_raw.notes] or [cite("geometry", "ok")],
        )
        if footwear:
            part_records = []
            outsole_delta = 1 if "outsole" in " ".join(hard) else 0
            heel_delta = 1 if any("heel" in item for item in hard) else 0
            logo_delta = 1 if any("logo" in item for item in hard + soft) else 0
            for name, delta, ref_v, cand_v in (
                (
                    "eyelets",
                    geom_raw.eyelet_delta,
                    ref_desc.eyelet_count,
                    cand_desc.eyelet_count,
                ),
                (
                    "lateral_panels",
                    geom_raw.panel_delta,
                    ref_desc.panel_count,
                    cand_desc.panel_count,
                ),
                ("outsole", outsole_delta, ref_desc.outsole_ratio, cand_desc.outsole_ratio),
                ("heel", heel_delta, ref_desc.heel_cut, cand_desc.heel_cut),
                ("logo", logo_delta, ref_desc.logo_kind, cand_desc.logo_kind),
            ):
                step = float(delta if isinstance(delta, int) else 1)
                mean = 0.95 if delta == 0 else max(0.1, 0.55 - 0.2 * step)
                part_records.append(
                    make_part_match(name, mean, explanation=f"ref={ref_v} cand={cand_v}")
                )
        else:
            part_records = compare_extracted_parts(
                ontology=ontology,
                candidate_parts=candidate.parts,
                correspondence=corr,
                strong_inliers=CORRESPONDENCE_STRONG_INLIERS,
            )
        parts_mean = part_matches_mean(part_records)
        # Correspondence measures geometry rather than hinting at it. Keypoints
        # that survive a RANSAC homography are the same physical surface seen
        # twice, so a strong inlier count IS the geometric evidence and sets the
        # score instead of nudging it.
        #
        # The count, not the ratio, is what separates. Measured on
        # fixtures/user_snapshots: a photograph of an object against its own
        # listing gives a median of 35 inliers with a worst case of 14, while a
        # different listing gives a median of 0 and a best of 7. The old
        # ratio > 0.4 gate passed 2 inliers out of 4 matches and would have
        # failed 35 out of 100.
        if corr.inlier_count >= CORRESPONDENCE_STRONG_INLIERS:
            geometry = tight(
                max(geometry.interval.mean, 0.92),
                support=list(geometry.support) + [corr_cite],
            )
        elif corr.inlier_ratio > 0.4:
            geometry = tight(
                min(1.0, geometry.interval.mean + 0.04),
                support=list(geometry.support) + [cite("correspondence", corr.method)],
            )
        elif corr.method != "none":
            # Cite the measurement even when it is below the identity bar, so a
            # live result can show the inlier count instead of looking as if
            # correspondence never ran.
            geometry = tight(
                geometry.interval.mean,
                support=list(geometry.support) + [corr_cite],
            )
    else:
        cheap = compute_cheap_signals(
            candidate=candidate.candidate,
            hypothesis=hypothesis,
            reference_signature=hypothesis.visual_signature,
            reference_pngs=reference_pngs,
            candidate_pngs=candidate.pngs,
            candidate_ocr=candidate.ocr_terms,
            embedding_similarity=embedding_sim,
        )
        glob = _blend_embedding(
            scored(cheap.perceptual, spread=0.12, missing=["structure"]),
            embedding_sim,
        )
        geometry = scored(0.45, spread=0.2, missing=["geometry"])
        if corr.inlier_count >= CORRESPONDENCE_STRONG_INLIERS:
            geometry = tight(0.92, support=[corr_cite])
        elif corr.method != "none":
            geometry = scored(0.45, spread=0.2, missing=["geometry"], support=[corr_cite])
        material = scored(cheap.colour, spread=0.14)
        if footwear:
            part_records = []
            parts_mean = 0.4
        else:
            part_records = compare_extracted_parts(
                ontology=ontology,
                candidate_parts=candidate.parts,
                correspondence=corr,
                strong_inliers=CORRESPONDENCE_STRONG_INLIERS,
            )
            parts_mean = part_matches_mean(part_records)
        hard, soft = [], []
        colour_contra = []
        label_mismatch = False

    gallery = list(candidate.descriptors.values())
    cross_score, cross_hard, cross_missing = cross_view_consistency(
        gallery, apply_footwear_rules=footwear
    )
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
    expected_views = ontology.authenticity_critical_views or ontology.expected_views
    for expected in expected_views:
        if expected not in present and expected != "unknown":
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
    if corr.method != "none":
        support.append(corr_cite)
    if embedding_sim is not None and embedding_sim >= OPERATING_THRESHOLD:
        support.append(cite("embedding", "cosine"))
        support.append(cite("embedding", "OBSERVED-pixels"))
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
