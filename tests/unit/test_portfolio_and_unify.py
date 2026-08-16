"""Portfolio construction and reference-set unification."""

from __future__ import annotations

from searcher.contracts.models import (
    CategoryHypothesis,
    LaneStatus,
    ReferenceAnalysis,
    TargetCluster,
)
from searcher.core.ids import new_id
from searcher.hypotheses.item import parse_user_text, seed_portfolio
from searcher.reference.unify import unify_references


def test_parse_user_text_is_generic() -> None:
    parsed = parse_user_text("House Name Field Model 07", ["black", "leather"])
    assert parsed.year == "2007"
    assert "black" in parsed.colours
    assert "leather" in parsed.materials
    assert parsed.brand_tokens
    assert parsed.model_tokens


def test_flagship_style_input_yields_competing_identities() -> None:
    analysis = ReferenceAnalysis(
        analysis_id=new_id(),
        search_id="s",
        primary_cluster=TargetCluster(cluster_id=new_id(), confidence=0.5),
        category_hypotheses=[CategoryHypothesis(category="footwear", confidence=0.4)],
        lanes=[LaneStatus(name="DENSE_FEATURES", available=False, blocked=True)],
        promotion_blocked=True,
    )
    hyps = seed_portfolio(
        search_id="s",
        text="Dior Homme General Army Trainer 07",
        tags=["Hedi Slimane", "2007", "black", "low-top"],
        analysis=analysis,
    )
    assert len(hyps) >= 2
    classes = {h.brand.fact_class.value for h in hyps}
    classes |= {h.model_name.fact_class.value for h in hyps}
    assert "USER_SUPPLIED" in classes
    # No hypothesis is asserted as OBSERVED from user text.
    assert all(h.brand.fact_class.value != "OBSERVED" for h in hyps)


def test_unify_builds_alternate_clusters() -> None:
    ids = ["a", "b", "c"]
    hashes = {
        "a": "0" * 16,
        "b": "0" * 15 + "1",
        "c": "f" * 16,
    }
    hist = {
        "a": [1.0] + [0.0] * 7,
        "b": [0.95] + [0.0] * 7,
        "c": [0.0] * 7 + [1.0],
    }
    primary, alts = unify_references(ids, hashes, hist)
    assert primary.image_ids
    assert alts
    assert primary.role == "primary"
    assert alts[0].role == "alternate"
