"""§13.1 query families. Bounded, one local token per translated query."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.contracts.enums import QueryType
from searcher.contracts.models import ItemHypothesis
from searcher.queries.languages import (
    CATEGORY,
    COLOUR,
    CONDITION,
    TranslationRecord,
    sources_for,
    translate_term,
    transliterate_brand,
)
from searcher.queries.source_specific import source_queries


@dataclass(frozen=True, slots=True)
class DraftQuery:
    text: str
    query_type: QueryType
    language: str
    round: int
    family: str
    sources: tuple[str, ...]
    cost: float
    novelty: float
    provisional: bool = False
    translation: TranslationRecord | None = None
    origin: tuple[str, ...] = ()


def _join(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def drafts_for_hypothesis(
    hyp: ItemHypothesis,
    *,
    demoted: set[str] | None = None,
    visual_terms: list[str] | None = None,
    product_codes: list[str] | None = None,
) -> list[DraftQuery]:
    demoted = {term.lower() for term in (demoted or set())}
    brand = hyp.brand.value
    model = hyp.model_name.value
    year = hyp.year.value
    colour = hyp.colourway.value
    designer = hyp.designer.value
    category = hyp.category
    aliases = [a.alias for a in hyp.aliases if a.belief.confidence >= 0.5]
    drafts: list[DraftQuery] = []

    def add(
        text: str,
        qtype: QueryType,
        language: str,
        round_no: int,
        family: str,
        *,
        cost: float,
        novelty: float,
        provisional: bool = False,
        translation: TranslationRecord | None = None,
    ) -> None:
        if not text or text.lower() in demoted:
            return
        if any(tok.lower() in demoted for tok in text.split()):
            return
        drafts.append(
            DraftQuery(
                text=text,
                query_type=qtype,
                language=language,
                round=round_no,
                family=family,
                sources=sources_for(language),
                cost=cost,
                novelty=novelty,
                provisional=provisional,
                translation=translation,
                origin=(hyp.hypothesis_id,),
            )
        )

    # Round 0 — exact name / user text
    if brand and model:
        add(_join(brand, model), QueryType.EXACT_NAME, "en", 0, "exact_name", cost=0.1, novelty=1.0)
        if year and year.isdigit():
            add(
                _join(brand, model, year),
                QueryType.EXACT_NAME,
                "en",
                0,
                "exact_name",
                cost=0.1,
                novelty=0.85,
            )
        if colour:
            add(
                _join(brand, model, colour),
                QueryType.EXACT_NAME,
                "en",
                0,
                "exact_name",
                cost=0.1,
                novelty=0.7,
            )
    elif brand:
        add(brand, QueryType.EXACT_NAME, "en", 0, "exact_name", cost=0.1, novelty=0.6)

    # Round 1 — aliases, season/designer, codes
    for alias in aliases[:3]:
        add(_join(brand, alias), QueryType.ALIAS, "en", 1, "alias", cost=0.12, novelty=0.7)
    if brand and designer:
        add(
            _join(brand, designer, year, category if category != "unknown" else None),
            QueryType.SEASON_DESIGNER,
            "en",
            1,
            "designer_season",
            cost=0.12,
            novelty=0.65,
        )
    for code in (product_codes or [])[:2]:
        add(
            _join(brand, code),
            QueryType.PRODUCT_CODE,
            "en",
            1,
            "product_code",
            cost=0.1,
            novelty=0.8,
        )
        add(f'"{code}"', QueryType.PRODUCT_CODE, "en", 1, "product_code", cost=0.1, novelty=0.75)

    # Round 2 — visual + translated
    for term in (visual_terms or [])[:3]:
        add(
            _join(brand, term, "trainer" if category == "footwear" else category),
            QueryType.VISUAL_ATTRIBUTE,
            "en",
            2,
            "visual",
            cost=0.2,
            novelty=0.55,
            provisional=True,
        )
    for language in ("ja", "ko", "zh", "fr", "it", "ru"):
        local_brand = transliterate_brand(brand or "", language)
        cat_key = category if category != "unknown" else "footwear"
        cat_rec = translate_term(cat_key, language, CATEGORY)
        used = translate_term("used", language, CONDITION)
        archive = translate_term("archive", language, CONDITION)
        colour_rec = translate_term(colour or "", language, COLOUR) if colour else None
        # Preserve Latin brand; add at most one local token.
        if brand:
            if used:
                add(
                    _join(brand, used.translated_term),
                    QueryType.TRANSLATED,
                    language,
                    2,
                    "multilingual",
                    cost=0.15,
                    novelty=0.7,
                    translation=used,
                )
            if archive:
                add(
                    _join(brand, archive.translated_term),
                    QueryType.TRANSLATED,
                    language,
                    2,
                    "multilingual",
                    cost=0.15,
                    novelty=0.65,
                    translation=archive,
                )
            if cat_rec:
                add(
                    _join(brand, cat_rec.translated_term),
                    QueryType.TRANSLATED,
                    language,
                    2,
                    "multilingual",
                    cost=0.15,
                    novelty=0.6,
                    translation=cat_rec,
                )
            if colour_rec:
                add(
                    _join(brand, colour_rec.translated_term),
                    QueryType.TRANSLATED,
                    language,
                    2,
                    "multilingual",
                    cost=0.15,
                    novelty=0.5,
                    translation=colour_rec,
                )
        if local_brand and local_brand != brand:
            add(
                _join(local_brand, used.translated_term if used else None),
                QueryType.TRANSLATED,
                language,
                2,
                "multilingual",
                cost=0.16,
                novelty=0.72,
                translation=TranslationRecord(
                    source_term=brand or "",
                    translated_term=local_brand,
                    language=language,
                    tool="searcher.queries.languages.transliterate_brand",
                    confidence=0.45,
                ),
            )

    # Round 3 — source-specific
    for language in ("en", "ja", "ko", "zh", "fr", "it", "ru"):
        used = translate_term("used", language, CONDITION)
        cat_key = "footwear" if category == "footwear" else category
        cat_rec = translate_term(cat_key, language, CATEGORY)
        for source, text, family in source_queries(
            language=language,
            brand=brand,
            model=model,
            local_condition=used.translated_term if used else None,
            local_category=cat_rec.translated_term if cat_rec else None,
        ):
            add(
                text,
                QueryType.SOURCE_SPECIFIC,
                language,
                3,
                family,
                cost=0.12,
                novelty=0.45,
            )
            _ = source

    # Round 4 — archival / sold
    for language, key in (("en", "sold"), ("ja", "sold"), ("fr", "sold")):
        sold = translate_term(key, language, CONDITION)
        vintage = translate_term("vintage", language, CONDITION)
        if brand and sold:
            add(
                _join(brand, model, sold.translated_term),
                QueryType.TRANSLATED,
                language,
                4,
                "archival",
                cost=0.14,
                novelty=0.4,
                translation=sold,
            )
        if brand and vintage:
            add(
                _join(brand, vintage.translated_term),
                QueryType.TRANSLATED,
                language,
                4,
                "archival",
                cost=0.14,
                novelty=0.38,
                translation=vintage,
            )

    # Round 4/5 — archival already above; negative-research never recommends listings
    if brand:
        add(
            _join(brand, model, "authentication"),
            QueryType.NEGATIVE_RESEARCH,
            "en",
            4,
            "negative_research",
            cost=0.14,
            novelty=0.5,
        )
        add(
            _join(brand, model, "replica differences"),
            QueryType.NEGATIVE_RESEARCH,
            "en",
            5,
            "negative_research",
            cost=0.18,
            novelty=0.45,
        )

    return drafts
