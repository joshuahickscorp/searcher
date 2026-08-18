"""§8.2 / §10 campaign orchestrator. The controller remains the only writer."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import TransitionContext
from searcher.campaigns.publication import (
    event_name_for_public_bucket,
    published_public_bucket,
    published_terminal_status,
)
from searcher.campaigns.resume import reconstruct
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import (
    Availability,
    CampaignState,
    PublicEventName,
    QueryStatus,
)
from searcher.contracts.models import (
    ItemHypothesis,
    ListingCandidate,
    ListingImage,
    ListingUtility,
    QueryVariant,
    ReferenceAnalysis,
)
from searcher.core.errors import BudgetExceeded, CancelledError, ErrorClass, SearcherError
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.hypotheses.aliases import AliasEvidence, can_promote_alias, promote_or_hold
from searcher.hypotheses.product_codes import assess_code
from searcher.queries.compiler import compile_queries
from searcher.queries.dedupe import normalize_query_text
from searcher.ranking.utility import listing_utility
from searcher.receipts.types import (
    AuthenticityDecisionReceipt,
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    CandidateNormalizationReceipt,
    CostReceipt,
    DeduplicationReceipt,
    LiveCheckReceipt,
    MatchEvidenceReceipt,
    QueryPlanReceipt,
    SearchExhaustionReceipt,
    SourceAdmissionReceipt,
)
from searcher.retrieval.cost import CostLedger
from searcher.retrieval.text import self_declared_replica, tokenize
from searcher.sources.broker import DEFAULT_ORDER
from searcher.sources.families import names_for_scopes, normalize_source_scopes
from searcher.sources.statuses import is_block
from searcher.workers.reference.pipeline import run_reference_query_wave

STAGE_LANGUAGE: dict[str, str] = {
    CampaignState.CREATED.value: "Understanding the item",
    CampaignState.VALIDATING_INPUT.value: "Understanding the item",
    CampaignState.INGESTING_REFERENCES.value: "Understanding the item",
    CampaignState.CALIBRATING_REFERENCES.value: "Understanding the item",
    CampaignState.DECOMPOSING_REFERENCES.value: "Reading visible labels",
    CampaignState.FORMING_HYPOTHESES.value: "Building possible identities",
    CampaignState.PLANNING_QUERIES.value: "Searching exact names",
    CampaignState.PLANNING_SOURCES.value: "Searching international sources",
    CampaignState.DISCOVERING.value: "Searching international sources",
    CampaignState.ACQUIRING.value: "Comparing candidate images",
    CampaignState.NORMALIZING.value: "Comparing candidate images",
    CampaignState.DEDUPLICATING.value: "Comparing candidate images",
    CampaignState.BROAD_RETRIEVAL.value: "Comparing candidate images",
    CampaignState.FINE_MATCHING.value: "Checking detail consistency",
    CampaignState.AUTHENTICITY_REVIEW.value: "Checking listing authenticity evidence",
    CampaignState.LIVE_CHECKING.value: "Verifying live links",
    CampaignState.RANKING.value: "Ranking results",
    CampaignState.PUBLISHING.value: "Ranking results",
    CampaignState.GAP_ANALYSIS.value: "Ranking results",
    CampaignState.REPLANNING.value: "Searching alternate names",
}

REFERENCE_DONE = CampaignState.PLANNING_QUERIES.value

# Fine match, authenticity, and live-check stay inside the sealed page/image
# budget. Broad retrieval may keep many hits for recall scoring; only this
# many go through the expensive remaining stages.
FINE_COMPARE_CAP = 8

_IMAGE_PREFIXES = (b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")


def select_kept_ids(
    ranked_ids: list[str],
    all_ids: list[str],
    *,
    cap: int = FINE_COMPARE_CAP,
) -> list[str]:
    """Highest-recall first, then fill from discovery order, never above cap."""
    out: list[str] = []
    seen: set[str] = set()
    for cid in list(ranked_ids) + list(all_ids):
        if not cid or cid in seen:
            continue
        out.append(cid)
        seen.add(cid)
        if len(out) >= cap:
            break
    return out


_MATCH_STAGES = frozenset(
    {
        CampaignState.FINE_MATCHING,
        CampaignState.AUTHENTICITY_REVIEW,
        CampaignState.LIVE_CHECKING,
        CampaignState.RANKING,
        CampaignState.PUBLISHING,
    }
)


def _looks_like_image(data: bytes) -> bool:
    if data.startswith(_IMAGE_PREFIXES):
        return True
    return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def layers_present() -> dict[str, bool]:
    present = {"discovery": False, "routing": False}
    try:
        from searcher.sources.engine import DiscoveryEngine

        del DiscoveryEngine
        present["discovery"] = True
    except Exception:
        present["discovery"] = False
    try:
        from searcher.ranking.buckets import route_candidate
        from searcher.retrieval.pipeline import run_broad_retrieval

        del route_candidate, run_broad_retrieval
        present["routing"] = True
    except Exception:
        present["routing"] = False
    return present


def _from_index_feed(candidate: object) -> bool:
    """True when an authoritative source feed published this URL itself.

    structured_data is a plain dict on the model, not an object; reading it with
    getattr silently answered False for every candidate.
    """
    structured = getattr(candidate, "structured_data", None)
    if not isinstance(structured, dict):
        return False
    raw = structured.get("raw")
    return bool(raw.get("from_index_feed")) if isinstance(raw, dict) else False


class CampaignOrchestrator:
    """Walk §10.1 states in §8.2 order. Every stage is optional and degradable."""

    def __init__(
        self,
        controller: CampaignController,
        *,
        source_names: list[str] | None = None,
        max_rounds: int = 2,
        max_work: int = 40,
        batch_size: int = 4,
    ) -> None:
        self.controller = controller
        self.source_names = source_names
        self.max_rounds = max(1, max_rounds)
        self.max_work = max_work
        self.batch_size = batch_size
        self.engine: Any = None
        self.blocked_lanes: dict[str, str] = {}
        self.round = 1
        self._started = 0.0
        self._destination_verified: dict[str, bool] = {}
        self._destination_attested: dict[str, bool] = {}
        self._kept_ids: list[str] = []

    def run(self, search_id: str) -> None:
        reconstruct(self.controller.repos, search_id)
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state) or self.controller.repos.is_deleted(search_id):
            return
        self._started = time.monotonic()
        runtime = self.controller.repos.get_runtime(search_id)
        self.round = int(runtime.get("orchestrator_round") or 1)
        try:
            self._open_engine(search_id)
            self._ensure_reference(search_id)
            while self.round <= self.max_rounds:
                self.controller.cancellation.raise_if_cancelled(search_id)
                if is_terminal(self.controller.get(search_id).state):
                    return
                self._run_pipeline(search_id)
                if is_terminal(self.controller.get(search_id).state):
                    return
                if self._should_stop(search_id) or not self._replan(search_id):
                    break
                self.round += 1
                self.controller.set_runtime(search_id, orchestrator_round=self.round)
            self._terminate(search_id)
        except CancelledError:
            self._cleanup()
            return
        except BudgetExceeded:
            self._charge_wall(search_id)
            self._salvage_publish(search_id)
            self._terminate(search_id, forced=CampaignState.PARTIAL, reason="budget exhausted")
        except SearcherError as exc:
            if exc.error_class is ErrorClass.CANCELLED:
                return
            self._fail(search_id, exc)
        except Exception as exc:
            self._fail(search_id, exc)
        finally:
            self._cleanup()

    def resume(self, search_id: str) -> None:
        self.run(search_id)

    def _open_engine(self, search_id: str) -> None:
        present = layers_present()
        if not present["discovery"]:
            self.blocked_lanes["discovery"] = "Discovery engine could not be imported."
            return
        try:
            from searcher.sources.engine import DiscoveryEngine

            self.engine = DiscoveryEngine(
                self.controller, batch_size=self.batch_size, max_work=self.max_work
            )
        except Exception as exc:
            self.blocked_lanes["discovery"] = f"Discovery engine unavailable: {exc}"
            self.engine = None
        if not present["routing"]:
            self.blocked_lanes["routing"] = (
                "Retrieval, matching, authenticity, or ranking could not be imported."
            )
        del search_id

    def _cleanup(self) -> None:
        engine = self.engine
        self.engine = None
        if engine is not None:
            close = getattr(engine, "close", None)
            if callable(close):
                close()

    def _completed(self, search_id: str) -> set[str]:
        runtime = self.controller.repos.get_runtime(search_id)
        return {str(item) for item in (runtime.get("completed_steps") or [])}

    def _progress(self, search_id: str, stage: str, detail: str | None = None) -> None:
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_PROGRESS.value,
            payload={"stage": stage, "detail": detail, "phase": stage},
            actor="orchestrator",
        )
        self.controller.set_runtime(search_id, progress={"stage": stage, "detail": detail})

    def _context(self, search_id: str, target: CampaignState) -> TransitionContext:
        ctx = self.controller.context_from_disk(search_id)
        if target is CampaignState.COMPLETE:
            runtime = self.controller.repos.get_runtime(search_id)
            receipt = runtime.get("exhaustion_receipt")
            ctx.exhaustion_receipt = str(receipt) if receipt else ctx.exhaustion_receipt
        return ctx

    def _enter(self, search_id: str, target: CampaignState) -> None:
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state) or campaign.state is target:
            return
        self.controller.transition(
            search_id, target, context=self._context(search_id, target), actor="orchestrator"
        )

    def _finish_stage(self, search_id: str, state: CampaignState) -> None:
        self.controller.checkpoint(search_id, state.value)
        self.controller.mark_step(search_id, state.value)
        self.controller.persist_usage(search_id)
        delay = self.controller.settings.step_delay_seconds
        if delay > 0:
            time.sleep(delay)

    def _sequence(self, search_id: str) -> list[CampaignState]:
        seq = [
            CampaignState.PLANNING_SOURCES,
            CampaignState.DISCOVERING,
            CampaignState.ACQUIRING,
            CampaignState.NORMALIZING,
            CampaignState.DEDUPLICATING,
            CampaignState.BROAD_RETRIEVAL,
        ]
        if self.controller.repos.list_candidates(search_id):
            seq.extend(
                [
                    CampaignState.FINE_MATCHING,
                    CampaignState.AUTHENTICITY_REVIEW,
                    CampaignState.LIVE_CHECKING,
                    CampaignState.RANKING,
                    CampaignState.PUBLISHING,
                ]
            )
        seq.append(CampaignState.GAP_ANALYSIS)
        return seq

    def _ensure_reference(self, search_id: str) -> None:
        completed = self._completed(search_id)
        if REFERENCE_DONE in completed:
            return
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state):
            return
        if (
            campaign.state
            in {
                CampaignState.PLANNING_SOURCES,
                CampaignState.DISCOVERING,
                CampaignState.ACQUIRING,
                CampaignState.NORMALIZING,
                CampaignState.DEDUPLICATING,
                CampaignState.BROAD_RETRIEVAL,
                CampaignState.GAP_ANALYSIS,
                CampaignState.REPLANNING,
            }
            | _MATCH_STAGES
        ):
            return
        run_reference_query_wave(self.controller, search_id, [], settings=self.controller.settings)

    def _run_pipeline(self, search_id: str) -> None:
        handlers: dict[CampaignState, Any] = {
            CampaignState.PLANNING_SOURCES: self._plan_sources,
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
        }
        seen: set[CampaignState] = set()
        while True:
            campaign = self.controller.get(search_id)
            if is_terminal(campaign.state):
                return
            completed = self._completed(search_id)
            remaining = [
                state for state in self._sequence(search_id) if state.value not in completed
            ]
            if not remaining:
                return
            state = remaining[0]
            if state in seen:
                return
            seen.add(state)
            self.controller.cancellation.raise_if_cancelled(search_id)
            if self._wall_exceeded(search_id):
                raise BudgetExceeded(
                    "sealed budget ceiling would be crossed on wall_seconds",
                    dimension="wall_seconds",
                    search_id=search_id,
                )
            if state in _MATCH_STAGES and "routing" in self.blocked_lanes:
                if campaign.state is CampaignState.BROAD_RETRIEVAL:
                    self._enter(search_id, CampaignState.GAP_ANALYSIS)
                    self._gaps(search_id)
                    self._finish_stage(search_id, CampaignState.GAP_ANALYSIS)
                return
            self._enter(search_id, state)
            language = STAGE_LANGUAGE.get(state.value, "Ranking results")
            self._progress(search_id, language)
            handler = handlers.get(state)
            if handler is not None:
                handler(search_id)
            self._finish_stage(search_id, state)

    def _primary_hypothesis(self, search_id: str) -> ItemHypothesis | None:
        hyps = self.controller.repos.list_hypotheses(search_id)
        if not hyps:
            return None
        return max(hyps, key=lambda item: item.posterior)

    def _analysis(self, search_id: str) -> ReferenceAnalysis | None:
        try:
            raw = self.controller.store.get_private(search_id, "analysis.json")
        except (FileNotFoundError, KeyError):
            return None
        return ReferenceAnalysis.model_validate_json(raw)

    def _selected_scopes(self, search_id: str) -> tuple[str, ...]:
        runtime = self.controller.repos.get_runtime(search_id)
        return normalize_source_scopes(runtime.get("source_scopes"))

    def _scoped_source_names(self, search_id: str) -> list[str]:
        preferred = tuple(self.source_names) if self.source_names is not None else None
        return list(
            names_for_scopes(
                self._selected_scopes(search_id),
                preferred,
                default_order=DEFAULT_ORDER,
            )
        )

    def _plan_sources(self, search_id: str) -> None:
        if self.engine is None:
            self.blocked_lanes.setdefault("discovery", "Discovery layer is not present.")
            return
        from searcher.sources.broker import SourceBroker

        queries = self.controller.repos.list_queries(search_id)
        usage = self.controller.usage(search_id)
        scopes = self._selected_scopes(search_id)
        names = tuple(self._scoped_source_names(search_id))
        broker = SourceBroker(health=self.engine.health, names=names)
        try:
            plans = broker.plan(queries, usage, families=frozenset(scopes))
        except Exception as exc:
            self.blocked_lanes["discovery"] = f"Source planning failed: {exc}"
            return
        for plan in plans:
            self.controller.repos.upsert_source_run(
                search_id,
                plan.source_plan_id,
                plan.source_adapter,
                cursor=None,
                last_outcome="NOT_ATTEMPTED",
                payload=plan.model_dump(mode="json"),
            )
            receipt = SourceAdmissionReceipt(
                search_id=search_id,
                source_id=plan.source_adapter,
                url=plan.source_adapter,
                decision=plan.admission.status.value,
                basis=plan.admission.basis,
            ).seal()
            self.controller.store_receipt(receipt)
        if not plans:
            self.blocked_lanes["discovery"] = "No admitted sources accepted the compiled queries."
        self.controller.set_runtime(
            search_id,
            planned_sources=[p.source_adapter for p in plans],
            source_scopes=list(scopes),
        )

    def _discover(self, search_id: str) -> None:
        if self.engine is None:
            self.blocked_lanes.setdefault("discovery", "Discovery layer is not present.")
            self._emit_discovery_fallback(search_id)
            return
        queries = self.controller.repos.list_queries(search_id)
        try:
            summary = self.engine.run(
                search_id,
                queries,
                source_names=self._scoped_source_names(search_id),
                families=frozenset(self._selected_scopes(search_id)),
            )
        except BudgetExceeded:
            raise
        except CancelledError:
            raise
        except Exception as exc:
            self.blocked_lanes["discovery"] = f"Discovery failed: {exc}"
            self._emit_discovery_fallback(search_id)
            return
        coverage = self._ui_coverage(search_id, summary.coverage, summary.candidates_after, summary)
        self.controller.set_runtime(
            search_id,
            coverage=coverage,
            last_discovery={
                "before": summary.candidates_before,
                "after": summary.candidates_after,
                "index_expansions": list(summary.expansions),
                "catalog_fallbacks": list(getattr(summary, "catalog_fallbacks", []) or []),
                "strategies": dict(getattr(summary, "strategy_coverage", {}) or {}),
            },
        )
        self.controller.emit(
            search_id, PublicEventName.SEARCH_COVERAGE.value, payload=coverage, actor="orchestrator"
        )
        for candidate in summary.listings:
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_DISCOVERED.value,
                payload={"candidate_id": candidate.candidate_id, "url": candidate.canonical_url},
                actor="orchestrator",
            )

    def _emit_discovery_fallback(self, search_id: str) -> None:
        reason = self.blocked_lanes.get("discovery") or "Discovery layer is not present."
        coverage = {
            "sources_completed": [],
            "sources_blocked": [
                {
                    "id": "live_discovery",
                    "name": "Live listing discovery",
                    "status": "SOURCE_UNAVAILABLE",
                    "detail": reason,
                }
            ],
            "sources_in_progress": [],
            "pages_fetched": 0,
            "candidates_normalized": 0,
            "candidates_hidden": 0,
        }
        self.controller.set_runtime(search_id, coverage=coverage)
        self.controller.emit(
            search_id, PublicEventName.SEARCH_COVERAGE.value, payload=coverage, actor="orchestrator"
        )
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_WARNING.value,
            payload={"code": "discovery_unavailable", "message": reason},
            actor="orchestrator",
        )

    def _ui_coverage(
        self,
        search_id: str,
        per_source: dict[str, str],
        normalized: int,
        summary: Any | None = None,
    ) -> dict[str, object]:
        completed: list[dict[str, object]] = []
        blocked: list[dict[str, object]] = []
        from searcher.contracts.enums import SourceOutcome

        details = dict(getattr(summary, "coverage_details", {}) or {}) if summary else {}
        strategies = dict(getattr(summary, "strategy_coverage", {}) or {}) if summary else {}
        for source_id, outcome in per_source.items():
            source_strategies = list(strategies.get(source_id) or [])
            detail = str(details.get(source_id) or "")
            if not detail and source_strategies:
                from searcher.sources.strategies import format_strategy_detail

                detail = format_strategy_detail(source_strategies)
            entry: dict[str, object] = {
                "id": source_id,
                "name": source_id,
                "status": outcome,
                "detail": detail,
            }
            if source_strategies:
                entry["strategies"] = source_strategies
            known = SourceOutcome._value2member_map_
            parsed = SourceOutcome(outcome) if outcome in known else None
            if parsed is not None and (
                is_block(parsed)
                or parsed
                in {
                    SourceOutcome.AUTH_REQUIRED,
                    SourceOutcome.SOURCE_UNAVAILABLE,
                    SourceOutcome.UNMEASURABLE,
                }
            ):
                blocked.append(entry)
            else:
                completed.append(entry)
        pages = len(self.controller.repos.list_discovery_pages(search_id))
        hidden = 0
        for row in self.controller.repos.list_results(search_id):
            if str(row["public_bucket"]) == "hidden":
                hidden += 1
        return {
            "sources_completed": completed,
            "sources_blocked": blocked,
            "sources_in_progress": [],
            "pages_fetched": pages,
            # `pages_fetched` counts every discovery page. The campaign
            # `page_limit` caps only HTTP fetches: a browser fetch charges
            # `browser_pages`, a separate dimension with its own ceiling.
            # Reporting the total beside a stated page_limit of 40 is how a live
            # run came to read as "60 pages against a limit of 40" - two
            # different quantities compared as though they were one. The number
            # the limit actually governs is published beside it so the limit can
            # be checked rather than inferred.
            "pages_charged_to_page_limit": self._pages_charged(search_id),
            "candidates_normalized": normalized,
            "candidates_hidden": hidden,
        }

    def _bytes_present(self, search_id: str, digest: str) -> bool:
        """Whether this campaign can actually read the bytes behind a digest.

        A digest was treated as proof the image was already downloaded, which
        holds for a candidate discovered by this campaign and not for one
        hydrated from the warm index: hydration copies the digest from the
        stored payload while the bytes live in whichever campaign first indexed
        them. The image was then skipped as already-present, the candidate
        reached broad retrieval with no pixels, scored nothing visually, and was
        cut by the fine-compare cap before any judgment ran.
        """
        try:
            return bool(self.controller.store.get(digest, campaign_id=search_id))
        except Exception:
            try:
                return bool(self.controller.store.get(digest))
            except Exception:
                return False

    def _download_listing_image(
        self,
        image: ListingImage,
        *,
        search_id: str,
        http: Any,
        usage: Any,
    ) -> tuple[ListingImage, bool]:
        if not image.remote_url:
            return image, False
        if image.content_digest and self._bytes_present(search_id, image.content_digest):
            return image, False
        if usage.would_exceed(images=1) is not None:
            return image, False
        remote = image.remote_url
        if not remote.startswith(("http://", "https://")):
            return image, False
        try:
            response = http.get(remote, pace=False)
        except Exception:
            return image, False
        body = getattr(response, "body", b"") or b""
        if getattr(response, "status", 0) != 200 or not _looks_like_image(body):
            return image, False
        digest = self.controller.store.put_bytes(
            body, zone="incoming", campaign_id=search_id, private=True
        )
        usage.consume(images=1, bytes=len(body))
        return image.model_copy(update={"content_digest": digest}), True

    def _acquire(self, search_id: str) -> None:
        candidates = self.controller.repos.list_candidates(search_id)
        if not candidates or self.engine is None:
            return
        http = getattr(self.engine, "http", None)
        if http is None:
            return
        # One image per listing first so embeddings can weigh the catalog,
        # then fill remaining slots until the image budget is gone.
        for per_candidate in (1, None):
            usage = self.controller.usage(search_id)
            for candidate in self.controller.repos.list_candidates(search_id):
                updated_images: list[ListingImage] = []
                changed = False
                downloaded = 0
                for image in candidate.images:
                    if (
                        per_candidate is not None
                        and downloaded >= per_candidate
                        and not image.content_digest
                    ):
                        updated_images.append(image)
                        continue
                    fresh, did = self._download_listing_image(
                        image, search_id=search_id, http=http, usage=usage
                    )
                    if did:
                        downloaded += 1
                        changed = True
                    updated_images.append(fresh)
                if changed:
                    self.controller.repos.upsert_candidate(
                        search_id, candidate.model_copy(update={"images": updated_images})
                    )
        self.controller.persist_usage(search_id)

    def _normalize(self, search_id: str) -> None:
        candidates = self.controller.repos.list_candidates(search_id)
        ids = [item.candidate_id for item in candidates]
        for candidate in candidates:
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_NORMALIZED.value,
                payload={"candidate_id": candidate.candidate_id},
                actor="orchestrator",
            )
        receipt = CandidateNormalizationReceipt(
            search_id=search_id, candidate_ids=ids, count=len(ids)
        ).seal()
        self.controller.store_receipt(receipt)
        runtime = self.controller.repos.get_runtime(search_id)
        coverage = runtime.get("coverage")
        if isinstance(coverage, dict):
            coverage = dict(coverage)
            coverage["candidates_normalized"] = len(ids)
            self.controller.set_runtime(search_id, coverage=coverage)

    def _dedupe(self, search_id: str) -> None:
        from searcher.deduplication.clusters import cluster_candidates

        candidates = self.controller.repos.list_candidates(search_id)
        if not candidates:
            receipt = DeduplicationReceipt(search_id=search_id, before=0, after=0).seal()
            self.controller.store_receipt(receipt)
            return
        if all(item.cluster_id for item in candidates):
            receipt = DeduplicationReceipt(
                search_id=search_id, before=len(candidates), after=len(candidates)
            ).seal()
            self.controller.store_receipt(receipt)
            return
        result = cluster_candidates(candidates)
        for candidate in result.representatives:
            self.controller.repos.upsert_candidate(search_id, candidate)
        for cluster in result.clusters:
            self.controller.repos.insert_cluster(
                search_id,
                cluster.cluster_id,
                cluster.representative_id,
                {
                    "members": cluster.member_ids,
                    "reason": cluster.reason,
                    "savings": result.savings,
                },
            )
        receipt = DeduplicationReceipt(
            search_id=search_id,
            before=result.before,
            after=result.after,
            exact_url_dupes=result.exact_url_dupes,
            image_family_dupes=result.image_family_dupes,
            text_dupes=result.text_dupes,
            savings=result.savings,
        ).seal()
        self.controller.store_receipt(receipt)

    def _reference_pngs(self, search_id: str) -> dict[str, bytes]:
        runtime = self.controller.repos.get_runtime(search_id)
        out: dict[str, bytes] = {}
        for digest in runtime.get("reference_digests") or []:
            try:
                out[str(digest)] = self.controller.store.get(str(digest), campaign_id=search_id)
            except Exception:
                continue
        return out

    def _candidate_pngs(self, search_id: str, candidate: ListingCandidate) -> dict[str, bytes]:
        pngs: dict[str, bytes] = {}
        for image in candidate.images:
            if not image.content_digest:
                continue
            try:
                pngs[image.listing_image_id] = self.controller.store.get(
                    image.content_digest, campaign_id=search_id
                )
            except Exception:
                continue
        return pngs

    def _already_scored(self, search_id: str, kind: str, stage: str | None = None) -> bool:
        for row in self.controller.repos.list_scores(search_id):
            if row["kind"] != kind:
                continue
            if stage is None:
                return True
            if stage in str(row.get("payload_json") or ""):
                return True
        return False

    def _broad(self, search_id: str) -> None:
        candidates = self.controller.repos.list_candidates(search_id)
        if not candidates:
            self._kept_ids = []
            return
        if "routing" in self.blocked_lanes:
            self._kept_ids = select_kept_ids([], [item.candidate_id for item in candidates])
            return
        hypothesis = self._primary_hypothesis(search_id)
        if hypothesis is None:
            self.blocked_lanes["retrieval"] = "No hypothesis available for retrieval."
            self._kept_ids = select_kept_ids([], [item.candidate_id for item in candidates])
            return
        try:
            from searcher.retrieval.pipeline import run_broad_retrieval
        except Exception as exc:
            self.blocked_lanes["retrieval"] = str(exc)
            self._kept_ids = select_kept_ids([], [item.candidate_id for item in candidates])
            return
        ledger = CostLedger(search_id=search_id)
        pngs = {item.candidate_id: self._candidate_pngs(search_id, item) for item in candidates}
        result = run_broad_retrieval(
            candidates=candidates,
            hypothesis=hypothesis,
            reference_signature=hypothesis.visual_signature,
            reference_pngs=self._reference_pngs(search_id),
            candidate_pngs=pngs,
            ledger=ledger,
            already_deduplicated=True,
        )
        kept = result.kept or result.hits
        ranked_ids = [hit.candidate.candidate_id for hit in kept]
        self._kept_ids = select_kept_ids(ranked_ids, [item.candidate_id for item in candidates])
        if not self._already_scored(search_id, "ITEM_MATCH", "broad"):
            for hit in kept:
                mean = max(0.0, min(1.0, hit.signals.recall_score))
                lower = max(0.0, mean - 0.12)
                upper = min(1.0, mean + 0.12)
                self.controller.repos.insert_score(
                    search_id,
                    new_id(),
                    "ITEM_MATCH",
                    mean,
                    lower,
                    upper,
                    {"stage": "broad", "candidate_id": hit.candidate.candidate_id},
                    candidate_id=hit.candidate.candidate_id,
                )
        self.controller.store_receipt(
            CostReceipt(
                search_id=search_id,
                stages=ledger.stage_names(),
                cache_hits=ledger.cache_hits,
                model_calls=ledger.model_calls,
                bytes_touched=ledger.bytes_touched,
                cheap_first=ledger.cheap_first_respected(),
            ).seal()
        )
        self.controller.set_runtime(
            search_id, kept_ids=self._kept_ids, pending_comparisons=self._kept_ids
        )

    def _candidates_for_match(self, search_id: str) -> list[ListingCandidate]:
        listed = self.controller.repos.list_candidates(search_id)
        by_id = {item.candidate_id: item for item in listed}
        runtime = self.controller.repos.get_runtime(search_id)
        kept = list(self._kept_ids or runtime.get("kept_ids") or by_id.keys())
        return [by_id[cid] for cid in kept if cid in by_id][:FINE_COMPARE_CAP]

    def _fine(self, search_id: str) -> None:
        candidates = self._candidates_for_match(search_id)
        hypothesis = self._primary_hypothesis(search_id)
        if not candidates or hypothesis is None:
            return
        try:
            from searcher.matching.pipeline import (
                enrich_candidate,
                match_candidate,
                prepare_reference,
            )
        except Exception as exc:
            self.blocked_lanes["matching"] = str(exc)
            return
        ledger = CostLedger(search_id=search_id)
        ledger.mark_deduplicated()
        ref_pngs = self._reference_pngs(search_id)
        ref_desc = prepare_reference(ref_pngs, ledger=ledger)
        intent = self.controller.repos.get_intent(search_id)
        for candidate in candidates:
            if any(
                row["kind"] == "ITEM_MATCH"
                and row.get("candidate_id") == candidate.candidate_id
                and "match_evidence_id" in str(row.get("payload_json") or "")
                for row in self.controller.repos.list_scores(search_id)
            ):
                continue
            pngs = self._candidate_pngs(search_id, candidate)
            enriched = enrich_candidate(candidate, pngs, ledger=ledger)
            evidence = match_candidate(
                hypothesis=hypothesis,
                candidate=enriched,
                reference_pngs=ref_pngs,
                reference_descriptors=ref_desc,
                constraints=intent.constraints,
                ledger=ledger,
            )
            interval = evidence.item_match_distribution
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
            self.controller.store_receipt(
                MatchEvidenceReceipt(
                    search_id=search_id,
                    candidate_id=candidate.candidate_id,
                    hypothesis_id=hypothesis.hypothesis_id,
                    item_match_lower_bound=interval.lower_bound,
                ).seal()
            )
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_PROMOTED.value,
                payload={"candidate_id": candidate.candidate_id, "stage": "fine"},
                actor="orchestrator",
            )

    def _authenticity(self, search_id: str) -> None:
        candidates = self._candidates_for_match(search_id)
        hypothesis = self._primary_hypothesis(search_id)
        if not candidates or hypothesis is None:
            return
        try:
            from searcher.authenticity.engine import assess_authenticity
            from searcher.matching.pipeline import enrich_candidate, prepare_reference
        except Exception as exc:
            self.blocked_lanes["authenticity"] = str(exc)
            return
        ledger = CostLedger(search_id=search_id)
        ledger.mark_deduplicated()
        ref_desc = prepare_reference(self._reference_pngs(search_id), ledger=ledger)
        intent = self.controller.repos.get_intent(search_id)
        for candidate in candidates:
            if any(
                row["kind"] == "AUTHENTICITY_CONFIDENCE"
                and row.get("candidate_id") == candidate.candidate_id
                for row in self.controller.repos.list_scores(search_id)
            ):
                continue
            pngs = self._candidate_pngs(search_id, candidate)
            enriched = enrich_candidate(candidate, pngs, ledger=ledger)
            record = assess_authenticity(
                hypothesis=hypothesis,
                candidate=enriched,
                reference_descriptors=ref_desc,
                constraints=intent.constraints,
                ledger=ledger,
                deep=False,
            )
            interval = record.authenticity_distribution
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
            self.controller.store_receipt(
                AuthenticityDecisionReceipt(
                    search_id=search_id,
                    candidate_id=candidate.candidate_id,
                    authority_ceiling=record.authority_ceiling,
                ).seal()
            )

    def _live(self, search_id: str) -> None:
        candidates = self._candidates_for_match(search_id)
        if not candidates:
            return
        updated = candidates
        if self.engine is not None:
            try:
                updated = self.engine.live_check_all(search_id, candidates)
            except BudgetExceeded:
                self.blocked_lanes["live_check"] = "budget exhausted during live check"
                listed = self.controller.repos.list_candidates(search_id)
                by_id = {item.candidate_id: item for item in listed}
                updated = [by_id.get(item.candidate_id, item) for item in candidates]
            except Exception as exc:
                self.blocked_lanes["live_check"] = str(exc)
                updated = candidates
            if "live_check" not in self.blocked_lanes:
                try:
                    updated = self.engine.verify_all(search_id, updated)
                except BudgetExceeded:
                    self.blocked_lanes["verification"] = (
                        "budget exhausted during listing verification"
                    )
                except Exception as exc:
                    self.blocked_lanes["verification"] = str(exc)
        now = utc_now()
        for candidate in updated:
            live = candidate.availability is Availability.LIVE
            dest = live and candidate.availability is Availability.LIVE
            self._destination_attested[candidate.candidate_id] = _from_index_feed(candidate)
            self._destination_verified[candidate.candidate_id] = dest
            utility = listing_utility(candidate, destination_verified=dest)
            if not any(
                row["kind"] == "LISTING_UTILITY"
                and row.get("candidate_id") == candidate.candidate_id
                for row in self.controller.repos.list_scores(search_id)
            ):
                self.controller.repos.insert_score(
                    search_id,
                    new_id(),
                    "LISTING_UTILITY",
                    utility.utility_score,
                    1.0 if live else 0.0,
                    1.0 if live else 0.0,
                    utility.model_dump(mode="json"),
                    candidate_id=candidate.candidate_id,
                )
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_UPDATED.value,
                payload={"candidate_id": candidate.candidate_id},
                actor="orchestrator",
            )
        self.controller.store_receipt(
            LiveCheckReceipt(
                search_id=search_id,
                result_ids=[item.candidate_id for item in updated],
                refreshed=self.engine is not None and "live_check" not in self.blocked_lanes,
                reason="live check of discovered listings",
            ).seal()
        )
        self.controller.set_runtime(
            search_id,
            destination_verified=self._destination_verified,
            destination_attested=self._destination_attested,
        )
        del now

    def _score_payloads(
        self, search_id: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        match: dict[str, Any] = {}
        auth: dict[str, Any] = {}
        util: dict[str, Any] = {}
        for row in self.controller.repos.list_scores(search_id):
            cid = row.get("candidate_id")
            if not cid:
                continue
            kind = row["kind"]
            if kind == "ITEM_MATCH":
                finer = "match_evidence_id" in str(row.get("payload_json") or "")
                if cid not in match or finer:
                    match[str(cid)] = row
            elif kind == "AUTHENTICITY_CONFIDENCE":
                auth[str(cid)] = row
            elif kind == "LISTING_UTILITY":
                util[str(cid)] = row
        return match, auth, util

    def _rank(self, search_id: str) -> None:
        if self.controller.repos.list_decisions(search_id):
            return
        candidates = self._candidates_for_match(search_id) or self.controller.repos.list_candidates(
            search_id
        )
        if not candidates:
            return
        try:
            from searcher.contracts.models import AuthenticityEvidence, MatchEvidence
            from searcher.ranking.buckets import route_candidate
            from searcher.ranking.order import rank_tab
            from searcher.ranking.policy_versions import load_policy
            from searcher.verification.runner import merge_verification
        except Exception as exc:
            self.blocked_lanes["ranking"] = str(exc)
            return
        import json

        match_rows, auth_rows, util_rows = self._score_payloads(search_id)
        policy = load_policy("matching-1")
        intent = self.controller.repos.get_intent(search_id)
        runtime = self.controller.repos.get_runtime(search_id)
        dest_map = dict(runtime.get("destination_verified") or self._destination_verified)
        attested_map = dict(
            runtime.get("destination_attested") or self._destination_attested
        )
        utilities: dict[str, ListingUtility] = {}
        for candidate in candidates:
            match_row = match_rows.get(candidate.candidate_id)
            auth_row = auth_rows.get(candidate.candidate_id)
            if match_row is None or auth_row is None:
                continue
            try:
                match = MatchEvidence.model_validate(json.loads(str(match_row["payload_json"])))
            except Exception:
                continue
            try:
                raw_auth = json.loads(str(auth_row["payload_json"]))
                auth = AuthenticityEvidence.model_validate(raw_auth)
            except Exception:
                continue
            dest = bool(dest_map.get(candidate.candidate_id, False))
            utility = listing_utility(
                candidate, constraints=intent.constraints, destination_verified=dest
            )
            utilities[candidate.candidate_id] = utility
            live_checked = candidate.candidate_id in dest_map or utility.live
            complete = 0.4 if candidate.images else 0.15
            complete = min(complete, 0.35) if auth.missing_evidence else max(complete, 0.2)
            if candidate.images:
                complete = min(1.0, complete + 0.15 * min(3, len(candidate.images)))
            decision = route_candidate(
                candidate=candidate,
                match=match,
                authenticity=auth,
                utility=utility,
                completeness_value=complete,
                constraints=intent.constraints,
                destination_verified=dest,
                destination_attested=bool(attested_map.get(candidate.candidate_id, False)),
                policy=policy,
                live_checked=live_checked,
            )
            decision = merge_verification(decision, candidate)
            self.controller.repos.insert_decision(search_id, new_id(), decision)
            self.controller.store_receipt(
                BucketDecisionReceipt(
                    search_id=search_id,
                    candidate_id=decision.candidate_id,
                    internal=decision.decision.internal.value,
                    public=decision.decision.public.value,
                    policy_version=decision.policy_version,
                ).seal()
            )
        if utilities:
            from searcher.contracts.enums import BucketPublic

            rank_tab(
                public=BucketPublic.REAL,
                decisions=self.controller.repos.list_decisions(search_id),
                utilities=utilities,
                weights=policy.ranking,
            )
            rank_tab(
                public=BucketPublic.POSSIBLY_REAL,
                decisions=self.controller.repos.list_decisions(search_id),
                utilities=utilities,
                weights=policy.ranking,
            )

    def _publish(self, search_id: str) -> None:
        if self.controller.repos.list_results(search_id):
            return
        hidden = 0
        for decision in self.controller.repos.list_decisions(search_id):
            result_id = new_id()
            candidate = self.controller.repos.get_candidate(search_id, decision.candidate_id)
            public = published_public_bucket(decision, candidate)
            payload = decision.model_dump(mode="json")
            payload["public_bucket"] = public
            self.controller.repos.insert_result(
                search_id,
                result_id,
                decision.candidate_id,
                public,
                payload,
            )
            name = event_name_for_public_bucket(public)
            if name == PublicEventName.RESULT_REMOVED.value:
                hidden += 1
            self.controller.emit(
                search_id,
                name,
                payload={"candidate_id": decision.candidate_id, "result_id": result_id},
                actor="orchestrator",
            )
        counts = {"real": 0, "possibly_real": 0, "hidden": hidden}
        for row in self.controller.repos.list_results(search_id):
            bucket = str(row["public_bucket"])
            if bucket in counts:
                counts[bucket] += 1
        runtime = self.controller.repos.get_runtime(search_id)
        coverage = runtime.get("coverage")
        if isinstance(coverage, dict):
            coverage = dict(coverage)
            coverage["candidates_hidden"] = counts["hidden"]
            self.controller.set_runtime(search_id, coverage=coverage, counts=counts)
        else:
            self.controller.set_runtime(search_id, counts=counts)

    def _gaps(self, search_id: str) -> None:
        analysis = self._analysis(search_id)
        missing: list[dict[str, str]] = []
        if analysis is not None:
            from searcher.reference.gaps import evidence_gaps

            # Ask for the views this kind of thing actually has. A garment has
            # no sole to photograph, and requesting one guarantees the part
            # evidence behind it never arrives.
            hypothesis = self._primary_hypothesis(search_id)
            category = getattr(hypothesis, "category", None) if hypothesis else None
            for gap in evidence_gaps(analysis, category=category):
                if not gap.gap.startswith("missing_"):
                    continue
                missing.append({"view": gap.gap.removeprefix("missing_"), "why": gap.impact})
                if len(missing) >= 3:
                    break
        self.controller.set_runtime(search_id, missing_reference_views=missing)
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_PROGRESS.value,
            payload={
                "stage": "Searching alternate names",
                "detail": None,
                "phase": "gap_analysis",
                "replans": self.round - 1,
            },
            actor="orchestrator",
        )

    def _learn_terms(self, search_id: str) -> tuple[list[str], list[str]]:
        stored = self.controller.repos.list_decisions(search_id)
        decisions = {item.candidate_id: item for item in stored}
        by_alias: dict[str, list[AliasEvidence]] = defaultdict(list)
        codes: list[str] = []
        for candidate in self.controller.repos.list_candidates(search_id):
            title = str(candidate.title.value) if candidate.title and candidate.title.value else ""
            desc = (
                str(candidate.description.value)
                if candidate.description and candidate.description.value
                else ""
            )
            blob = f"{title} {desc}"
            if self_declared_replica(blob):
                continue
            decision = decisions.get(candidate.candidate_id)
            if decision is not None and decision.hard_vetoes:
                continue
            family = candidate.source_adapter or "listing"
            if title:
                by_alias[normalize_query_text(title)].append(
                    AliasEvidence(
                        alias=title.strip(),
                        source_family=family,
                        authority="listing",
                        confidence=0.45,
                    )
                )
            model = (
                str(candidate.seller_reported_model.value)
                if candidate.seller_reported_model and candidate.seller_reported_model.value
                else ""
            )
            if model:
                reading = assess_code(
                    model,
                    region_level_ocr=False,
                    structured_source=True,
                    consistent_across_candidates=False,
                )
                if reading.promotable:
                    codes.append(reading.normalized)
            for token in tokenize(title):
                if len(token) < 4:
                    continue
                reading = assess_code(
                    token,
                    region_level_ocr=False,
                    structured_source=bool(candidate.structured_data),
                    consistent_across_candidates=False,
                )
                if reading.promotable:
                    codes.append(reading.normalized)
        promoted: list[str] = []
        hypothesis = self._primary_hypothesis(search_id)
        for evidence in by_alias.values():
            if not can_promote_alias(evidence):
                continue
            belief = promote_or_hold(evidence)
            if belief is None:
                continue
            promoted.append(belief.alias)
            if hypothesis is not None:
                aliases = list(hypothesis.aliases) + [belief]
                hypothesis = hypothesis.model_copy(update={"aliases": aliases})
        if hypothesis is not None:
            self.controller.repos.upsert_hypothesis(hypothesis)
        return promoted, list(dict.fromkeys(codes))

    def _replan(self, search_id: str) -> bool:
        if self.round >= self.max_rounds:
            return False
        if self._should_stop(search_id):
            return False
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state):
            return False
        aliases, codes = self._learn_terms(search_id)
        if not aliases and not codes:
            return False
        analysis = self._analysis(search_id)
        hypotheses = self.controller.repos.list_hypotheses(search_id)
        prior = self.controller.repos.list_queries(search_id)
        new_queries = compile_queries(
            hypotheses,
            analysis,
            ceiling=self.controller.settings.query_ceiling,
            prior=prior,
            product_codes=codes or None,
        )
        existing = {normalize_query_text(item.query_text) for item in prior}
        added: list[QueryVariant] = []
        for query in new_queries:
            key = normalize_query_text(query.query_text)
            if key in existing:
                continue
            self.controller.repos.upsert_query(search_id, query)
            added.append(query)
            existing.add(key)
        if not added:
            return False
        self._enter(search_id, CampaignState.REPLANNING)
        self._progress(search_id, STAGE_LANGUAGE[CampaignState.REPLANNING.value])
        languages = sorted({item.language for item in added})
        families = sorted({item.family for item in added if item.family})
        self.controller.store_receipt(
            QueryPlanReceipt(
                search_id=search_id,
                query_ids=[item.query_id for item in added],
                languages=languages,
                families=families,
                max_round=max((item.round for item in added), default=self.round + 1),
                query_count=len(added),
            ).seal()
        )
        completed = [step for step in self._completed(search_id) if step == REFERENCE_DONE]
        self.controller.set_runtime(
            search_id,
            completed_steps=completed,
            query_ids=[item.query_id for item in self.controller.repos.list_queries(search_id)],
        )
        self._finish_stage(search_id, CampaignState.REPLANNING)
        self._enter(search_id, CampaignState.DISCOVERING)
        return True

    def _pages_charged(self, search_id: str) -> int | None:
        """HTTP pages charged against the campaign page limit, or None."""
        usage = self.controller.repos.get_budget_usage(search_id)
        if not isinstance(usage, dict):
            return None
        used = usage.get("used")
        if isinstance(used, dict) and "pages" in used:
            try:
                return int(used["pages"])
            except (TypeError, ValueError):
                return None
        return None

    def _coverage_map(self, search_id: str) -> dict[str, Any]:
        raw = self.controller.repos.get_runtime(search_id).get("coverage")
        return raw if isinstance(raw, dict) else {}

    def _public_counts(self, search_id: str) -> dict[str, int]:
        counts = {"real": 0, "possibly_real": 0, "hidden": 0}
        for row in self.controller.repos.list_results(search_id):
            bucket = str(row["public_bucket"])
            if bucket in counts:
                counts[bucket] += 1
        return counts

    def _cluster_count(self, search_id: str) -> int:
        families = {
            item.cluster_id or item.candidate_id
            for item in self.controller.repos.list_candidates(search_id)
        }
        return len(families)

    def _should_stop(self, search_id: str) -> bool:
        counts = self._public_counts(search_id)
        usage = self.controller.usage(search_id)
        if usage.would_exceed(pages=1) is not None or usage.would_exceed(sources=1) is not None:
            return True
        if counts["real"] >= self.controller.settings.saturation_real:
            return True
        runtime = self.controller.repos.get_runtime(search_id)
        previous = int(runtime.get("cluster_count") or 0)
        current = self._cluster_count(search_id)
        self.controller.set_runtime(search_id, cluster_count=current)
        return bool(self.round > 1 and current <= previous)

    def _salvage_publish(self, search_id: str) -> None:
        """Rank and publish whatever scores exist so a budget stop is PARTIAL, not empty."""
        if is_terminal(self.controller.get(search_id).state):
            return
        try:
            if not self.controller.repos.list_decisions(search_id):
                self._rank(search_id)
            if self.controller.repos.list_decisions(
                search_id
            ) and not self.controller.repos.list_results(search_id):
                self._publish(search_id)
        except Exception:
            return

    def _wall_exceeded(self, search_id: str) -> bool:
        if not self._started:
            return False
        elapsed = time.monotonic() - self._started
        ceiling = int(self.controller.usage(search_id).sealed.ceiling("wall_seconds"))
        return elapsed >= float(ceiling)

    def _charge_wall(self, search_id: str) -> None:
        if not self._started:
            return
        elapsed = max(0, int(time.monotonic() - self._started))
        if elapsed <= 0:
            return
        usage = self.controller.usage(search_id)
        already = int(usage.used("wall_seconds"))
        ceiling = int(usage.sealed.ceiling("wall_seconds"))
        remaining = max(0, ceiling - already)
        if remaining:
            usage.consume(wall_seconds=min(elapsed, remaining))
            self.controller.persist_usage(search_id)

    def _exhaustion(
        self, search_id: str, *, reason: str, saturation: bool
    ) -> SearchExhaustionReceipt:
        queries = self.controller.repos.list_queries(search_id)
        hyps = self.controller.repos.list_hypotheses(search_id)
        runs = self.controller.repos.list_source_runs(search_id)
        pages = self.controller.repos.list_discovery_pages(search_id)
        candidates = self.controller.repos.list_candidates(search_id)
        usage = self.controller.usage(search_id)
        snap = usage.snapshot()["committed"]
        runtime = self.controller.repos.get_runtime(search_id)
        coverage = self._coverage_map(search_id)
        blocked = [
            str(item.get("id") or "")
            for item in (coverage.get("sources_blocked") or [])
            if isinstance(item, dict)
        ]
        completed = [
            str(item.get("id") or "")
            for item in (coverage.get("sources_completed") or [])
            if isinstance(item, dict)
        ]
        if not blocked and not completed:
            for run in runs:
                source_id = str(run.get("source_id") or "")
                outcome = str(run.get("last_outcome") or "")
                if "BLOCK" in outcome or outcome in {"AUTH_REQUIRED", "SOURCE_UNAVAILABLE"}:
                    blocked.append(source_id)
                else:
                    completed.append(source_id)
        families = sorted({item.family for item in queries if item.family})
        languages = sorted({item.language for item in queries})
        fine = sum(
            1
            for row in self.controller.repos.list_scores(search_id)
            if row["kind"] == "ITEM_MATCH"
            and "match_evidence_id" in str(row.get("payload_json") or "")
        )
        last = self._learn_unresolved(search_id)
        receipt = SearchExhaustionReceipt(
            search_id=search_id,
            reason=reason,
            saturation=saturation,
            queries_exhausted=sum(1 for item in queries if item.status is QueryStatus.EXHAUSTED)
            or len(queries),
            sources_covered=len(completed),
            hypotheses_searched=len(hyps),
            query_families=families,
            languages=languages,
            sources_admitted=[str(run.get("source_id") or "") for run in runs],
            sources_completed=completed,
            sources_blocked=blocked,
            pages_fetched=len(pages),
            candidates_normalized=len(candidates),
            duplicates_removed=max(
                0, int((runtime.get("last_discovery") or {}).get("before") or 0) - len(candidates)
            ),
            candidates_finely_compared=fine,
            model_calls=int(snap.get("model_calls") or 0),
            bytes=int(snap.get("bytes") or 0),
            retries=int(snap.get("retries") or 0),
            unresolved_evidence=last,
        ).seal()
        self.controller.store_receipt(receipt)
        self.controller.set_runtime(search_id, exhaustion_receipt=receipt.receipt_id)
        return receipt

    def _learn_unresolved(self, search_id: str) -> list[str]:
        runtime = self.controller.repos.get_runtime(search_id)
        missing = runtime.get("missing_reference_views") or []
        out: list[str] = []
        if isinstance(missing, list):
            for item in missing:
                if isinstance(item, dict) and item.get("view"):
                    out.append(str(item["view"]))
        out.extend(self.blocked_lanes.keys())
        return out[:8]

    def _choose_terminal(
        self, search_id: str, *, forced: CampaignState | None
    ) -> tuple[CampaignState, str, bool]:
        if forced is not None:
            reason = "budget exhausted" if forced is CampaignState.PARTIAL else forced.value
            return forced, reason, False
        counts = self._public_counts(search_id)
        coverage = self._coverage_map(search_id)
        blocked = list(coverage.get("sources_blocked") or [])
        completed = list(coverage.get("sources_completed") or [])
        candidates = self.controller.repos.list_candidates(search_id)
        discovery_blocked = "discovery" in self.blocked_lanes
        if discovery_blocked and not candidates:
            return (
                CampaignState.BLOCKED,
                self.blocked_lanes["discovery"],
                False,
            )
        if counts["real"] >= self.controller.settings.saturation_real:
            return CampaignState.COMPLETE, "success saturation", True
        if blocked and not completed and not candidates:
            return CampaignState.BLOCKED, "admitted sources were blocked or unavailable", False
        if blocked and (counts["real"] or counts["possibly_real"] or candidates):
            return (
                CampaignState.PARTIAL,
                "useful coverage remains incomplete; some sources blocked",
                False,
            )
        if self.blocked_lanes and (counts["real"] or counts["possibly_real"]):
            return (
                CampaignState.PARTIAL,
                "one or more lanes degraded; results are incomplete",
                False,
            )
        if self.blocked_lanes and not candidates:
            return CampaignState.BLOCKED, next(iter(self.blocked_lanes.values())), False
        # COMPLETE means planned coverage was searched and exhausted.
        # An empty campaign is not exhaustion — name what was missing.
        queries = self.controller.repos.list_queries(search_id)
        usable = [item for item in queries if str(item.query_text or "").strip()]
        pages_fetched = int(coverage.get("pages_fetched") or 0)
        if not queries or not usable:
            return CampaignState.BLOCKED, "no usable query was compiled", False
        if not completed and not blocked:
            return CampaignState.BLOCKED, "no source work was planned", False
        # A source that timed out, hung, looped or returned unparseable content
        # did not answer, and a campaign carrying one has not exhausted its
        # coverage. Fault injection found COMPLETE returned after all four.
        # Coverage rows are dicts on the live path and bare source names on
        # others. Assuming the dict shape crashed the terminal decision with
        # AttributeError on a str, which turns an honest status into a 500.
        outcomes: dict[str, str] = {}
        for row in list(coverage.get("sources_completed") or []) + blocked:
            if isinstance(row, dict):
                name = str(row.get("id") or "")
                if name:
                    outcomes[name] = str(row.get("status") or "")
            elif isinstance(row, str) and row:
                # A bare name carries no outcome, so it cannot be judged
                # unresolved and must not silently force PARTIAL.
                outcomes.setdefault(row, "")
        verdict = published_terminal_status(
            proposed=CampaignState.COMPLETE.value,
            pages_fetched=pages_fetched,
            candidate_count=len(candidates),
            queries_compiled=len(usable),
            source_outcomes=outcomes or None,
        )
        if verdict == CampaignState.PARTIAL.value:
            return (
                CampaignState.PARTIAL,
                "a planned source did not answer; coverage is incomplete",
                False,
            )
        if verdict != CampaignState.COMPLETE.value:
            return CampaignState.BLOCKED, "nothing was fetched", False
        return CampaignState.COMPLETE, "coverage exhausted", False

    def _terminate(
        self,
        search_id: str,
        *,
        forced: CampaignState | None = None,
        reason: str | None = None,
    ) -> None:
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state):
            return
        self._charge_wall(search_id)
        for query in self.controller.repos.list_queries(search_id):
            if query.status in {QueryStatus.QUEUED, QueryStatus.RUNNING}:
                self.controller.repos.upsert_query(
                    search_id, query.model_copy(update={"status": QueryStatus.EXHAUSTED})
                )
        target, chosen_reason, saturation = self._choose_terminal(search_id, forced=forced)
        if reason:
            chosen_reason = reason
        receipt = self._exhaustion(search_id, reason=chosen_reason, saturation=saturation)
        ctx = self.controller.context_from_disk(search_id)
        ctx.exhaustion_receipt = receipt.receipt_id
        ctx.reason = chosen_reason
        if saturation:
            ctx.saturation_receipt = receipt.receipt_id
        if target is CampaignState.FAILED:
            ctx.error_class = ErrorClass.INTERNAL_INVARIANT
        updated = self.controller.transition(search_id, target, context=ctx, actor="orchestrator")
        terminal = CampaignTerminalReceipt(
            search_id=search_id,
            terminal_status=target.value,
            terminal_reason=chosen_reason,
            state_version=updated.state_version,
            predecessor=receipt.receipt_id,
        ).seal()
        self.controller.store_receipt(terminal)
        self.controller.checkpoint(search_id, "terminal", {"reason": chosen_reason})
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_COMPLETE.value,
            payload={"terminal_status": target.value, "reason": chosen_reason},
            actor="orchestrator",
        )

    def _fail(self, search_id: str, exc: Exception) -> None:
        campaign = self.controller.get(search_id)
        if is_terminal(campaign.state):
            return
        reason = "The search failed because of an internal error. This is not a no-results outcome."
        ctx = self.controller.context_from_disk(search_id)
        ctx.error_class = ErrorClass.INTERNAL_INVARIANT
        ctx.reason = reason
        try:
            updated = self.controller.transition(
                search_id, CampaignState.FAILED, context=ctx, actor="orchestrator"
            )
        except SearcherError:
            return
        self.controller.emit(
            search_id,
            PublicEventName.SEARCH_COMPLETE.value,
            payload={"terminal_status": CampaignState.FAILED.value, "reason": reason},
            actor="orchestrator",
        )
        del exc, updated
