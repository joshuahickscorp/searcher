"""§18.8 support / contradiction / missing explanations citing evidence IDs."""

from __future__ import annotations

from searcher.contracts.enums import Availability
from searcher.contracts.primitives import PublicExplanation
from searcher.core.time import UtcDateTime


def build_match_explanation(
    *,
    support: list[str],
    contradictions: list[str],
    missing: list[str],
    live: Availability | None,
    checked_at: UtcDateTime | None,
    compared: list[str],
    families: list[str],
    seller_fields: list[str],
) -> PublicExplanation:
    return PublicExplanation(
        support=support,
        contradictions=contradictions,
        missing_evidence=missing,
        live_status=live,
        last_checked_at=checked_at,
        compared_images=compared,
        duplicate_image_families=families,
        seller_reported_fields=seller_fields,
    )


def cite(kind: str, name: str) -> str:
    return f"ev:{kind}:{name}"
