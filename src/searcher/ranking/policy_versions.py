"""Versioned bucket policy. Benchmarks recalibrate without a code change."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from searcher.core.policy import POLICY_VERSION, PossiblyRealGate, RealGate
from searcher.ranking.order import RankingWeights


@dataclass(frozen=True, slots=True)
class BucketPolicy:
    version: str
    real: RealGate
    possibly: PossiblyRealGate
    ranking: RankingWeights
    require_calibrated_for_real: bool
    dead_listing_is_hard_veto: bool


def _matching_v1() -> BucketPolicy:
    return BucketPolicy(
        version="matching-1",
        real=RealGate(
            policy_version="matching-1",
            item_match_lower_bound=0.90,
            authenticity_lower_bound=0.80,
            evidence_completeness=0.65,
        ),
        possibly=PossiblyRealGate(
            policy_version="matching-1",
            plausible_item_match_lower_bound=0.45,
        ),
        ranking=RankingWeights(),
        require_calibrated_for_real=True,
        dead_listing_is_hard_veto=True,
    )


def _provisional_v1() -> BucketPolicy:
    return BucketPolicy(
        version=POLICY_VERSION,
        real=RealGate(),
        possibly=PossiblyRealGate(),
        ranking=RankingWeights(),
        require_calibrated_for_real=False,
        dead_listing_is_hard_veto=False,
    )


_REGISTRY: dict[str, BucketPolicy] = {
    "matching-1": _matching_v1(),
    POLICY_VERSION: _provisional_v1(),
    "provisional-1": _provisional_v1(),
}


def load_policy(version: str | None = None, *, path: Path | None = None) -> BucketPolicy:
    if path is not None and path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BucketPolicy(
            version=str(raw["version"]),
            real=RealGate(
                policy_version=str(raw["version"]),
                item_match_lower_bound=float(raw["real"]["item_match_lower_bound"]),
                authenticity_lower_bound=float(raw["real"]["authenticity_lower_bound"]),
                evidence_completeness=float(raw["real"]["evidence_completeness"]),
            ),
            possibly=PossiblyRealGate(
                policy_version=str(raw["version"]),
                plausible_item_match_lower_bound=float(
                    raw["possibly"]["plausible_item_match_lower_bound"]
                ),
            ),
            ranking=RankingWeights(),
            require_calibrated_for_real=bool(raw.get("require_calibrated_for_real", True)),
            dead_listing_is_hard_veto=bool(raw.get("dead_listing_is_hard_veto", True)),
        )
    if version and version in _REGISTRY:
        return _REGISTRY[version]
    return _REGISTRY["matching-1"]


def register_policy(policy: BucketPolicy) -> None:
    _REGISTRY[policy.version] = policy


def available_versions() -> list[str]:
    return sorted(_REGISTRY)
