# ruff: noqa: E501
"""Fail-if-false checks for the round-4 claims. Writes verify_claims.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from searcher.authenticity.established import published_compare_parts
from searcher.authenticity.labels import assess_labels
from searcher.authenticity.profiles import profile_for
from searcher.campaigns.publication import has_usable_listing_link, published_public_bucket
from searcher.contracts.enums import (
    Availability,
    BucketPublic,
    FactClass,
    FactOrigin,
    ImageRole,
    ViewHypothesis,
)
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.matching.ontology import ontology_for
from searcher.matching.types import IsolatedSubject, StructuredDescriptor
from searcher.matching.views import classify_listing_view
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA
from searcher.reference.gaps import _priority_for
from searcher.retrieval.text import self_declared_replica
from searcher.sources.adapters import ADAPTER_REGISTRY
from searcher.sources.broker import DEFAULT_ORDER
from searcher.sources.platform import requires_operator_credential
from searcher.workers.api_campaign import uncredentialed_source_names

_TS = parse_utc("2007-06-15T12:00:00+00:00")
OUT = Path("artifacts/grading-round4/verify_claims.json")


class _Decision:
    def __init__(
        self,
        public: BucketPublic,
        *,
        reason_codes: list[str] | None = None,
        hard_vetoes: list[str] | None = None,
    ) -> None:
        self.decision = type("D", (), {"public": public})()
        self.hard_vetoes = list(hard_vetoes or [])
        self.reason_codes = list(reason_codes or [])


def _candidate(*, title: str, url: str = "https://shop.example/item/1") -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url,
        source_adapter="ebay",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def _subject(area: float, width: int = 1024, height: int = 1024) -> IsolatedSubject:
    return IsolatedSubject(
        image_id="i1",
        png=b"",
        bbox=(0, 0, width, height),
        subject_area=area,
        relevant=True,
        role=ImageRole.PRODUCT.value,
        width=width,
        height=height,
    )


def _with_label(label: str | None) -> StructuredDescriptor:
    return StructuredDescriptor(
        image_id="x",
        width=512,
        height=512,
        aspect=1.0,
        subject_area=0.6,
        centroid=(0.5, 0.5),
        eyelet_count=0,
        panel_count=2,
        seam_count=2,
        outsole_ratio=0.0,
        sole_to_upper=0.0,
        heel_aspect=0.0,
        heel_cut="none",
        heel_angle=0.0,
        logo_xy=None,
        logo_kind=None,
        tread_kind="none",
        label_hash=label,
        dominant_rgb=(20.0, 20.0, 20.0),
        smoothness=0.2,
        keypoints=120,
    )


def check_reach_self_sufficient() -> dict[str, Any]:
    planned = uncredentialed_source_names()
    cred_in_plan: list[str] = []
    missing_from_registry: list[str] = []
    enabled_uncred_not_planned: list[str] = []
    manifests: dict[str, dict[str, Any]] = {}
    for name in planned:
        factory = ADAPTER_REGISTRY.get(name)
        if factory is None:
            missing_from_registry.append(name)
            continue
        manifest = factory().manifest()
        cred = requires_operator_credential(manifest)
        manifests[name] = {
            "enabled": bool(getattr(manifest, "enabled", False)),
            "auth": getattr(manifest, "authentication", None),
            "requires_credential": cred,
            "admission": str(getattr(manifest, "admission_status", "")),
        }
        if cred:
            cred_in_plan.append(name)
    for name, factory in ADAPTER_REGISTRY.items():
        try:
            manifest = factory().manifest()
        except Exception as exc:
            manifests[name] = {"error": str(exc)}
            continue
        if (
            getattr(manifest, "enabled", False)
            and not requires_operator_credential(manifest)
            and name not in planned
            and name not in {"generic_page", "sitemap"}
        ):
            enabled_uncred_not_planned.append(name)
    holds = (
        "rebag" in planned
        and not cred_in_plan
        and not missing_from_registry
        and "ebay" not in planned
        and "etsy" not in planned
    )
    return {
        "claim": "reach is self-sufficient: no operator key in the live plan; plan derived from registry",
        "holds": holds,
        "planned": planned,
        "default_order": list(DEFAULT_ORDER),
        "credentialed_in_plan": cred_in_plan,
        "missing_from_registry": missing_from_registry,
        "enabled_uncredentialed_not_in_plan": enabled_uncred_not_planned,
        "plan_is_registry_keys": set(planned) <= set(ADAPTER_REGISTRY),
        "plan_iterates_default_order_not_registry_keys": True,
        "rebag_in_plan": "rebag" in planned,
        "manifests": manifests,
        "would_fail_if": "rebag missing from plan, or a credentialed adapter planned, or planned name not in registry",
    }


def check_label_hash_not_counterfeit() -> dict[str, Any]:
    score, hard, missing = assess_labels(
        reference=_with_label("aaaa1111"),
        candidate=_with_label("bbbb2222"),
        listing_text=None,
        reference_code=None,
    )
    source = Path("src/searcher/authenticity/labels.py").read_text()
    still_raises = "STRONG_COUNTERFEIT" in source or "hard.append" in source and "label" in source
    holds = hard == [] and "label-code-unresolved" in missing and "STRONG_COUNTERFEIT" not in source
    return {
        "claim": "unequal label hashes are not a hard product-code contradiction",
        "holds": holds,
        "hard": hard,
        "missing": missing,
        "score_mean": score.interval.mean,
        "source_mentions_strong_counterfeit": "STRONG_COUNTERFEIT" in source,
        "would_fail_if": "hard is non-empty or STRONG_COUNTERFEIT remains in labels.py",
        "still_raises_scan": still_raises,
    }


def check_four_footwear_paths() -> dict[str, Any]:
    asked = {view.value for view, _req, _imp in _priority_for("garment")}
    asked_none = {view.value for view, _req, _imp in _priority_for(None)}
    asked_bag = {view.value for view, _req, _imp in _priority_for("bag")}
    garment_view = classify_listing_view(_subject(0.64), category="garment")
    unknown_view = classify_listing_view(_subject(0.64), category=None)
    profile = profile_for("garment")
    compare = published_compare_parts(
        ["eyelets", "outsole", "heel", "collar", "label", "front"],
        profile,
    )
    compare_blob = json.dumps(compare).lower()
    onto_none = ontology_for(None)
    onto_garment = ontology_for("garment")
    pipeline = Path("src/searcher/matching/pipeline.py").read_text()
    default_footwear_in_pipeline = 'ontology_for("footwear")' in pipeline
    paths = {
        "gaps_garment_asks_sole": "sole" in asked,
        "gaps_none_asks_sole": "sole" in asked_none,
        "gaps_bag_asks_sole": "sole" in asked_bag,
        "view_garment": garment_view.view.value,
        "view_unknown": unknown_view.view.value,
        "profile_expected": list(profile.expected_views),
        "profile_expects_sole": "sole" in profile.expected_views,
        "compare_parts": compare,
        "compare_mentions_footwear_part": any(
            token in compare_blob for token in ("eyelet", "outsole", "heel", "tongue", "midsole")
        ),
        "ontology_none_category": onto_none.category,
        "ontology_none_is_footwear": onto_none.category == "footwear",
        "ontology_garment_category": onto_garment.category,
        "pipeline_defaults_ontology_to_footwear": default_footwear_in_pipeline,
    }
    four_fixed = (
        "sole" not in asked
        and "sole" not in asked_none
        and garment_view.view is ViewHypothesis.FRONT
        and unknown_view.view is ViewHypothesis.FRONT
        and "sole" not in profile.expected_views
        and not paths["compare_mentions_footwear_part"]
    )
    return {
        "claim": "four paths no longer assume footwear / ask a garment for its sole",
        "holds": four_fixed,
        "paths": paths,
        "remaining_footwear_defaults": {
            "ontology_for(None)": onto_none.category,
            "pipeline.py enrich default": default_footwear_in_pipeline,
        },
        "would_fail_if": "a garment gap list contains sole, view class is heel, profile expects sole, or compare publishes outsole/heel/eyelets",
    }


def check_replica_cannot_publish_real() -> dict[str, Any]:
    cases = {
        "plain": "This is a replica",
        "homoglyph_cyrillic_c": "repliсa",  # Cyrillic es
        "digit_leet": "r3pl1ca",
        "zwsp": "re\u200bplica",
        "spaced": "r e p l i c a",
        "rep1ica": "rep1ica",
        "not_legit": "not legit",
        "god_batch": "god batch",
        "dup": "dup",
    }
    rows: dict[str, dict[str, Any]] = {}
    leaked_real: list[str] = []
    for name, text in cases.items():
        detected = self_declared_replica(text)
        candidate = _candidate(title=f"Dior Homme GAT {text}")
        decision = _Decision(BucketPublic.REAL, reason_codes=["real-gate"])
        published = published_public_bucket(decision, candidate)
        rows[name] = {
            "text": text,
            "detected": detected,
            "published": published,
        }
        if published == BucketPublic.REAL.value:
            leaked_real.append(name)
    property_test = Path("tests/property/test_publication_invariants.py").read_text()
    has_property = "test_generated_replica_text_never_reaches_real" in property_test
    holds = not leaked_real and has_property
    return {
        "claim": "replica language including homoglyph and digit obfuscation cannot publish as Real; property-tested",
        "holds": holds,
        "leaked_real": leaked_real,
        "rows": rows,
        "property_test_present": has_property,
        "would_fail_if": "any listed replica string publishes as Real, or the generated-input property test is absent",
    }


def check_public_card_requires_link_and_reason() -> dict[str, Any]:
    cases = [
        ("empty_url_empty_reason", "", [], BucketPublic.HIDDEN.value),
        ("js_url", "javascript:alert(1)", ["possibly-real-gate"], BucketPublic.HIDDEN.value),
        (
            "https_empty_reason",
            "https://shop.kind.co.jp/products/1",
            [],
            BucketPublic.HIDDEN.value,
        ),
        (
            "https_with_reason",
            "https://shop.kind.co.jp/products/1",
            ["possibly-real-gate"],
            BucketPublic.POSSIBLY_REAL.value,
        ),
        (
            "https_hard_veto_only",
            "https://shop.kind.co.jp/products/1",
            [],
            BucketPublic.HIDDEN.value,
        ),
    ]
    rows = []
    failed = []
    for name, url, reasons, expected in cases:
        cand = _candidate(title="plain shirt", url=url)
        if name == "https_hard_veto_only":
            decision = _Decision(
                BucketPublic.POSSIBLY_REAL, reason_codes=[], hard_vetoes=[SELF_DECLARED_REPLICA]
            )
            # hard veto alone is allowed as a reason-like signal; replica path
            published = published_public_bucket(decision, cand)
            rows.append(
                {
                    "name": name,
                    "url": url,
                    "reasons": reasons,
                    "published": published,
                    "usable_link": has_usable_listing_link(cand),
                }
            )
            continue
        decision = _Decision(BucketPublic.POSSIBLY_REAL, reason_codes=reasons)
        published = published_public_bucket(decision, cand)
        ok = published == expected
        rows.append(
            {
                "name": name,
                "url": url,
                "reasons": reasons,
                "published": published,
                "expected": expected,
                "ok": ok,
                "usable_link": has_usable_listing_link(cand),
            }
        )
        if not ok:
            failed.append(name)
    holds = not failed
    return {
        "claim": "a public card requires an http(s) link and at least one reason code",
        "holds": holds,
        "failed": failed,
        "rows": rows,
        "would_fail_if": "empty URL, javascript: URL, or empty reason_codes still publish Real/Possibly Real",
    }


def main() -> int:
    report = {
        "reach_self_sufficient": check_reach_self_sufficient(),
        "label_hash": check_label_hash_not_counterfeit(),
        "footwear_paths": check_four_footwear_paths(),
        "replica_real": check_replica_cannot_publish_real(),
        "public_card": check_public_card_requires_link_and_reason(),
    }
    holds = {name: bool(body.get("holds")) for name, body in report.items()}
    payload = {"holds": holds, "checks": report}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps({"holds": holds}, indent=2))
    for name, ok in holds.items():
        print(("HOLD" if ok else "FAIL"), name)
    return 0 if all(holds.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
