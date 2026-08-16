"""Parse user text into beliefs and seed a bounded hypothesis portfolio."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from searcher.contracts.enums import FactClass, FactOrigin, HypothesisStatus
from searcher.contracts.models import (
    ItemHypothesis,
    ReferenceAnalysis,
    TextObservation,
    VisualSignature,
)
from searcher.core.ids import new_id
from searcher.hypotheses.beliefs import empty_belief, make_belief
from searcher.reference.vocab import category_of, is_colour, is_material

_YEAR_FULL = re.compile(r"\b((?:19|20)\d{2})\b")
_YEAR_SHORT = re.compile(r"\b((?:0[0-9]|1[0-9]|2[0-6]))\b")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'./-]*")


@dataclass
class ParsedUserText:
    raw: str
    brand_tokens: list[str] = field(default_factory=list)
    model_tokens: list[str] = field(default_factory=list)
    year: str | None = None
    years_alt: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    category: str | None = None
    designer_tokens: list[str] = field(default_factory=list)
    leftover: list[str] = field(default_factory=list)


def parse_user_text(text: str | None, tags: list[str] | None = None) -> ParsedUserText:
    raw = " ".join(part for part in [text or "", *(tags or [])] if part).strip()
    parsed = ParsedUserText(raw=raw)
    if not raw:
        return parsed
    year_full = _YEAR_FULL.search(raw)
    if year_full:
        parsed.year = year_full.group(1)
    else:
        short = _YEAR_SHORT.search(raw)
        if short:
            century = "20" if int(short.group(1)) <= 30 else "19"
            parsed.year = century + short.group(1)
    if parsed.year:
        y = int(parsed.year)
        parsed.years_alt = [str(y - 1), str(y + 1)]
    tokens = _TOKEN.findall(raw)
    unused: list[str] = []
    for token in tokens:
        lower = token.lower()
        if parsed.year and (token == parsed.year or token == parsed.year[2:]):
            continue
        cat = category_of(token)
        if cat:
            parsed.category = parsed.category or cat
            continue
        if is_colour(token):
            parsed.colours.append(lower)
            continue
        if is_material(token):
            parsed.materials.append(lower)
            continue
        if lower in {"low-top", "high-top", "lowtop", "hightop"}:
            continue
        unused.append(token)
    # First 1–2 capitalized / unknown tokens are a brand hypothesis; rest is model.
    if unused:
        if len(unused) == 1:
            parsed.brand_tokens = unused[:1]
        else:
            parsed.brand_tokens = unused[:2]
            parsed.model_tokens = unused[2:]
            if not parsed.model_tokens and len(unused) >= 2:
                parsed.brand_tokens = unused[:1]
                parsed.model_tokens = unused[1:]
    parsed.leftover = unused
    return parsed


def _ocr_values(ocr: list[TextObservation], kind: str) -> list[str]:
    return [item.text for item in ocr if item.kind == kind and not item.injection_candidate]


def _hypothesis(
    search_id: str,
    *,
    category: str,
    brand: str | None,
    brand_class: FactClass,
    brand_origin: FactOrigin,
    model: str | None,
    model_class: FactClass,
    model_origin: FactOrigin,
    year: str | None,
    year_class: FactClass,
    year_origin: FactOrigin,
    colour: str | None,
    designer: str | None,
    materials: list[str],
    posterior: float,
    signature: VisualSignature,
    status: HypothesisStatus = HypothesisStatus.ACTIVE,
    notes_as_uncertainties: list[str] | None = None,
) -> ItemHypothesis:
    from searcher.contracts.models import Uncertainty

    return ItemHypothesis(
        hypothesis_id=new_id(),
        search_id=search_id,
        status=status,
        category=category,
        brand=make_belief(
            brand, confidence=0.55 if brand else 0.1, fact_class=brand_class, origin=brand_origin
        )
        if brand
        else empty_belief(),
        model_name=make_belief(
            model, confidence=0.5 if model else 0.1, fact_class=model_class, origin=model_origin
        )
        if model
        else empty_belief(),
        line=empty_belief(),
        designer=make_belief(
            designer,
            confidence=0.4,
            fact_class=FactClass.USER_SUPPLIED,
            origin=FactOrigin.USER,
        )
        if designer
        else empty_belief(),
        season=empty_belief(),
        year=make_belief(year, confidence=0.45, fact_class=year_class, origin=year_origin)
        if year
        else empty_belief(),
        colourway=make_belief(
            colour,
            confidence=0.4,
            fact_class=FactClass.USER_SUPPLIED if colour else FactClass.UNRESOLVED,
            origin=FactOrigin.USER if colour else FactOrigin.SYSTEM,
        )
        if colour
        else empty_belief(),
        materials=[
            make_belief(
                m, confidence=0.35, fact_class=FactClass.USER_SUPPLIED, origin=FactOrigin.USER
            )
            for m in materials
        ],
        visual_signature=signature,
        posterior=posterior,
        uncertainties=[
            Uncertainty(question=note, impact="identity remains open")
            for note in (notes_as_uncertainties or [])
        ],
    )


def seed_portfolio(
    *,
    search_id: str,
    text: str | None,
    tags: list[str],
    analysis: ReferenceAnalysis,
    ceiling: int = 8,
) -> list[ItemHypothesis]:
    parsed = parse_user_text(text, tags)
    ocr = analysis.text_and_marks
    signature = analysis.visual_signature
    category = parsed.category or (
        analysis.category_hypotheses[0].category if analysis.category_hypotheses else "unknown"
    )
    brand = " ".join(parsed.brand_tokens) or None
    model = " ".join(parsed.model_tokens) or None
    colour = parsed.colours[0] if parsed.colours else None
    ocr_brands = _ocr_values(ocr, "brand")
    ocr_years = [t for t in _ocr_values(ocr, "season") if re.fullmatch(r"(?:19|20)\d{2}", t)]
    portfolio: list[ItemHypothesis] = []

    if parsed.raw:
        portfolio.append(
            _hypothesis(
                search_id,
                category=category,
                brand=brand,
                brand_class=FactClass.USER_SUPPLIED,
                brand_origin=FactOrigin.USER,
                model=model,
                model_class=FactClass.USER_SUPPLIED,
                model_origin=FactOrigin.USER,
                year=parsed.year,
                year_class=FactClass.USER_SUPPLIED,
                year_origin=FactOrigin.USER,
                colour=colour,
                designer=" ".join(parsed.designer_tokens) or None,
                materials=parsed.materials,
                posterior=0.38,
                signature=signature,
                notes_as_uncertainties=["user text is a hypothesis, not authority"],
            )
        )
        if model:
            portfolio.append(
                _hypothesis(
                    search_id,
                    category=category,
                    brand=brand,
                    brand_class=FactClass.USER_SUPPLIED,
                    brand_origin=FactOrigin.USER,
                    model=model,
                    model_class=FactClass.INFERRED,
                    model_origin=FactOrigin.INFERENCE,
                    year=parsed.year,
                    year_class=FactClass.USER_SUPPLIED,
                    year_origin=FactOrigin.USER,
                    colour=colour,
                    designer=None,
                    materials=parsed.materials,
                    posterior=0.18,
                    signature=signature,
                    notes_as_uncertainties=[
                        "typed name may be a resale nickname rather than an official model"
                    ],
                )
            )
        if parsed.year and parsed.years_alt:
            portfolio.append(
                _hypothesis(
                    search_id,
                    category=category,
                    brand=brand,
                    brand_class=FactClass.USER_SUPPLIED,
                    brand_origin=FactOrigin.USER,
                    model=model,
                    model_class=FactClass.USER_SUPPLIED if model else FactClass.INFERRED,
                    model_origin=FactOrigin.USER if model else FactOrigin.INFERENCE,
                    year=f"{parsed.years_alt[0]}-{parsed.years_alt[1]}",
                    year_class=FactClass.INFERRED,
                    year_origin=FactOrigin.INFERENCE,
                    colour=colour,
                    designer=None,
                    materials=parsed.materials,
                    posterior=0.16,
                    signature=signature,
                    notes_as_uncertainties=["adjacent year remains open"],
                )
            )

    visual_brand = ocr_brands[0] if ocr_brands else None
    visual_year = ocr_years[0] if ocr_years else None
    portfolio.append(
        _hypothesis(
            search_id,
            category=category,
            brand=visual_brand,
            brand_class=FactClass.EXTRACTED if visual_brand else FactClass.INFERRED,
            brand_origin=FactOrigin.EXTRACTOR if visual_brand else FactOrigin.INFERENCE,
            model=None,
            model_class=FactClass.INFERRED,
            model_origin=FactOrigin.INFERENCE,
            year=visual_year,
            year_class=FactClass.EXTRACTED if visual_year else FactClass.UNRESOLVED,
            year_origin=FactOrigin.EXTRACTOR if visual_year else FactOrigin.SYSTEM,
            colour=None,
            designer=None,
            materials=[],
            posterior=0.14,
            signature=signature,
            notes_as_uncertainties=["visual-only identity; typed name not used as authority"],
        )
    )

    if brand and visual_brand and visual_brand.lower() not in brand.lower():
        portfolio.append(
            _hypothesis(
                search_id,
                category=category,
                brand=visual_brand,
                brand_class=FactClass.EXTRACTED,
                brand_origin=FactOrigin.EXTRACTOR,
                model=None,
                model_class=FactClass.INFERRED,
                model_origin=FactOrigin.INFERENCE,
                year=visual_year,
                year_class=FactClass.EXTRACTED if visual_year else FactClass.UNRESOLVED,
                year_origin=FactOrigin.EXTRACTOR if visual_year else FactOrigin.SYSTEM,
                colour=colour,
                designer=None,
                materials=[],
                posterior=0.12,
                signature=signature,
                notes_as_uncertainties=["OCR brand conflicts with typed brand"],
            )
        )

    if analysis.alternate_clusters:
        portfolio.append(
            _hypothesis(
                search_id,
                category=category,
                brand=brand,
                brand_class=FactClass.INFERRED,
                brand_origin=FactOrigin.INFERENCE,
                model=None,
                model_class=FactClass.INFERRED,
                model_origin=FactOrigin.INFERENCE,
                year=parsed.year,
                year_class=FactClass.USER_SUPPLIED if parsed.year else FactClass.UNRESOLVED,
                year_origin=FactOrigin.USER if parsed.year else FactOrigin.SYSTEM,
                colour=None,
                designer=None,
                materials=[],
                posterior=0.08,
                signature=signature,
                notes_as_uncertainties=["alternate target cluster in the reference set"],
            )
        )

    # Always at least two identities when any signal exists.
    if len(portfolio) < 2:
        portfolio.append(
            _hypothesis(
                search_id,
                category="unknown",
                brand=None,
                brand_class=FactClass.UNRESOLVED,
                brand_origin=FactOrigin.SYSTEM,
                model=None,
                model_class=FactClass.UNRESOLVED,
                model_origin=FactOrigin.SYSTEM,
                year=None,
                year_class=FactClass.UNRESOLVED,
                year_origin=FactOrigin.SYSTEM,
                colour=None,
                designer=None,
                materials=[],
                posterior=0.1,
                signature=signature,
                notes_as_uncertainties=["competing unknown identity"],
            )
        )

    # Normalize posteriors and bind crop-level aliases from user tags only as provisional.
    total = sum(h.posterior for h in portfolio) or 1.0
    bounded: list[ItemHypothesis] = []
    for hyp in portfolio[:ceiling]:
        bounded.append(
            hyp.model_copy(
                update={
                    "posterior": round(hyp.posterior / total, 4),
                    "aliases": [],
                    "supporting_evidence": [analysis.analysis_id],
                }
            )
        )
    return bounded
