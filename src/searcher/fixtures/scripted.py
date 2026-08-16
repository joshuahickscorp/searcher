"""Fixture-scoped scripted campaign. Not part of the live search path.

Canned listing identity and scores live here so src/searcher/campaigns stays clean.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import Any

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import EvidencePacket, TransitionContext
from searcher.campaigns.resume import reconstruct
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import (
    Availability,
    CampaignState,
    EvidencePolarity,
    FactClass,
    FactOrigin,
    FetchMode,
    HypothesisStatus,
    ImageRole,
    PublicEventName,
    QueryStatus,
    QueryType,
    SourceAdmission,
    SourceOutcome,
)
from searcher.contracts.models import (
    Admission,
    AliasBelief,
    AuthenticityEvidence,
    Belief,
    BucketDecision,
    BucketDecisionFields,
    DiscoveryPage,
    FetchAttempt,
    ImageQuality,
    IntentBudget,
    ItemHypothesis,
    ListingCandidate,
    ListingImage,
    ListingUtility,
    MatchEvidence,
    PrivacySettings,
    QueryVariant,
    ReferenceImage,
    ReferenceImageRef,
    SearchConstraints,
    SearchIntent,
    SourcePlan,
    VisualSignature,
)
from searcher.contracts.primitives import (
    ClassifiedFact,
    PublicExplanation,
    ScoreInterval,
    ScoreWithEvidence,
)
from searcher.contracts.routing import internal_bucket_from_public, public_bucket_from_view
from searcher.core.budgets import Budget
from searcher.core.errors import CancelledError
from searcher.core.ids import new_id, sha256_hex
from searcher.core.policy import POLICY_VERSION, GateView
from searcher.core.time import parse_utc, utc_now
from searcher.evidence.lineage import derived_lineage, raw_lineage
from searcher.evidence.records import EvidenceRecord
from searcher.receipts.types import (
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    ReferenceIngestionReceipt,
    SearchExhaustionReceipt,
    SourceRunReceipt,
)

STEPS: list[CampaignState] = [
    CampaignState.VALIDATING_INPUT,
    CampaignState.INGESTING_REFERENCES,
    CampaignState.CALIBRATING_REFERENCES,
    CampaignState.DECOMPOSING_REFERENCES,
    CampaignState.FORMING_HYPOTHESES,
    CampaignState.PLANNING_QUERIES,
    CampaignState.PLANNING_SOURCES,
    CampaignState.DISCOVERING,
    CampaignState.ACQUIRING,
    CampaignState.NORMALIZING,
    CampaignState.DEDUPLICATING,
    CampaignState.BROAD_RETRIEVAL,
    CampaignState.FINE_MATCHING,
    CampaignState.AUTHENTICITY_REVIEW,
    CampaignState.LIVE_CHECKING,
    CampaignState.RANKING,
    CampaignState.PUBLISHING,
    CampaignState.GAP_ANALYSIS,
    CampaignState.COMPLETE,
]


def locate_fixture(name: str, explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit / name
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "fixtures" / name,
    ]
    for parent in here.parents:
        candidates.append(parent / "fixtures" / name)
    for path in candidates:
        if path.is_dir():
            return path
    raise FileNotFoundError(f"fixture not found: {name}")


def load_fixture_pack(name: str, explicit: Path | None = None) -> dict[str, Any]:
    root = locate_fixture(name, explicit)
    intent = json.loads((root / "intent.json").read_text(encoding="utf-8"))
    listings = json.loads((root / "listings.json").read_text(encoding="utf-8"))
    return {"root": root, "intent": intent, "listings": listings}


def build_intent(pack: dict[str, Any], *, search_id: str | None = None) -> SearchIntent:
    raw = pack["intent"]
    created = parse_utc(str(raw["created_at"]))
    images = [
        ReferenceImageRef(
            reference_image_id=str(item["reference_image_id"]),
            content_digest=sha256_hex(str(item["bytes"]).encode("utf-8")),
        )
        for item in raw.get("images", [])
    ]
    budget_raw = raw["budget"]
    return SearchIntent(
        search_id=search_id or new_id(),
        created_at=created,
        images=images,
        text=raw.get("text"),
        tags=list(raw.get("tags") or []),
        constraints=SearchConstraints.model_validate(raw.get("constraints") or {}),
        budget=IntentBudget.model_validate(budget_raw),
        privacy=PrivacySettings(),
    )


class FixtureRunner:
    def __init__(self, controller: CampaignController, *, step_delay: float = 0.0) -> None:
        self.controller = controller
        self.step_delay = step_delay

    def create(self, fixture_name: str) -> SearchIntent:
        pack = load_fixture_pack(fixture_name, self.controller.settings.fixtures_dir)
        intent = build_intent(pack)
        budget = Budget.from_dict(
            {
                **intent.budget.model_dump(mode="json"),
                "retry_limit": 4,
                "storage_limit": 100_000_000,
                "per_host_rate": {},
            }
        )
        self.controller.create(intent, fixture_name=fixture_name, budget=budget)
        self.controller.set_runtime(
            intent.search_id,
            fixture_name=fixture_name,
            fixture_root=str(pack["root"]),
        )
        return intent

    def run(self, search_id: str) -> None:
        campaign = self.controller.get(search_id)
        runtime = self.controller.repos.get_runtime(search_id)
        completed = {str(s) for s in (runtime.get("completed_steps") or [])}
        for state in STEPS:
            campaign = self.controller.get(search_id)
            if is_terminal(campaign.state) and campaign.state is not state:
                return
            if state.value in completed:
                continue
            self.controller.cancellation.raise_if_cancelled(search_id)
            self._enter(search_id, state)
            self._execute(search_id, state)
            self.controller.checkpoint(search_id, state.value)
            self.controller.mark_step(search_id, state.value)
            completed.add(state.value)
            if self.step_delay > 0:
                time.sleep(self.step_delay)

    def resume(self, search_id: str) -> None:
        reconstruct(self.controller.repos, search_id)
        self.run(search_id)

    def _enter(self, search_id: str, target: CampaignState) -> None:
        campaign = self.controller.get(search_id)
        if campaign.state is target:
            return
        if is_terminal(campaign.state):
            return
        ctx = self._context(search_id, target)
        if campaign.state is CampaignState.CREATED or target in {s for s in STEPS}:
            # Walk one legal hop if needed. Fixture path is linear.
            if target is campaign.state:
                return
            self.controller.transition(search_id, target, context=ctx)

    def _context(self, search_id: str, target: CampaignState) -> TransitionContext:
        ctx = self.controller.context_from_disk(search_id)
        if target is CampaignState.COMPLETE:
            runtime = self.controller.repos.get_runtime(search_id)
            receipt = runtime.get("exhaustion_receipt")
            if not receipt:
                sealed = SearchExhaustionReceipt(
                    search_id=search_id,
                    reason="fixture source exhausted",
                    saturation=True,
                    queries_exhausted=len(self.controller.repos.list_queries(search_id)),
                    sources_covered=1,
                    input_digests=[],
                    output_digests=[],
                ).seal()
                self.controller.store_receipt(sealed)
                receipt = sealed.receipt_id
                self.controller.set_runtime(search_id, exhaustion_receipt=receipt)
            ctx.exhaustion_receipt = str(receipt)
            ctx.reason = "fixture source exhausted"
        return ctx

    def _execute(self, search_id: str, state: CampaignState) -> None:
        handlers = {
            CampaignState.VALIDATING_INPUT: self._validate,
            CampaignState.INGESTING_REFERENCES: self._ingest,
            CampaignState.CALIBRATING_REFERENCES: self._calibrate,
            CampaignState.DECOMPOSING_REFERENCES: self._decompose,
            CampaignState.FORMING_HYPOTHESES: self._hypotheses,
            CampaignState.PLANNING_QUERIES: self._queries,
            CampaignState.PLANNING_SOURCES: self._sources,
            CampaignState.DISCOVERING: self._discover,
            CampaignState.ACQUIRING: self._acquire,
            CampaignState.NORMALIZING: self._normalize,
            CampaignState.DEDUPLICATING: self._dedupe,
            CampaignState.BROAD_RETRIEVAL: self._broad,
            CampaignState.FINE_MATCHING: self._fine,
            CampaignState.AUTHENTICITY_REVIEW: self._authenticity,
            CampaignState.LIVE_CHECKING: self._live,
            CampaignState.RANKING: self._rank,
            CampaignState.PUBLISHING: self._publish,
            CampaignState.GAP_ANALYSIS: self._gaps,
            CampaignState.COMPLETE: self._complete,
        }
        if state is CampaignState.PLANNING_SOURCES:
            self._consult_index(search_id)
        handler = handlers.get(state)
        if handler is not None:
            handler(search_id)
        if state is CampaignState.PUBLISHING:
            self._remember_index(search_id)

    def _consult_index(self, search_id: str) -> None:
        from searcher.index.consult import consult_and_surface

        consult_and_surface(self.controller, search_id)

    def _remember_index(self, search_id: str) -> None:
        from searcher.index.consult import remember_campaign

        remember_campaign(self.controller, search_id)

    def _pack(self, search_id: str) -> dict[str, Any]:
        runtime = self.controller.repos.get_runtime(search_id)
        name = str(runtime.get("fixture_name") or self.controller.get(search_id).fixture_name)
        return load_fixture_pack(name, self.controller.settings.fixtures_dir)

    def _accept(
        self,
        search_id: str,
        *,
        digest: str,
        family_id: str,
        label: str,
        polarity: EvidencePolarity = EvidencePolarity.SUPPORTING,
        fact_class: FactClass = FactClass.USER_SUPPLIED,
        raw: bool = True,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            evidence_id=new_id(),
            search_id=search_id,
            content_digest=digest,
            family_id=family_id,
            polarity=polarity,
            fact_class=fact_class,
            accepted=True,
            lineage=raw_lineage(input_digests=[digest], process=label)
            if raw
            else derived_lineage(input_digests=[digest], derived_from=[], process=label),
            created_at=utc_now(),
            label=label,
        )
        self.controller.record_evidence(record)
        return record

    def _has_hypotheses(self, search_id: str) -> bool:
        return bool(self.controller.repos.list_hypotheses(search_id))

    def _validate(self, search_id: str) -> None:
        intent = self.controller.repos.get_intent(search_id)
        if not intent.images and not (intent.text or intent.tags):
            raise ValueError("fixture intent has no images, text, or tags")
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_PROGRESS.value,
            payload={"phase": "validated"},
        )

    def _ingest(self, search_id: str) -> None:
        existing = self.controller.repos.list_evidence(search_id, accepted_only=True)
        if any(e.label == "reference_image" for e in existing):
            return
        pack = self._pack(search_id)
        digests: list[str] = []
        for item in pack["intent"].get("images", []):
            data = str(item["bytes"]).encode("utf-8")
            digest = self.controller.store.put_private(
                search_id, f"references/{item['reference_image_id']}", data
            )
            digests.append(digest)
            image = ReferenceImage(
                reference_image_id=str(item["reference_image_id"]),
                content_digest=digest,
                media_type="application/octet-stream",
                byte_length=len(data),
                width=int(item.get("width", 1)),
                height=int(item.get("height", 1)),
                quality=ImageQuality(usable_for=["global_identity"]),
            )
            self.controller.store.put_private(
                search_id,
                f"references/{image.reference_image_id}.json",
                image.model_dump_json().encode("utf-8"),
            )
            self._accept(
                search_id,
                digest=digest,
                family_id=digest,
                label="reference_image",
            )
        receipt = ReferenceIngestionReceipt(
            search_id=search_id,
            reference_image_ids=[
                str(i["reference_image_id"]) for i in pack["intent"].get("images", [])
            ],
            byte_count=sum(
                len(str(i["bytes"]).encode("utf-8")) for i in pack["intent"].get("images", [])
            ),
            input_digests=digests,
            output_digests=digests,
        ).seal()
        self.controller.store_receipt(receipt)
        self.controller.set_runtime(
            search_id,
            has_visual_representation=True,
            reference_digests=digests,
            ingestion_receipt=receipt.receipt_id,
        )
        usage = self.controller.usage(search_id)
        if digests:
            usage.consume(
                images=len(digests),
                bytes=sum(len(str(i["bytes"])) for i in pack["intent"]["images"]),
            )
            self.controller.repos.upsert_budget_usage(search_id, usage.snapshot())

    def _calibrate(self, search_id: str) -> None:
        self.controller.set_runtime(search_id, calibrated=True)

    def _decompose(self, search_id: str) -> None:
        self.controller.set_runtime(search_id, decomposed=True)

    def _hypotheses(self, search_id: str) -> None:
        if self._has_hypotheses(search_id):
            return
        pack = self._pack(search_id)
        created = parse_utc(str(pack["intent"]["created_at"]))

        def belief(value: str, origin: FactOrigin, fact_class: FactClass) -> Belief:
            return Belief(
                value=value,
                confidence=0.7,
                fact_class=fact_class,
                origin=origin,
            )

        primary = ItemHypothesis(
            hypothesis_id=new_id(),
            search_id=search_id,
            status=HypothesisStatus.ACTIVE,
            category="footwear",
            brand=belief("Dior Homme", FactOrigin.USER, FactClass.USER_SUPPLIED),
            model_name=belief("General Army Trainer", FactOrigin.USER, FactClass.USER_SUPPLIED),
            line=belief("Army Trainer", FactOrigin.INFERENCE, FactClass.INFERRED),
            designer=belief("Kris Van Assche", FactOrigin.INFERENCE, FactClass.INFERRED),
            season=belief("unknown", FactOrigin.INFERENCE, FactClass.UNRESOLVED),
            year=belief("2007", FactOrigin.USER, FactClass.USER_SUPPLIED),
            colourway=belief("black/olive", FactOrigin.USER, FactClass.USER_SUPPLIED),
            aliases=[
                AliasBelief(
                    alias="Dior GAT 07",
                    language="en",
                    belief=belief("Dior GAT 07", FactOrigin.USER, FactClass.USER_SUPPLIED),
                )
            ],
            visual_signature=VisualSignature(),
            posterior=0.62,
        )
        adjacent = ItemHypothesis(
            hypothesis_id=new_id(),
            search_id=search_id,
            status=HypothesisStatus.ACTIVE,
            category="footwear",
            brand=belief("Dior Homme", FactOrigin.USER, FactClass.USER_SUPPLIED),
            model_name=belief(
                "adjacent military trainer", FactOrigin.INFERENCE, FactClass.INFERRED
            ),
            line=belief("Army Trainer", FactOrigin.INFERENCE, FactClass.INFERRED),
            designer=belief("unknown", FactOrigin.INFERENCE, FactClass.UNRESOLVED),
            season=belief("unknown", FactOrigin.INFERENCE, FactClass.UNRESOLVED),
            year=belief("2006-2008", FactOrigin.INFERENCE, FactClass.INFERRED),
            colourway=belief("unknown", FactOrigin.INFERENCE, FactClass.UNRESOLVED),
            visual_signature=VisualSignature(),
            posterior=0.22,
        )
        del created
        self.controller.repos.upsert_hypothesis(primary)
        self.controller.repos.upsert_hypothesis(adjacent)
        self.controller.set_runtime(
            search_id,
            primary_hypothesis_id=primary.hypothesis_id,
            hypothesis_ids=[primary.hypothesis_id, adjacent.hypothesis_id],
        )

    def _queries(self, search_id: str) -> None:
        if self.controller.repos.list_queries(search_id):
            return
        runtime = self.controller.repos.get_runtime(search_id)
        hid = str(runtime["primary_hypothesis_id"])
        variants = [
            ("en", "Dior Homme General Army Trainer 07", QueryType.EXACT_NAME),
            ("en", "Dior GAT 07", QueryType.ALIAS),
            ("fr", "Dior Homme General Army Trainer 2007", QueryType.TRANSLATED),
        ]
        ids: list[str] = []
        for lang, text, qtype in variants:
            query = QueryVariant(
                query_id=new_id(),
                hypothesis_id=hid,
                round=1,
                language=lang,
                query_text=text,
                query_type=qtype,
                status=QueryStatus.QUEUED,
                expected_gain=0.4,
                cost_estimate=0.1,
            )
            self.controller.repos.upsert_query(search_id, query)
            ids.append(query.query_id)
        self.controller.set_runtime(search_id, query_ids=ids)

    def _sources(self, search_id: str) -> None:
        if self.controller.repos.list_source_runs(search_id):
            return
        runtime = self.controller.repos.get_runtime(search_id)
        plan = SourcePlan(
            source_plan_id=new_id(),
            source_adapter="fixture.dior_minimal",
            query_ids=list(runtime.get("query_ids") or []),
            admission=Admission(status=SourceAdmission.ADMITTED, basis="offline fixture"),
            fetch_modes=[FetchMode.CACHE],
            budget={"pages": 8},
        )
        self.controller.repos.upsert_source_run(
            search_id,
            plan.source_plan_id,
            "fixture.dior_minimal",
            cursor="0",
            last_outcome=SourceOutcome.NOT_ATTEMPTED.value,
            payload=plan.model_dump(mode="json"),
        )
        self.controller.set_runtime(search_id, source_run_id=plan.source_plan_id)

    def _discover(self, search_id: str) -> None:
        if self.controller.repos.get_runtime(search_id).get("index_skip_source_work"):
            self.controller.emit(
                search_id,
                PublicEventName.SEARCH_COVERAGE.value,
                payload={"source": "index", "pages": 0, "from_index": True},
            )
            return
        if self.controller.repos.list_discovery_pages(search_id):
            return
        pack = self._pack(search_id)
        listings = list(pack["listings"]["listings"])
        usage = self.controller.usage(search_id)
        usage.consume(sources=1, pages=1)
        self.controller.repos.upsert_budget_usage(search_id, usage.snapshot())
        runtime = self.controller.repos.get_runtime(search_id)
        query_id = (runtime.get("query_ids") or [None])[0]
        page = DiscoveryPage(
            page_id=new_id(),
            search_id=search_id,
            source_id="fixture.dior_minimal",
            query_id=query_id,
            url="fixture://dior_minimal/listings",
            content_digest=sha256_hex(json.dumps(listings, sort_keys=True).encode()),
            cursor=str(len(listings)),
            outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
            fetched_at=parse_utc(str(pack["intent"]["created_at"])),
        )
        self.controller.repos.insert_discovery_page(page)
        self.controller.repos.upsert_source_run(
            search_id,
            str(runtime["source_run_id"]),
            "fixture.dior_minimal",
            cursor=str(len(listings)),
            last_outcome=SourceOutcome.SEARCHED_MATCHES_FOUND.value,
            payload={"listing_count": len(listings)},
        )
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_COVERAGE.value,
            payload={"source": "fixture.dior_minimal", "pages": 1},
        )
        for listing in listings:
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_DISCOVERED.value,
                payload={"url": listing["url"]},
            )

    def _acquire(self, search_id: str) -> None:
        if self.controller.repos.get_runtime(search_id).get("index_skip_source_work"):
            return
        if self.controller.repos.list_fetch_attempts(search_id):
            return
        pack = self._pack(search_id)
        created = parse_utc(str(pack["intent"]["created_at"]))
        for listing in pack["listings"]["listings"]:
            payload = json.dumps(listing, sort_keys=True).encode("utf-8")
            digest = self.controller.store.put_bytes(
                payload, zone="incoming", campaign_id=search_id, private=True
            )
            attempt = FetchAttempt(
                attempt_id=new_id(),
                source_id="fixture.dior_minimal",
                url=str(listing["url"]),
                canonical_url=str(listing["url"]),
                started_at=created,
                ended_at=created,
                mode=FetchMode.CACHE,
                status=SourceOutcome.SEARCHED_MATCHES_FOUND,
                http_status=200,
                content_digest=digest,
                bytes=len(payload),
            )
            self.controller.repos.insert_fetch_attempt(search_id, attempt)
            usage = self.controller.usage(search_id)
            usage.consume(bytes=len(payload))
            self.controller.repos.upsert_budget_usage(search_id, usage.snapshot())

    def _normalize(self, search_id: str) -> None:
        if self.controller.repos.list_candidates(search_id):
            return
        pack = self._pack(search_id)
        created = parse_utc(str(pack["intent"]["created_at"]))
        for listing in pack["listings"]["listings"]:
            candidate_id = new_id()
            images: list[ListingImage] = []
            for image in listing.get("images") or []:
                blob = str(image["bytes"]).encode("utf-8")
                digest = self.controller.store.put_bytes(
                    blob, zone="incoming", campaign_id=search_id, private=True
                )
                family = str(image.get("family_id") or digest)
                images.append(
                    ListingImage(
                        listing_image_id=new_id(),
                        candidate_id=candidate_id,
                        remote_url=f"fixture://image/{family}",
                        content_digest=digest,
                        role=ImageRole(image.get("role", "unknown")),
                        duplicate_family_id=family,
                        fact_class=FactClass.REPORTED_BY_SOURCE,
                    )
                )
                self._accept(
                    search_id,
                    digest=digest,
                    family_id=family,
                    label="listing_image",
                    fact_class=FactClass.REPORTED_BY_SOURCE,
                )
                usage = self.controller.usage(search_id)
                usage.consume(images=1, bytes=len(blob))
                self.controller.repos.upsert_budget_usage(search_id, usage.snapshot())
            availability = Availability(str(listing["availability"]).upper())
            candidate = ListingCandidate(
                candidate_id=candidate_id,
                canonical_url=str(listing["url"]),
                source_adapter="fixture.dior_minimal",
                source_listing_id=str(listing.get("listing_id") or ""),
                title=ClassifiedFact(
                    value=str(listing.get("title")),
                    fact_class=FactClass.REPORTED_BY_SELLER,
                    origin=FactOrigin.SELLER,
                ),
                description=ClassifiedFact(
                    value=str(listing.get("description")),
                    fact_class=FactClass.REPORTED_BY_SELLER,
                    origin=FactOrigin.SELLER,
                ),
                seller_reported_brand=ClassifiedFact(
                    value=listing.get("brand"),
                    fact_class=FactClass.REPORTED_BY_SELLER,
                    origin=FactOrigin.SELLER,
                ),
                seller_reported_model=ClassifiedFact(
                    value=listing.get("model"),
                    fact_class=FactClass.REPORTED_BY_SELLER,
                    origin=FactOrigin.SELLER,
                ),
                price_original=listing.get("price"),
                currency_original=listing.get("currency"),
                size_original=listing.get("size"),
                availability=availability,
                images=images,
                first_seen_at=created,
                last_checked_at=created,
                explanation=PublicExplanation(
                    live_status=availability,
                    last_checked_at=created,
                    seller_reported_fields=["title", "brand", "model"],
                ),
            )
            self.controller.repos.upsert_candidate(search_id, candidate)
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_NORMALIZED.value,
                payload={"candidate_id": candidate_id},
            )
        # Idempotent "normalize listings" task so property tests can repeat it.
        capsule = self.controller.make_capsule(
            search_id,
            "normalize_listings",
            input_digests=["fixture:dior_minimal:listings"],
            parameters={"fixture": "dior_minimal"},
        )

        def worker(cap: Any) -> EvidencePacket:
            return EvidencePacket(
                task_id=cap.task_id,
                search_id=search_id,
                idempotency_key=cap.idempotency_key,
                outputs={
                    "task_type": "normalize_listings",
                    "count": len(pack["listings"]["listings"]),
                },
            )

        self.controller.run_task(capsule, worker)

    def _dedupe(self, search_id: str) -> None:
        candidates = self.controller.repos.list_candidates(search_id)
        families: dict[str, list[str]] = {}
        for candidate in candidates:
            keys = [
                img.duplicate_family_id or img.content_digest or candidate.candidate_id
                for img in candidate.images
            ]
            key = keys[0] if keys else candidate.candidate_id
            families.setdefault(key, []).append(candidate.candidate_id)
        for family, ids in families.items():
            self.controller.repos.insert_cluster(
                search_id,
                family,
                ids[0],
                {"members": ids, "family": family},
            )
            if len(ids) > 1:
                for extra in ids[1:]:
                    found = next(c for c in candidates if c.candidate_id == extra)
                    updated = found.model_copy(update={"cluster_id": family})
                    self.controller.repos.upsert_candidate(search_id, updated)
            primary = next(c for c in candidates if c.candidate_id == ids[0])
            self.controller.repos.upsert_candidate(
                search_id, primary.model_copy(update={"cluster_id": family})
            )

    def _score(self, mean: float, lower: float, upper: float) -> ScoreWithEvidence:
        return ScoreWithEvidence(
            interval=ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper),
            fact_class=FactClass.INFERRED,
        )

    def _kind_scored(self, search_id: str, kind: str, stage: str | None = None) -> bool:
        for row in self.controller.repos.list_scores(search_id):
            if row["kind"] != kind:
                continue
            if stage is None:
                return True
            payload = row.get("payload_json")
            if payload and stage in str(payload):
                return True
        return False

    def _broad(self, search_id: str) -> None:
        if self._kind_scored(search_id, "ITEM_MATCH", "broad"):
            return
        for candidate in self.controller.repos.list_candidates(search_id):
            self.controller.repos.insert_score(
                search_id,
                new_id(),
                "ITEM_MATCH",
                0.5,
                0.3,
                0.7,
                {"stage": "broad", "candidate_id": candidate.candidate_id},
                candidate_id=candidate.candidate_id,
            )

    def _fine(self, search_id: str) -> None:
        if self._kind_scored(search_id, "ITEM_MATCH") and not self._kind_scored(
            search_id, "ITEM_MATCH", "broad"
        ):
            return
        existing_fine = [
            row
            for row in self.controller.repos.list_scores(search_id)
            if row["kind"] == "ITEM_MATCH"
            and "match_evidence_id" in str(row.get("payload_json") or "")
        ]
        if existing_fine:
            return
        pack = self._pack(search_id)
        by_url = {str(item["url"]): item for item in pack["listings"]["listings"]}
        hid = str(self.controller.repos.get_runtime(search_id)["primary_hypothesis_id"])
        for candidate in self.controller.repos.list_candidates(search_id):
            spec = by_url.get(candidate.canonical_url, {})
            match = spec.get("item_match") or {"mean": 0.5, "lower_bound": 0.3, "upper_bound": 0.7}
            interval = ScoreInterval(
                mean=float(match["mean"]),
                lower_bound=float(match["lower_bound"]),
                upper_bound=float(match["upper_bound"]),
            )
            evidence = MatchEvidence(
                match_evidence_id=new_id(),
                candidate_id=candidate.candidate_id,
                hypothesis_id=hid,
                global_visual=self._score(
                    interval.mean, interval.lower_bound, interval.upper_bound
                ),
                text_identity=self._score(0.6, 0.4, 0.8),
                geometry=self._score(interval.mean, interval.lower_bound, interval.upper_bound),
                material=self._score(0.5, 0.3, 0.7),
                colourway=self._score(0.5, 0.3, 0.7),
                cross_image_consistency=self._score(0.6, 0.4, 0.8),
                metadata_consistency=self._score(0.5, 0.3, 0.7),
                item_match_distribution=interval,
                hard_contradictions=list(spec.get("hard_item_contradictions") or []),
            )
            self.controller.repos.insert_score(
                search_id,
                evidence.match_evidence_id,
                "ITEM_MATCH",
                interval.mean,
                interval.lower_bound,
                interval.upper_bound,
                evidence.model_dump(mode="json"),
                candidate_id=candidate.candidate_id,
            )
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_PROMOTED.value,
                payload={"candidate_id": candidate.candidate_id, "stage": "fine"},
            )

    def _authenticity(self, search_id: str) -> None:
        if self._kind_scored(search_id, "AUTHENTICITY_CONFIDENCE"):
            return
        pack = self._pack(search_id)
        by_url = {str(item["url"]): item for item in pack["listings"]["listings"]}
        for candidate in self.controller.repos.list_candidates(search_id):
            spec = by_url.get(candidate.canonical_url, {})
            auth = spec.get("authenticity") or {"mean": 0.4, "lower_bound": 0.2, "upper_bound": 0.6}
            interval = ScoreInterval(
                mean=float(auth["mean"]),
                lower_bound=float(auth["lower_bound"]),
                upper_bound=float(auth["upper_bound"]),
            )
            record = AuthenticityEvidence(
                authenticity_evidence_id=new_id(),
                candidate_id=candidate.candidate_id,
                reference_class="designer_footwear",
                construction_consistency=self._score(
                    interval.mean, interval.lower_bound, interval.upper_bound
                ),
                label_and_code_consistency=self._score(0.4, 0.2, 0.6),
                logo_and_hardware_consistency=self._score(0.4, 0.2, 0.6),
                material_consistency=self._score(0.4, 0.2, 0.6),
                photo_set_consistency=self._score(0.5, 0.3, 0.7),
                image_originality=self._score(0.5, 0.3, 0.7),
                source_and_seller_signal=self._score(0.4, 0.2, 0.6),
                provenance_signal=self._score(0.3, 0.1, 0.5),
                price_anomaly=self._score(0.5, 0.5, 0.5),
                authenticity_distribution=interval,
                hard_contradictions=list(spec.get("hard_authenticity_contradictions") or []),
                missing_evidence=list(spec.get("missing_evidence") or []),
            )
            self.controller.repos.insert_score(
                search_id,
                record.authenticity_evidence_id,
                "AUTHENTICITY_CONFIDENCE",
                interval.mean,
                interval.lower_bound,
                interval.upper_bound,
                record.model_dump(mode="json"),
                candidate_id=candidate.candidate_id,
            )

    def _live(self, search_id: str) -> None:
        if self._kind_scored(search_id, "LISTING_UTILITY"):
            return
        now = utc_now()
        for candidate in self.controller.repos.list_candidates(search_id):
            updated = candidate.model_copy(
                update={
                    "last_checked_at": now,
                    "explanation": candidate.explanation.model_copy(
                        update={
                            "live_status": candidate.availability,
                            "last_checked_at": now,
                        }
                    ),
                }
            )
            self.controller.repos.upsert_candidate(search_id, updated)
            live = 1.0 if candidate.availability is Availability.LIVE else 0.0
            utility = ListingUtility(
                live=candidate.availability is Availability.LIVE,
                last_checked_at=now,
                utility_score=live,
                image_coverage=0.5,
                description_quality=0.5,
            )
            self.controller.repos.insert_score(
                search_id,
                new_id(),
                "LISTING_UTILITY",
                live,
                live,
                live,
                utility.model_dump(mode="json"),
                candidate_id=candidate.candidate_id,
            )

    def _rank(self, search_id: str) -> None:
        if self.controller.repos.list_decisions(search_id):
            return
        pack = self._pack(search_id)
        by_url = {str(item["url"]): item for item in pack["listings"]["listings"]}
        scores = self.controller.repos.list_scores(search_id)
        match_lb: dict[str, float] = {}
        auth_lb: dict[str, float] = {}
        for row in scores:
            cid = row.get("candidate_id")
            if not cid:
                continue
            if row["kind"] == "ITEM_MATCH":
                match_lb[str(cid)] = float(row["lower_bound"])
            elif row["kind"] == "AUTHENTICITY_CONFIDENCE":
                auth_lb[str(cid)] = float(row["lower_bound"])
        for candidate in self.controller.repos.list_candidates(search_id):
            spec = by_url.get(candidate.canonical_url, {})
            hard_vetoes = list(spec.get("hard_vetoes") or [])
            hard_item = list(spec.get("hard_item_contradictions") or [])
            hard_auth = list(spec.get("hard_authenticity_contradictions") or [])
            completeness = float(spec.get("evidence_completeness") or 0.4)
            view = GateView(
                item_match_lower_bound=match_lb.get(candidate.candidate_id, 0.0),
                authenticity_lower_bound=auth_lb.get(candidate.candidate_id, 0.0),
                evidence_completeness=completeness,
                availability=candidate.availability.value,
                live_checked=True,
                destination_verified=bool(spec.get("destination_verified", True)),
                hard_item_contradictions=hard_item,
                hard_authenticity_contradictions=hard_auth,
                hard_visual_vetoes=list(spec.get("hard_visual_vetoes") or []),
                scam_or_malicious=bool(spec.get("scam", False)),
                hard_vetoes=hard_vetoes,
            )
            public = public_bucket_from_view(view)
            internal = internal_bucket_from_public(
                public, hard_vetoes=view.hard_vetoes + view.hard_visual_vetoes
            )
            decision = BucketDecision(
                candidate_id=candidate.candidate_id,
                decision=BucketDecisionFields(internal=internal, public=public),
                policy_version=POLICY_VERSION,
                item_match_lower_bound=view.item_match_lower_bound,
                authenticity_lower_bound=view.authenticity_lower_bound,
                evidence_completeness=completeness,
                hard_vetoes=view.hard_vetoes + view.hard_visual_vetoes,
                reason_codes=["fixture-gate"],
                explanation=PublicExplanation(
                    support=list(spec.get("support") or []),
                    contradictions=hard_item + hard_auth,
                    missing_evidence=list(spec.get("missing_evidence") or []),
                    live_status=candidate.availability,
                    last_checked_at=candidate.last_checked_at,
                    seller_reported_fields=["title"],
                ),
            )
            self.controller.repos.insert_decision(search_id, new_id(), decision)
            receipt = BucketDecisionReceipt(
                search_id=search_id,
                candidate_id=candidate.candidate_id,
                internal=internal.value,
                public=public.value,
                input_digests=[img.content_digest or "" for img in candidate.images],
                payload={"candidate_id": candidate.candidate_id},
            ).seal()
            self.controller.store_receipt(receipt)

    def _publish(self, search_id: str) -> None:
        if self.controller.repos.list_results(search_id):
            return
        for decision in self.controller.repos.list_decisions(search_id):
            result_id = new_id()
            self.controller.repos.insert_result(
                search_id,
                result_id,
                decision.candidate_id,
                decision.decision.public.value,
                decision.model_dump(mode="json"),
            )
            if decision.decision.public.value == "real":
                name = PublicEventName.RESULT_REAL.value
            elif decision.decision.public.value == "possibly_real":
                name = PublicEventName.RESULT_POSSIBLY_REAL.value
            else:
                name = PublicEventName.RESULT_REMOVED.value
            self.controller.emit(
                search_id,
                name,
                payload={"candidate_id": decision.candidate_id, "result_id": result_id},
            )

    def _gaps(self, search_id: str) -> None:
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_PROGRESS.value,
            payload={"phase": "gap_analysis", "replans": 0},
        )

    def _complete(self, search_id: str) -> None:
        for query in self.controller.repos.list_queries(search_id):
            if query.status is QueryStatus.QUEUED or query.status is QueryStatus.RUNNING:
                self.controller.repos.upsert_query(
                    search_id, query.model_copy(update={"status": QueryStatus.EXHAUSTED})
                )
        runtime = self.controller.repos.get_runtime(search_id)
        source_receipt = SourceRunReceipt(
            search_id=search_id,
            source_id="fixture.dior_minimal",
            outcome=SourceOutcome.SEARCHED_MATCHES_FOUND.value,
            pages=1,
            matches=len(self.controller.repos.list_candidates(search_id)),
        ).seal()
        self.controller.store_receipt(source_receipt)
        terminal = CampaignTerminalReceipt(
            search_id=search_id,
            terminal_status=CampaignState.COMPLETE.value,
            terminal_reason="fixture source exhausted",
            state_version=self.controller.get(search_id).state_version,
            predecessor=str(runtime.get("exhaustion_receipt") or ""),
        ).seal()
        self.controller.store_receipt(terminal)
        export = {
            "search_id": search_id,
            "receipt_id": terminal.receipt_id,
            "digest": terminal.digest,
            **terminal.model_dump(mode="json"),
        }
        export_path = (
            self.controller.settings.data_root
            / "exports"
            / search_id
            / "campaign_terminal.receipt.json"
        )
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(export, indent=2, sort_keys=True), encoding="utf-8")
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_COMPLETE.value,
            payload={"receipt": terminal.receipt_id, "path": str(export_path)},
        )


def create_and_run(
    controller: CampaignController,
    fixture_name: str,
    *,
    step_delay: float = 0.0,
) -> str:
    runner = FixtureRunner(controller, step_delay=step_delay)
    intent = runner.create(fixture_name)
    with contextlib.suppress(CancelledError):
        runner.run(intent.search_id)
    return intent.search_id
