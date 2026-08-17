"""Round-2 attacks. Fail if a replica reaches Real, COMPLETE needs no work,
a dummy capability is available, or a result publishes without a reason or link.

Writes artifacts/grading-round2/attacks.json. Does not change src/.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from searcher.api.views import list_public_results, project_result
from searcher.campaigns.controller import CampaignController
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.campaigns.publication import published_public_bucket
from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    FactClass,
    FactOrigin,
)
from searcher.contracts.models import (
    AuthenticityEvidence,
    BucketDecision,
    BucketDecisionFields,
    IntentBudget,
    ListingCandidate,
    MatchEvidence,
    PrivacySettings,
    SearchConstraints,
    SearchIntent,
)
from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence, classified
from searcher.core.capabilities import CapabilityName
from searcher.core.config import Settings
from searcher.core.embedding_gateway import (
    clear_embedding_probe_cache,
    embedding_capability,
    find_local_weights,
)
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.evidence.content_store import ContentStore
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.utility import listing_utility
from searcher.retrieval.text import self_declared_replica
from searcher.core.budgets import Budget
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


def make_intent(search_id: str | None = None) -> SearchIntent:
    return SearchIntent(
        search_id=search_id or new_id(),
        created_at=_TS,
        text="Dior Homme General Army Trainer 07",
        tags=["dior"],
        constraints=SearchConstraints(brand="Dior Homme"),
        budget=IntentBudget(
            wall_seconds=60,
            source_limit=4,
            page_limit=20,
            browser_page_limit=0,
            image_limit=10,
            model_call_limit=0,
            byte_limit=1_000_000,
            monetary_limit=None,
        ),
        privacy=PrivacySettings(),
    )


def make_budget() -> Budget:
    return Budget.fixture_default()

_TS = parse_utc("2007-06-15T12:00:00+00:00")
OUT = Path("artifacts/grading-round2/attacks.json")

# The thirteen phrases that published as Real in round 1.
LEAKED = [
    "This is fake.",
    "スーパーコピー レプリカ",
    "Dior Homme GAT dupe",
    "Inspired by Dior Homme General Army Trainer",
    "Dior Homme GAT superfake",
    "Dior Homme GAT PK God factory",
    "Dior Homme GAT UA batch",
    "Dior Homme GAT 1：1",
    "not genuine",
    "Dior Homme GAT mirror batch",
    "Dior Homme GAT homage",
    "repsneaker quality",
    "Unauthorized replica 1:1 of the original trainer",
]

# Extra phrasings a seller would actually use. Not in the regression list.
EXTRA = [
    "1st copy",
    "first copy",
    "super copy",
    "super-copy",
    "AAA+",
    "aaa quality",
    "god factory",
    "not the authentic piece",
    "isn't authentic",
    "ain't genuine",
    "not the real thing",
    "this is a rep",
    "replika",
    "réplique",
    "imitazione",
    "imitation",
    "unauthorised replica",
    "not original item",
    "re\u200bplica",  # zero-width joiner
    "r e p l i c a",
    "1/1 pair",
    "1-1 quality",
    "one to one",
    "same as retail",
    "best batch",
    "repfam",
    "high quality copy",
    "mirror",  # without quality/batch
    "from the factory",
    "not orig",
    "this isn't the authentic pair",
    "counter feit",
    "super  copy",
    "UA quality",
    "PK factory",
]

SHOULD_STAY_CLEAN = [
    "Dior Homme General Army Trainer",
    "Black wool coat with faux fur collar",
    "Vintage fake leather jacket",
    "Authentic Prada pumps size 38 1/2",
    "WILLY CHAVARRIA 無地 ロングスリーブカットソー",
]


def _score(mean: float = 0.92) -> ScoreWithEvidence:
    return ScoreWithEvidence(
        interval=ScoreInterval(mean=mean, lower_bound=mean - 0.04, upper_bound=mean + 0.04)
    )


def _candidate(*, title: str, description: str = "", adapter: str = "ebay", url: str | None = None) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url or f"https://{adapter}.example/item/{new_id()[:8]}",
        source_adapter=adapter,
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(description, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER)
        if description
        else None,
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def _perfect_match(cid: str) -> MatchEvidence:
    interval = ScoreInterval(mean=0.92, lower_bound=0.88, upper_bound=0.96)
    return MatchEvidence(
        match_evidence_id=new_id(),
        candidate_id=cid,
        hypothesis_id="h",
        global_visual=_score(),
        text_identity=_score(),
        geometry=_score(),
        material=_score(),
        colourway=_score(),
        cross_image_consistency=_score(),
        metadata_consistency=_score(),
        item_match_distribution=interval,
    )


def _perfect_auth(cid: str) -> AuthenticityEvidence:
    interval = ScoreInterval(mean=0.92, lower_bound=0.88, upper_bound=0.96)
    return AuthenticityEvidence(
        authenticity_evidence_id=new_id(),
        candidate_id=cid,
        reference_class="designer_footwear",
        construction_consistency=_score(),
        label_and_code_consistency=_score(),
        logo_and_hardware_consistency=_score(),
        material_consistency=_score(),
        photo_set_consistency=_score(),
        image_originality=_score(),
        source_and_seller_signal=_score(),
        provenance_signal=_score(),
        price_anomaly=_score(),
        authenticity_distribution=interval,
        authority_ceiling="fixture-calibrated:fixture-v1",
    )


def _route(candidate: ListingCandidate) -> BucketDecision:
    return route_candidate(
        candidate=candidate,
        match=_perfect_match(candidate.candidate_id),
        authenticity=_perfect_auth(candidate.candidate_id),
        utility=listing_utility(candidate, destination_verified=True),
        completeness_value=0.8,
        destination_verified=True,
        policy=load_policy("matching-1"),
    )


def _controller(root: Path) -> CampaignController:
    settings = Settings.from_env(data_root=root)
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    return CampaignController(database, store, settings)


def attack_replica() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    reached_real: list[str] = []
    reached_possible: list[str] = []
    for text in LEAKED + EXTRA:
        detected = self_declared_replica(text)
        candidate = _candidate(title=text)
        decision = _route(candidate)
        public = published_public_bucket(decision, candidate)
        row = {
            "text": text,
            "in_regression_list": text in LEAKED,
            "detected": detected,
            "routed_public": decision.decision.public.value,
            "published": public,
        }
        rows.append(row)
        if public == BucketPublic.REAL.value:
            reached_real.append(text)
        if public == BucketPublic.POSSIBLY_REAL.value:
            reached_possible.append(text)

    family = _candidate(title="Dior Homme General Army Trainer", adapter="yupoo")
    family_pub = published_public_bucket(
        BucketDecision(
            candidate_id=family.candidate_id,
            decision=BucketDecisionFields(
                internal=BucketInternal.REAL, public=BucketPublic.REAL
            ),
            policy_version="matching-1",
            item_match_lower_bound=0.95,
            authenticity_lower_bound=0.90,
            evidence_completeness=0.80,
            reason_codes=["real-gate"],
        ),
        family,
    )

    clean_false_pos: list[str] = []
    for text in SHOULD_STAY_CLEAN:
        if self_declared_replica(text):
            clean_false_pos.append(text)

    return {
        "attack": "publish a replica to Real",
        "leaked_regression": len(LEAKED),
        "extra_phrasings": len(EXTRA),
        "reached_real": reached_real,
        "reached_possibly_real": reached_possible,
        "replica_family_with_real_decision_published_as": family_pub,
        "clean_listings_flagged": clean_false_pos,
        "rows": rows,
        "outcome": (
            "BLOCKED"
            if not reached_real and family_pub != BucketPublic.REAL.value
            else "LEAK"
        ),
    }


def attack_complete_without_fetch() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        controller = _controller(Path(tmp))
        orch = CampaignOrchestrator(controller)

        intent = make_intent()
        controller.create(intent, budget=make_budget())
        state, reason, sat = orch._choose_terminal(intent.search_id, forced=None)
        findings.append(
            {
                "case": "empty campaign, no queries, no coverage",
                "state": state.value,
                "reason": reason,
                "saturation": sat,
                "complete": state.value == "COMPLETE",
            }
        )

        intent2 = make_intent()
        controller.create(intent2, budget=make_budget())
        from searcher.contracts.enums import QueryType
        from searcher.contracts.models import QueryVariant

        controller.repos.upsert_query(
            intent2.search_id,
            QueryVariant(
                query_id=new_id(),
                hypothesis_id=new_id(),
                round=1,
                language="en",
                query_text="Archive Alpha Trainer",
                query_type=QueryType.EXACT_NAME,
            ),
        )
        # Queries exist, but no completed/blocked sources and no fetches.
        state2, reason2, sat2 = orch._choose_terminal(intent2.search_id, forced=None)
        findings.append(
            {
                "case": "query compiled, no source work planned",
                "state": state2.value,
                "reason": reason2,
                "saturation": sat2,
                "complete": state2.value == "COMPLETE",
            }
        )

        intent3 = make_intent()
        controller.create(intent3, budget=make_budget())
        controller.repos.upsert_query(
            intent3.search_id,
            QueryVariant(
                query_id=new_id(),
                hypothesis_id=new_id(),
                round=1,
                language="en",
                query_text="Archive Alpha Trainer",
                query_type=QueryType.EXACT_NAME,
            ),
        )
        # Claimed completed source, but pages_fetched=0 and no candidates.
        controller.set_runtime(
            intent3.search_id,
            coverage={
                "sources_completed": [
                    {"id": "kind", "name": "kind", "status": "SEARCHED_MATCHES_FOUND", "detail": ""}
                ],
                "sources_blocked": [],
                "pages_fetched": 0,
                "candidates_normalized": 0,
                "candidates_hidden": 0,
            },
        )
        state3, reason3, sat3 = orch._choose_terminal(intent3.search_id, forced=None)
        findings.append(
            {
                "case": "source marked completed, pages_fetched=0, no candidates",
                "state": state3.value,
                "reason": reason3,
                "saturation": sat3,
                "complete": state3.value == "COMPLETE",
            }
        )

        intent4 = make_intent()
        controller.create(intent4, budget=make_budget())
        from searcher.contracts.enums import CampaignState

        state4, reason4, sat4 = orch._choose_terminal(
            intent4.search_id, forced=CampaignState.COMPLETE
        )
        findings.append(
            {
                "case": "forced COMPLETE with no work",
                "state": state4.value,
                "reason": reason4,
                "saturation": sat4,
                "complete": state4.value == "COMPLETE",
                "note": "forced=COMPLETE is an internal override used for saturation/tests",
            }
        )

    leaked = [f for f in findings if f["complete"] and "forced" not in f["case"]]
    return {
        "attack": "reach COMPLETE without fetching",
        "findings": findings,
        "unforced_complete_without_work": leaked,
        "outcome": "LEAK" if leaked else "BLOCKED",
    }


def attack_capability_lie() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        dummy = Path(tmp) / "dummy.pt"
        dummy.write_bytes(b"garbage!")
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(dummy)
        os.environ.pop("SEARCHER_DATA_ROOT", None)
        clear_embedding_probe_cache()

        unprobed = embedding_capability()
        findings.append(
            {
                "case": "dummy file, no probe",
                "path_found": str(find_local_weights()),
                "available": unprobed.available,
                "notes": unprobed.notes,
                "lied": unprobed.available is True,
            }
        )
        probed = embedding_capability(probe=True)
        findings.append(
            {
                "case": "dummy file, probe=True",
                "available": probed.available,
                "notes": probed.notes,
                "lied": probed.available is True,
            }
        )

        empty = Path(tmp) / "empty.pt"
        empty.write_bytes(b"")
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(empty)
        clear_embedding_probe_cache()
        empty_rec = embedding_capability(probe=True)
        findings.append(
            {
                "case": "zero-byte file, probe=True",
                "path_found": str(find_local_weights()),
                "available": empty_rec.available,
                "notes": empty_rec.notes,
                "lied": empty_rec.available is True,
            }
        )

        missing = Path(tmp) / "no-such.pt"
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(missing)
        clear_embedding_probe_cache()
        miss = embedding_capability(probe=True)
        findings.append(
            {
                "case": "missing path, probe=True",
                "path_found": str(find_local_weights()),
                "available": miss.available,
                "notes": miss.notes,
                "lied": miss.available is True,
            }
        )

        # Poison the cache: record a successful probe against garbage.
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(dummy)
        clear_embedding_probe_cache()
        from searcher.core.embedding_gateway import record_probe_result

        record_probe_result(dummy, True)
        poisoned = embedding_capability()
        findings.append(
            {
                "case": "dummy file after record_probe_result(True)",
                "available": poisoned.available,
                "notes": poisoned.notes,
                "lied": poisoned.available is True,
                "note": "internal cache write, not a public API",
            }
        )

        from searcher.integrations.visionmcp.probe import probe_capabilities

        clear_embedding_probe_cache()
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(dummy)
        report = probe_capabilities()
        dense = [r for r in report.capabilities if r.name is CapabilityName.DENSE_FEATURES]
        next_view = [r for r in report.capabilities if r.name.value == "NEXT_VIEW"]
        findings.append(
            {
                "case": "probe_capabilities() with dummy weights (GET /v1/capabilities path)",
                "dense_available": dense[0].available if dense else None,
                "dense_notes": dense[0].notes if dense else None,
                "next_view_available": next_view[0].available if next_view else None,
                "next_view_notes": next_view[0].notes if next_view else None,
                "lied": bool(dense and dense[0].available is True),
            }
        )

    leaked = [f for f in findings if f.get("lied") and "record_probe_result" not in f["case"]]
    return {
        "attack": "make a capability lie",
        "findings": findings,
        "public_lies": leaked,
        "outcome": "LEAK" if leaked else "BLOCKED",
    }


def attack_publish_without_reason_or_link() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        controller = _controller(Path(tmp))
        intent = make_intent()
        controller.create(intent, budget=make_budget())

        # Decision claiming Possibly Real, empty reason_codes, empty URL.
        bare = ListingCandidate(
            candidate_id=new_id(),
            canonical_url="",
            source_adapter="kind",
            title=classified("Plain tee", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
            availability=Availability.LIVE,
            first_seen_at=_TS,
            last_checked_at=_TS,
        )
        decision = BucketDecision(
            candidate_id=bare.candidate_id,
            decision=BucketDecisionFields(
                internal=BucketInternal.POSSIBLY_REAL,
                public=BucketPublic.POSSIBLY_REAL,
            ),
            policy_version="matching-1",
            item_match_lower_bound=0.6,
            authenticity_lower_bound=0.5,
            evidence_completeness=0.4,
            hard_vetoes=[],
            reason_codes=[],
        )
        controller.repos.upsert_candidate(intent.search_id, bare)
        controller.repos.insert_decision(intent.search_id, new_id(), decision)
        CampaignOrchestrator(controller)._publish(intent.search_id)
        body = list_public_results(controller, intent.search_id, None)
        published = body.get("possibly_real") or []
        first = published[0] if published else None
        findings.append(
            {
                "case": "empty canonical_url + empty reason_codes",
                "published_count": len(published),
                "listing_url": None if first is None else first.get("listing_url"),
                "tab_reason": None if first is None else (first.get("why") or {}).get("tab_reason"),
                "reason_codes_in_why": (
                    None
                    if first is None
                    else "Reason codes:" in str((first.get("why") or {}).get("tab_reason"))
                ),
                "published_without_link": bool(published) and not (first or {}).get("listing_url"),
                "published_without_reason_codes": bool(published)
                and "Reason codes:"
                not in str((first or {}).get("why", {}).get("tab_reason")),
            }
        )

        # javascript: URL
        intent2 = make_intent()
        controller.create(intent2, budget=make_budget())
        evil = _candidate(
            title="Archive Alpha Trainer",
            url="javascript:alert(1)",
            adapter="kind",
        )
        decision2 = BucketDecision(
            candidate_id=evil.candidate_id,
            decision=BucketDecisionFields(
                internal=BucketInternal.POSSIBLY_REAL,
                public=BucketPublic.POSSIBLY_REAL,
            ),
            policy_version="matching-1",
            item_match_lower_bound=0.6,
            authenticity_lower_bound=0.5,
            evidence_completeness=0.4,
            reason_codes=["possibly-real-gate"],
        )
        controller.repos.upsert_candidate(intent2.search_id, evil)
        controller.repos.insert_decision(intent2.search_id, new_id(), decision2)
        CampaignOrchestrator(controller)._publish(intent2.search_id)
        body2 = list_public_results(controller, intent2.search_id, None)
        pub2 = body2.get("possibly_real") or []
        first2 = pub2[0] if pub2 else None
        findings.append(
            {
                "case": "javascript: URL stored as canonical_url",
                "published_count": len(pub2),
                "listing_url": None if first2 is None else first2.get("listing_url"),
                "published_without_link": bool(pub2) and not (first2 or {}).get("listing_url"),
                "tab_reason": None if first2 is None else (first2.get("why") or {}).get("tab_reason"),
            }
        )

        # Honest path: real URL + reason codes via route_candidate
        intent3 = make_intent()
        controller.create(intent3, budget=make_budget())
        honest = _candidate(title="Archive Alpha Trainer", adapter="kind")
        routed = _route(honest)
        controller.repos.upsert_candidate(intent3.search_id, honest)
        controller.repos.insert_decision(intent3.search_id, new_id(), routed)
        CampaignOrchestrator(controller)._publish(intent3.search_id)
        body3 = list_public_results(controller, intent3.search_id, None)
        pub3 = (body3.get("possibly_real") or []) + (body3.get("real") or [])
        first3 = pub3[0] if pub3 else None
        findings.append(
            {
                "case": "routed honest listing",
                "published_count": len(pub3),
                "bucket": None if first3 is None else first3.get("bucket"),
                "listing_url": None if first3 is None else first3.get("listing_url"),
                "tab_reason": None if first3 is None else (first3.get("why") or {}).get("tab_reason"),
                "has_link": bool(first3 and first3.get("listing_url")),
                "has_reason_codes": bool(
                    first3
                    and "Reason codes:" in str((first3.get("why") or {}).get("tab_reason"))
                ),
            }
        )

    leaks = [
        f
        for f in findings
        if f.get("published_without_link") or f.get("published_without_reason_codes")
    ]
    return {
        "attack": "publish a result without a reason or a link",
        "findings": findings,
        "leaks": leaks,
        "outcome": "LEAK" if leaks else "BLOCKED",
    }


def main() -> int:
    report = {
        "git_sha": os.popen("git rev-parse HEAD").read().strip(),
        "replica": attack_replica(),
        "complete_without_fetch": attack_complete_without_fetch(),
        "capability_lie": attack_capability_lie(),
        "publish_without_reason_or_link": attack_publish_without_reason_or_link(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(
        {
            "replica": report["replica"]["outcome"],
            "replica_reached_real": report["replica"]["reached_real"],
            "replica_reached_possibly_real_count": len(report["replica"]["reached_possibly_real"]),
            "complete": report["complete_without_fetch"]["outcome"],
            "capability": report["capability_lie"]["outcome"],
            "publish": report["publish_without_reason_or_link"]["outcome"],
            "wrote": str(OUT),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
