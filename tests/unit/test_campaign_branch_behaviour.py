"""Campaign branches exist to name an outcome, not to execute a line.

These tests pin the uncovered guards: what a campaign may claim when it
stops, what it may publish, and what a repeated or cancelled write must
not do.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from searcher.campaigns.cancellation import CancellationController
from searcher.campaigns.checkpoints import checkpoint_label_for
from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import (
    CampaignEvent,
    event_chain_ok,
    is_public_event,
    numbered_public_events,
)
from searcher.campaigns.models import EvidencePacket, TransitionContext
from searcher.campaigns.orchestrator import (
    CampaignOrchestrator,
    _from_index_feed,
    _looks_like_image,
    layers_present,
    select_kept_ids,
)
from searcher.campaigns.publication import (
    event_name_for_public_bucket,
    is_replica_result,
    published_public_bucket,
    published_terminal_status,
)
from searcher.campaigns.resume import reconstruct
from searcher.campaigns.states import is_terminal, terminal_verdict_for
from searcher.campaigns.transitions import assert_invariants, legal_targets
from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    CampaignState,
    FactClass,
    FactOrigin,
    PublicEventName,
    TerminalVerdict,
)
from searcher.contracts.models import (
    BucketDecision,
    BucketDecisionFields,
    IntentBudget,
    ListingCandidate,
    ListingImage,
    PrivacySettings,
    SearchConstraints,
    SearchIntent,
)
from searcher.contracts.primitives import classified
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.core.errors import CancelledError, ErrorClass, IdempotencyConflict, InvariantViolation
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.evidence.content_store import ContentStore
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA
from searcher.sources.families import REPLICA_SOURCE_REASON
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _intent(search_id: str | None = None) -> SearchIntent:
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


def _controller(tmp_path: Path) -> CampaignController:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    return CampaignController(database, store, settings)


def _candidate(
    *,
    source_adapter: str = "kind",
    title: str = "Dior Homme trainer",
    description: str = "Used, original box.",
    url: str = "https://shop.example/products/1",
    structured_data: dict[str, object] | None = None,
) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url,
        source_adapter=source_adapter,
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(description, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
        structured_data=structured_data or {},
    )


def _decision(
    candidate_id: str,
    *,
    public: BucketPublic,
    hard_vetoes: list[str] | None = None,
    reason_codes: list[str] | None = None,
) -> BucketDecision:
    return BucketDecision(
        candidate_id=candidate_id,
        decision=BucketDecisionFields(internal=BucketInternal.REAL, public=public),
        policy_version="matching-1",
        item_match_lower_bound=0.95,
        authenticity_lower_bound=0.90,
        evidence_completeness=0.80,
        hard_vetoes=hard_vetoes or [],
        reason_codes=reason_codes or [],
    )


# --- image bytes and the fine-compare keep set --------------------------------


def test_only_real_image_bytes_count_as_an_image() -> None:
    png = b"\x89PNG" + b"\x00" * 8
    jpeg = b"\xff\xd8\xff" + b"\x00" * 8
    gif = b"GIF89a" + b"\x00" * 8
    webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00"
    html = b"<html>not an image</html>"
    short_riff = b"RIFFWEBP"
    assert _looks_like_image(png) is True
    assert _looks_like_image(jpeg) is True
    assert _looks_like_image(gif) is True
    assert _looks_like_image(webp) is True
    assert _looks_like_image(html) is False
    assert _looks_like_image(short_riff) is False
    assert _looks_like_image(b"") is False


def test_fine_compare_keep_set_is_capped_and_skips_empty_ids() -> None:
    kept = select_kept_ids(["r1", "", "r2", "r1"], ["r2", "a", "b", "c"], cap=3)
    assert kept == ["r1", "r2", "a"]
    assert len(kept) <= 3
    assert "" not in kept
    assert select_kept_ids([], [], cap=8) == []


def test_index_feed_flag_is_read_from_the_structured_raw_dict() -> None:
    assert _from_index_feed(object()) is False
    assert _from_index_feed(SimpleNamespace(structured_data="not-a-dict")) is False
    assert _from_index_feed(SimpleNamespace(structured_data={"raw": "string"})) is False
    assert _from_index_feed(SimpleNamespace(structured_data={"raw": {}})) is False
    flagged = SimpleNamespace(structured_data={"raw": {"from_index_feed": True}})
    assert _from_index_feed(flagged) is True


def test_present_layers_are_named_rather_than_assumed() -> None:
    present = layers_present()
    assert set(present) == {"discovery", "routing"}
    assert all(isinstance(flag, bool) for flag in present.values())


# --- terminal claims ----------------------------------------------------------


def test_only_terminal_states_have_a_verdict() -> None:
    assert terminal_verdict_for(CampaignState.COMPLETE) is TerminalVerdict.COMPLETE
    assert terminal_verdict_for(CampaignState.PARTIAL) is TerminalVerdict.PARTIAL
    assert terminal_verdict_for(CampaignState.BLOCKED) is TerminalVerdict.BLOCKED
    assert terminal_verdict_for(CampaignState.FAILED) is TerminalVerdict.FAILED
    assert terminal_verdict_for(CampaignState.CANCELLED) is TerminalVerdict.CANCELLED
    assert terminal_verdict_for(CampaignState.CREATED) is None
    assert terminal_verdict_for(CampaignState.DISCOVERING) is None
    assert is_terminal(CampaignState.CREATED) is False
    assert is_terminal(CampaignState.BLOCKED) is True
    assert legal_targets(CampaignState.COMPLETE) == frozenset()


def test_complete_is_refused_when_nothing_was_fetched() -> None:
    assert (
        published_terminal_status(
            proposed=CampaignState.PARTIAL.value,
            pages_fetched=0,
            candidate_count=0,
        )
        == CampaignState.PARTIAL.value
    )
    assert (
        published_terminal_status(
            proposed=CampaignState.COMPLETE.value,
            pages_fetched=0,
            candidate_count=0,
            saturation=True,
        )
        == CampaignState.COMPLETE.value
    )
    assert (
        published_terminal_status(
            proposed=CampaignState.COMPLETE.value,
            pages_fetched=4,
            candidate_count=0,
            queries_compiled=0,
        )
        == CampaignState.BLOCKED.value
    )
    assert (
        published_terminal_status(
            proposed=CampaignState.COMPLETE.value,
            pages_fetched=0,
            candidate_count=0,
            queries_compiled=3,
        )
        == CampaignState.BLOCKED.value
    )
    assert (
        published_terminal_status(
            proposed=CampaignState.COMPLETE.value,
            pages_fetched=2,
            candidate_count=1,
            queries_compiled=3,
        )
        == CampaignState.COMPLETE.value
    )


def test_public_bucket_events_are_named_from_the_published_list() -> None:
    assert event_name_for_public_bucket(BucketPublic.REAL.value) == (
        PublicEventName.RESULT_REAL.value
    )
    assert event_name_for_public_bucket(BucketPublic.POSSIBLY_REAL.value) == (
        PublicEventName.RESULT_POSSIBLY_REAL.value
    )
    assert event_name_for_public_bucket(BucketPublic.REPLICA.value) == (
        PublicEventName.RESULT_REPLICA.value
    )
    assert event_name_for_public_bucket(BucketPublic.HIDDEN.value) == (
        PublicEventName.RESULT_REMOVED.value
    )
    assert event_name_for_public_bucket("unknown") == PublicEventName.RESULT_REMOVED.value


def test_a_self_declared_or_replica_family_listing_never_enters_real() -> None:
    replica = _candidate(source_adapter="yupoo")
    declared = _candidate(description="This is a replica of the 2007 trainer.")
    vetoed = _candidate()
    coded = _candidate()
    ordinary = _candidate()
    assert is_replica_result(replica, _decision(replica.candidate_id, public=BucketPublic.REAL))
    assert is_replica_result(declared, _decision(declared.candidate_id, public=BucketPublic.REAL))
    assert is_replica_result(
        vetoed,
        _decision(
            vetoed.candidate_id,
            public=BucketPublic.HIDDEN,
            hard_vetoes=[SELF_DECLARED_REPLICA],
        ),
    )
    assert is_replica_result(
        coded,
        _decision(
            coded.candidate_id,
            public=BucketPublic.REAL,
            reason_codes=[REPLICA_SOURCE_REASON],
        ),
    )
    honest = _decision(
        ordinary.candidate_id,
        public=BucketPublic.REAL,
        reason_codes=["real-gate"],
    )
    assert is_replica_result(ordinary, honest) is False
    assert published_public_bucket(honest, ordinary) == BucketPublic.REAL.value
    assert published_public_bucket(
        _decision(replica.candidate_id, public=BucketPublic.REAL, reason_codes=["real-gate"]),
        replica,
    ) == BucketPublic.REPLICA.value


def test_discovering_may_start_from_a_visual_without_a_query() -> None:
    assert_invariants(
        CampaignState.PLANNING_SOURCES,
        CampaignState.DISCOVERING,
        TransitionContext(has_visual_representation=True),
    )
    assert_invariants(
        CampaignState.GAP_ANALYSIS,
        CampaignState.COMPLETE,
        TransitionContext(saturation_receipt="sat-1"),
    )
    assert_invariants(
        CampaignState.DISCOVERING,
        CampaignState.FAILED,
        TransitionContext(error_class=ErrorClass.DATABASE, reason="disk full"),
    )
    with pytest.raises(InvariantViolation, match="seller text"):
        assert_invariants(
            CampaignState.FINE_MATCHING,
            CampaignState.AUTHENTICITY_REVIEW,
            TransitionContext(seller_text_only=True, has_visual_or_normalized_evidence=True),
        )


# --- cancellation and the event chain -----------------------------------------


def test_a_cancelled_campaign_raises_and_does_not_sleep_on_zero_cleanup() -> None:
    ctl = CancellationController()
    sid = "search-1"
    assert ctl.is_cancelled(sid) is False
    ctl.request(sid)
    assert ctl.is_cancelled(sid) is True
    with pytest.raises(CancelledError):
        ctl.raise_if_cancelled(sid)
    ctl.bounded_cleanup(0)
    assert ctl.terminal_for() == (CampaignState.CANCELLED, TerminalVerdict.CANCELLED)


def test_public_event_sequence_skips_private_names_and_honours_after() -> None:
    assert is_public_event(PublicEventName.SEARCH_STATE.value) is True
    assert is_public_event("internal.worker.debug") is False
    assert event_chain_ok([]) is True
    first = CampaignEvent(
        search_id="s",
        state_version=0,
        actor="t",
        event_name=PublicEventName.SEARCH_STATE.value,
        predecessor=None,
    )
    broken = CampaignEvent(
        search_id="s",
        state_version=1,
        actor="t",
        event_name=PublicEventName.SEARCH_PROGRESS.value,
        predecessor="not-the-first",
    )
    assert event_chain_ok([first, broken]) is False


def test_numbered_public_events_are_campaign_local_and_1_based(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    controller.emit(intent.search_id, "internal.debug", payload={"n": 0})
    controller.emit(
        intent.search_id, PublicEventName.SEARCH_PROGRESS.value, payload={"n": 1}
    )
    numbered = numbered_public_events(controller.repos, intent.search_id)
    assert numbered
    assert numbered[0][0] == 1
    names = [event.event_name for _, event in numbered]
    assert "internal.debug" not in names
    assert PublicEventName.SEARCH_STATE.value in names
    after_first = numbered_public_events(controller.repos, intent.search_id, after=1)
    assert all(seq > 1 for seq, _ in after_first)


def test_created_has_no_checkpoint_label() -> None:
    assert checkpoint_label_for(CampaignState.CREATED) is None
    assert checkpoint_label_for(CampaignState.DISCOVERING) == "source_batch"


def test_reconstruct_names_a_missing_campaign() -> None:
    class _Empty:
        def get_campaign(self, search_id: str) -> None:
            del search_id
            return None

    with pytest.raises(KeyError):
        reconstruct(_Empty(), "missing")  # type: ignore[arg-type]


def test_campaigns_package_exports_the_orchestrator_lazily() -> None:
    import searcher.campaigns as campaigns

    loaded = campaigns.CampaignOrchestrator
    assert loaded is CampaignOrchestrator
    with pytest.raises(AttributeError, match="not_a_symbol"):
        campaigns.__getattr__("not_a_symbol")


# --- orchestrator stop and terminal choice ------------------------------------


class _FakeUsage:
    def __init__(self, *, pages: bool = False, sources: bool = False, wall: int = 60) -> None:
        self._pages = pages
        self._sources = sources
        self.sealed = SimpleNamespace(ceiling=lambda name: wall if name == "wall_seconds" else 10)
        self._used = {"wall_seconds": 0}

    def would_exceed(self, **kwargs: int) -> str | None:
        if kwargs.get("pages") and self._pages:
            return "pages"
        if kwargs.get("sources") and self._sources:
            return "sources"
        return None

    def used(self, name: str) -> int:
        return int(self._used.get(name, 0))

    def consume(self, **kwargs: int) -> None:
        for key, value in kwargs.items():
            self._used[key] = self._used.get(key, 0) + int(value)

    def snapshot(self) -> dict[str, object]:
        return {"committed": dict(self._used)}


class _FakeRepos:
    def __init__(self) -> None:
        self.campaign = SimpleNamespace(
            state=CampaignState.CREATED,
            state_version=1,
            budget_used={},
            search_exhaustion_receipt=None,
            terminal_status=None,
            terminal_reason="",
        )
        self.runtime: dict[str, object] = {}
        self.deleted = False
        self.results: list[dict[str, object]] = []
        self.candidates: list[object] = []
        self.queries: list[object] = []
        self.hypotheses: list[object] = []
        self.runs: list[dict[str, object]] = []
        self.pages: list[object] = []
        self.decisions: list[object] = []
        self.evidence: list[object] = []
        self.scores: list[dict[str, object]] = []

    def get_campaign(self, search_id: str) -> object:
        del search_id
        return self.campaign

    def is_deleted(self, search_id: str) -> bool:
        del search_id
        return self.deleted

    def get_runtime(self, search_id: str) -> dict[str, object]:
        del search_id
        return self.runtime

    def list_results(self, search_id: str) -> list[dict[str, object]]:
        del search_id
        return self.results

    def list_candidates(self, search_id: str) -> list[object]:
        del search_id
        return self.candidates

    def list_queries(self, search_id: str) -> list[object]:
        del search_id
        return self.queries

    def list_hypotheses(self, search_id: str) -> list[object]:
        del search_id
        return self.hypotheses

    def list_source_runs(self, search_id: str) -> list[dict[str, object]]:
        del search_id
        return self.runs

    def list_discovery_pages(self, search_id: str) -> list[object]:
        del search_id
        return self.pages

    def list_decisions(self, search_id: str) -> list[object]:
        del search_id
        return self.decisions

    def list_evidence(self, search_id: str, accepted_only: bool = False) -> list[object]:
        del search_id, accepted_only
        return self.evidence

    def last_checkpoint(self, search_id: str) -> None:
        del search_id
        return None

    def get_budget_usage(self, search_id: str) -> None:
        del search_id
        return None

    def list_scores(self, search_id: str) -> list[dict[str, object]]:
        del search_id
        return self.scores

    def update_runtime(self, search_id: str, runtime: dict[str, object]) -> None:
        del search_id
        self.runtime = runtime


class _FakeController:
    def __init__(self) -> None:
        self.repos = _FakeRepos()
        self.settings = SimpleNamespace(saturation_real=3)
        self._usage = _FakeUsage()
        self.cancellation = CancellationController()

    def get(self, search_id: str) -> object:
        del search_id
        return self.repos.campaign

    def usage(self, search_id: str) -> _FakeUsage:
        del search_id
        return self._usage

    def persist_usage(self, search_id: str) -> None:
        del search_id

    def set_runtime(self, search_id: str, **fields: object) -> None:
        self.repos.runtime.update(fields)

    def context_from_disk(self, search_id: str) -> TransitionContext:
        del search_id
        return TransitionContext()

    def emit(self, search_id: str, event_name: str, **kwargs: object) -> None:
        del search_id, event_name, kwargs

    def transition(self, search_id: str, target: CampaignState, **kwargs: object) -> object:
        del kwargs
        self.repos.campaign.state = target
        return self.repos.campaign


def _orch(controller: _FakeController | None = None) -> CampaignOrchestrator:
    held = controller or _FakeController()
    orch = CampaignOrchestrator.__new__(CampaignOrchestrator)
    orch.controller = held  # type: ignore[assignment]
    orch.blocked_lanes = {}
    orch.round = 1
    orch._started = 0.0
    orch.engine = None
    orch.max_rounds = 2
    orch.max_work = 40
    orch.batch_size = 4
    orch.source_names = None
    orch._destination_verified = {}
    orch._destination_attested = {}
    orch._kept_ids = []
    return orch


def test_a_terminal_or_deleted_campaign_is_not_run_again() -> None:
    controller = _FakeController()
    controller.repos.campaign.state = CampaignState.COMPLETE
    CampaignOrchestrator(controller).run("s")  # type: ignore[arg-type]
    assert controller.repos.campaign.state is CampaignState.COMPLETE

    controller = _FakeController()
    controller.repos.deleted = True
    CampaignOrchestrator(controller).run("s")  # type: ignore[arg-type]
    assert controller.repos.campaign.state is CampaignState.CREATED


def test_forced_partial_is_budget_exhausted_not_coverage() -> None:
    orch = _orch()
    target, reason, saturation = orch._choose_terminal("s", forced=CampaignState.PARTIAL)
    assert target is CampaignState.PARTIAL
    assert reason == "budget exhausted"
    assert saturation is False


def test_discovery_blocked_with_no_candidates_is_blocked() -> None:
    orch = _orch()
    orch.blocked_lanes["discovery"] = "Discovery engine could not be imported."
    target, reason, saturation = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert "Discovery engine" in reason
    assert saturation is False


def test_enough_real_results_are_success_saturation() -> None:
    controller = _FakeController()
    controller.repos.results = [{"public_bucket": "real"} for _ in range(3)]
    orch = _orch(controller)
    target, reason, saturation = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.COMPLETE
    assert reason == "success saturation"
    assert saturation is True


def test_every_admitted_source_blocked_with_no_candidates_is_blocked() -> None:
    controller = _FakeController()
    controller.repos.runtime = {"coverage": {"sources_blocked": ["ebay"], "sources_completed": []}}
    orch = _orch(controller)
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert "blocked or unavailable" in reason


def test_blocked_sources_with_useful_results_are_partial() -> None:
    controller = _FakeController()
    controller.repos.runtime = {
        "coverage": {"sources_blocked": ["ebay"], "sources_completed": []}
    }
    controller.repos.candidates = [SimpleNamespace(cluster_id=None, candidate_id="c1")]
    orch = _orch(controller)
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.PARTIAL
    assert "incomplete" in reason


def test_a_degraded_lane_with_published_results_is_partial() -> None:
    controller = _FakeController()
    controller.repos.results = [{"public_bucket": "possibly_real"}]
    orch = _orch(controller)
    orch.blocked_lanes["routing"] = "ranking unavailable"
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.PARTIAL
    assert "degraded" in reason


def test_a_degraded_lane_with_no_candidates_is_blocked() -> None:
    orch = _orch()
    orch.blocked_lanes["routing"] = "ranking unavailable"
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert reason == "ranking unavailable"


def test_no_usable_query_cannot_claim_coverage() -> None:
    controller = _FakeController()
    controller.repos.queries = [SimpleNamespace(query_text="   ", family=None, language="en")]
    orch = _orch(controller)
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert reason == "no usable query was compiled"


def test_no_source_work_cannot_claim_coverage() -> None:
    controller = _FakeController()
    controller.repos.queries = [
        SimpleNamespace(query_text="dior homme trainer", family="name", language="en")
    ]
    orch = _orch(controller)
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert reason == "no source work was planned"


def test_compiled_queries_but_nothing_fetched_cannot_claim_complete() -> None:
    controller = _FakeController()
    controller.repos.queries = [
        SimpleNamespace(query_text="dior homme trainer", family="name", language="en")
    ]
    controller.repos.runtime = {
        "coverage": {"sources_completed": ["kind"], "sources_blocked": [], "pages_fetched": 0}
    }
    orch = _orch(controller)
    target, reason, _ = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.BLOCKED
    assert reason == "nothing was fetched"


def test_planned_coverage_that_fetched_pages_is_complete() -> None:
    controller = _FakeController()
    controller.repos.queries = [
        SimpleNamespace(query_text="dior homme trainer", family="name", language="en")
    ]
    controller.repos.candidates = [SimpleNamespace(cluster_id=None, candidate_id="c1")]
    controller.repos.runtime = {
        "coverage": {"sources_completed": ["kind"], "sources_blocked": [], "pages_fetched": 3}
    }
    orch = _orch(controller)
    target, reason, saturation = orch._choose_terminal("s", forced=None)
    assert target is CampaignState.COMPLETE
    assert reason == "coverage exhausted"
    assert saturation is False


def test_stop_when_the_page_or_source_budget_is_spent() -> None:
    controller = _FakeController()
    controller._usage = _FakeUsage(pages=True)
    assert _orch(controller)._should_stop("s") is True
    controller = _FakeController()
    controller._usage = _FakeUsage(sources=True)
    assert _orch(controller)._should_stop("s") is True


def test_stop_when_real_results_reach_saturation() -> None:
    controller = _FakeController()
    controller.repos.results = [{"public_bucket": "real"} for _ in range(3)]
    assert _orch(controller)._should_stop("s") is True


def test_a_later_round_stops_when_clusters_do_not_grow() -> None:
    controller = _FakeController()
    controller.repos.candidates = [
        SimpleNamespace(cluster_id="a", candidate_id="c1"),
        SimpleNamespace(cluster_id="a", candidate_id="c2"),
    ]
    controller.repos.runtime = {"cluster_count": 2}
    orch = _orch(controller)
    orch.round = 2
    assert orch._should_stop("s") is True
    orch.round = 1
    controller.repos.runtime = {"cluster_count": 2}
    assert orch._should_stop("s") is False


def test_coverage_map_ignores_a_non_dict_runtime_value() -> None:
    controller = _FakeController()
    controller.repos.runtime = {"coverage": "not-a-map"}
    assert _orch(controller)._coverage_map("s") == {}


def test_unresolved_views_and_blocked_lanes_are_listed() -> None:
    controller = _FakeController()
    controller.repos.runtime = {
        "missing_reference_views": [{"view": "outsole"}, "skip", {"view": "heel"}]
    }
    orch = _orch(controller)
    orch.blocked_lanes["discovery"] = "down"
    unresolved = orch._learn_unresolved("s")
    assert unresolved[:2] == ["outsole", "heel"]
    assert "discovery" in unresolved


def test_ui_coverage_separates_blocked_sources_and_counts_hidden_rows() -> None:
    controller = _FakeController()
    controller.repos.results = [
        {"public_bucket": "hidden"},
        {"public_bucket": "real"},
        {"public_bucket": "hidden"},
    ]
    orch = _orch(controller)
    summary = SimpleNamespace(
        coverage_details={},
        strategy_coverage={
            "kind": [{"name": "catalog_feed", "status": "tried", "reason": "", "yielded": 4}]
        },
    )
    coverage = orch._ui_coverage(
        "s",
        {
            "kind": "SEARCHED_MATCHES_FOUND",
            "ebay": "BLOCKED_BY_ACCESS",
            "mystery": "not-an-outcome",
        },
        normalized=2,
        summary=summary,
    )
    blocked_ids = {item["id"] for item in coverage["sources_blocked"]}  # type: ignore[union-attr]
    completed_ids = {item["id"] for item in coverage["sources_completed"]}  # type: ignore[union-attr]
    assert blocked_ids == {"ebay"}
    assert "kind" in completed_ids
    assert "mystery" in completed_ids
    kind_entry = next(
        item for item in coverage["sources_completed"] if item["id"] == "kind"  # type: ignore[union-attr]
    )
    assert kind_entry["detail"]
    assert kind_entry["strategies"]
    assert coverage["candidates_hidden"] == 2
    assert coverage["candidates_normalized"] == 2


def test_wall_clock_is_not_exceeded_before_the_run_starts() -> None:
    orch = _orch()
    orch._started = 0.0
    assert orch._wall_exceeded("s") is False
    orch._charge_wall("s")
    assert orch.controller.usage("s").used("wall_seconds") == 0


def test_fail_does_not_rewrite_an_already_terminal_campaign() -> None:
    controller = _FakeController()
    controller.repos.campaign.state = CampaignState.CANCELLED
    transitions: list[object] = []
    controller.transition = lambda *args, **kwargs: transitions.append((args, kwargs))  # type: ignore[method-assign]
    _orch(controller)._fail("s", RuntimeError("boom"))
    assert transitions == []


# --- controller write path ----------------------------------------------------


def test_get_names_a_missing_campaign(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        _controller(tmp_path).get("missing")


def test_the_same_client_search_id_returns_the_existing_campaign(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    first = controller.create(
        _intent(), budget=Budget.fixture_default(), client_search_id="client-1"
    )
    second = controller.create(
        _intent(), budget=Budget.fixture_default(), client_search_id="client-1"
    )
    assert second.search_id == first.search_id
    assert controller.find_by_client_search_id("nobody") is None
    assert controller.find_by_client_search_id("client-1").search_id == first.search_id  # type: ignore[union-attr]


def test_cancel_is_idempotent_and_refuses_to_leave_another_terminal(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    first = controller.cancel(intent.search_id, cleanup_seconds=0)
    second = controller.cancel(intent.search_id, cleanup_seconds=0)
    assert first.state is CampaignState.CANCELLED
    assert second.state is CampaignState.CANCELLED
    assert first.state_version == second.state_version


def test_delete_of_an_unknown_or_already_deleted_campaign_is_named(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    with pytest.raises(KeyError):
        controller.delete("missing")
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    controller.delete(intent.search_id)
    with pytest.raises(KeyError):
        controller.delete(intent.search_id)
    assert controller.find_by_client_search_id(intent.search_id) is None


def test_a_repeated_packet_is_not_committed_twice(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    packet = EvidencePacket(
        task_id=new_id(),
        search_id=intent.search_id,
        idempotency_key="k1",
        outputs={"task_type": "normalize"},
    )
    first = controller.commit_packet(packet)
    second = controller.commit_packet(packet)
    assert first.idempotency_key == second.idempotency_key == "k1"


def test_a_worker_must_return_the_same_idempotency_key(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    capsule = controller.make_capsule(intent.search_id, "normalize", input_digests=["d"])

    def not_a_packet(cap: object) -> str:
        del cap
        return "nope"

    with pytest.raises(IdempotencyConflict, match="EvidencePacket"):
        controller.run_task(capsule, not_a_packet)

    def wrong_key(cap: object) -> EvidencePacket:
        packet_id = cap.task_id  # type: ignore[attr-defined]
        return EvidencePacket(
            task_id=packet_id,
            search_id=intent.search_id,
            idempotency_key="different",
            outputs={"task_type": "normalize"},
        )

    with pytest.raises(IdempotencyConflict, match="different idempotency"):
        controller.run_task(capsule, wrong_key)


def test_usage_is_restored_from_disk_on_a_new_controller(tmp_path: Path) -> None:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    first = CampaignController(database, store, settings)
    intent = _intent()
    first.create(intent, budget=Budget.fixture_default())
    first.persist_usage(intent.search_id)
    first._usages.clear()
    restored = first.usage(intent.search_id)
    assert restored.search_id == intent.search_id
    ctx = first.context_from_disk(intent.search_id)
    assert ctx.has_query is False
    assert ctx.normalized_candidate_count == 0


def test_checkpoint_records_the_state_once(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    controller.create(intent, budget=Budget.fixture_default())
    first = controller.checkpoint(intent.search_id, "input_validation", {"n": 1})
    second = controller.checkpoint(intent.search_id, "input_validation", {"n": 2})
    assert first.checkpoint_id != second.checkpoint_id
    steps = controller.repos.get_runtime(intent.search_id)["completed_steps"]
    assert steps.count(CampaignState.CREATED.value) == 1
    controller.mark_step(intent.search_id, CampaignState.CREATED.value)
    assert controller.repos.get_runtime(intent.search_id)["completed_steps"].count(
        CampaignState.CREATED.value
    ) == 1


def test_cancel_does_not_move_a_completed_campaign(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    intent = _intent()
    created = controller.create(intent, budget=Budget.fixture_default())
    created.state = CampaignState.COMPLETE
    created.terminal_status = TerminalVerdict.COMPLETE
    controller.repos.update_campaign_blob(created, expected_version=created.state_version)
    out = controller.cancel(intent.search_id, cleanup_seconds=0)
    assert out.state is CampaignState.COMPLETE


def test_a_listing_image_is_not_fetched_when_already_held_or_unbudgeted() -> None:
    orch = _orch()
    held = ListingImage(
        listing_image_id="i1",
        candidate_id="c1",
        remote_url="https://img.example/a.png",
        content_digest="already",
    )
    image, changed = orch._download_listing_image(
        held, search_id="s", http=SimpleNamespace(), usage=_FakeUsage()
    )
    assert changed is False
    assert image.content_digest == "already"

    bare = ListingImage(
        listing_image_id="i2", candidate_id="c1", remote_url="https://img.example/a.png"
    )
    usage = _FakeUsage()
    usage.would_exceed = lambda **kwargs: "images" if kwargs.get("images") else None  # type: ignore[method-assign]
    _, changed = orch._download_listing_image(
        bare, search_id="s", http=SimpleNamespace(), usage=usage
    )
    assert changed is False


def test_a_non_http_or_non_image_body_is_not_stored_as_a_listing_image() -> None:
    orch = _orch()
    relative = ListingImage(
        listing_image_id="i3", candidate_id="c1", remote_url="/static/a.png"
    )
    _, changed = orch._download_listing_image(
        relative, search_id="s", http=SimpleNamespace(), usage=_FakeUsage()
    )
    assert changed is False

    def boom(url: str, **kwargs: object) -> object:
        del url, kwargs
        raise RuntimeError("network")

    remote = ListingImage(
        listing_image_id="i4", candidate_id="c1", remote_url="https://img.example/a.png"
    )
    _, changed = orch._download_listing_image(
        remote, search_id="s", http=SimpleNamespace(get=boom), usage=_FakeUsage()
    )
    assert changed is False

    html = SimpleNamespace(status=200, body=b"<html>nope</html>")
    _, changed = orch._download_listing_image(
        remote,
        search_id="s",
        http=SimpleNamespace(get=lambda *a, **k: html),
        usage=_FakeUsage(),
    )
    assert changed is False


def test_a_real_listing_image_is_stored_and_charged() -> None:
    orch = _orch()
    png = b"\x89PNG" + b"\x00" * 16
    orch.controller.store = SimpleNamespace(put_bytes=lambda body, **kwargs: "digest-png")  # type: ignore[attr-defined]
    usage = _FakeUsage()
    usage.consume = lambda **kwargs: usage._used.update(  # type: ignore[method-assign]
        {k: usage._used.get(k, 0) + int(v) for k, v in kwargs.items()}
    )
    image = ListingImage(
        listing_image_id="i5", candidate_id="c1", remote_url="https://img.example/a.png"
    )
    updated, changed = orch._download_listing_image(
        image,
        search_id="s",
        http=SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status=200, body=png)),
        usage=usage,
    )
    assert changed is True
    assert updated.content_digest == "digest-png"
    assert usage.used("images") == 1


def test_a_score_is_not_recomputed_once_recorded() -> None:
    controller = _FakeController()
    controller.repos.scores = [
        {"kind": "AUTH", "payload_json": "{}"},
        {"kind": "ITEM_MATCH", "payload_json": '{"stage":"broad"}'},
    ]
    orch = _orch(controller)
    assert orch._already_scored("s", "ITEM_MATCH") is True
    assert orch._already_scored("s", "ITEM_MATCH", "broad") is True
    assert orch._already_scored("s", "ITEM_MATCH", "fine") is False
    assert orch._already_scored("s", "LISTING_UTILITY") is False


def test_no_hypothesis_means_no_primary() -> None:
    assert _orch()._primary_hypothesis("s") is None
    controller = _FakeController()
    controller.repos.hypotheses = [
        SimpleNamespace(posterior=0.2, hypothesis_id="low"),
        SimpleNamespace(posterior=0.8, hypothesis_id="high"),
    ]
    assert _orch(controller)._primary_hypothesis("s").hypothesis_id == "high"  # type: ignore[union-attr]


def test_enter_does_not_leave_a_terminal_or_repeat_the_same_state() -> None:
    controller = _FakeController()
    controller.repos.campaign.state = CampaignState.COMPLETE
    moved: list[CampaignState] = []
    controller.transition = lambda sid, target, **kwargs: moved.append(target)  # type: ignore[method-assign]
    _orch(controller)._enter("s", CampaignState.DISCOVERING)
    assert moved == []
    controller.repos.campaign.state = CampaignState.DISCOVERING
    _orch(controller)._enter("s", CampaignState.DISCOVERING)
    assert moved == []


def test_complete_context_reuses_the_exhaustion_receipt() -> None:
    controller = _FakeController()
    controller.repos.runtime = {"exhaustion_receipt": "ex-1"}
    ctx = _orch(controller)._context("s", CampaignState.COMPLETE)
    assert ctx.exhaustion_receipt == "ex-1"
    other = _orch(controller)._context("s", CampaignState.PARTIAL)
    assert other.exhaustion_receipt is None


def test_cleanup_closes_an_engine_that_can_close() -> None:
    orch = _orch()
    closed = {"n": 0}

    class _Engine:
        def close(self) -> None:
            closed["n"] += 1

    orch.engine = _Engine()
    orch._cleanup()
    assert closed["n"] == 1
    assert orch.engine is None


def test_the_match_stages_are_omitted_until_candidates_exist() -> None:
    empty = _orch()._sequence("s")
    assert CampaignState.FINE_MATCHING not in empty
    assert empty[-1] is CampaignState.GAP_ANALYSIS
    controller = _FakeController()
    controller.repos.candidates = [SimpleNamespace(candidate_id="c1")]
    full = _orch(controller)._sequence("s")
    assert CampaignState.FINE_MATCHING in full
    assert CampaignState.PUBLISHING in full


def test_reference_work_is_not_redone_once_queries_are_planned() -> None:
    controller = _FakeController()
    controller.repos.runtime = {"completed_steps": ["PLANNING_QUERIES"]}
    _orch(controller)._ensure_reference("s")
    controller.repos.campaign.state = CampaignState.DISCOVERING
    controller.repos.runtime = {}
    _orch(controller)._ensure_reference("s")


def test_planning_and_discovery_name_a_missing_engine() -> None:
    orch = _orch()
    orch.engine = None
    orch._plan_sources("s")
    assert orch.blocked_lanes["discovery"] == "Discovery layer is not present."
    orch.blocked_lanes.clear()
    orch._discover("s")
    assert orch.blocked_lanes["discovery"] == "Discovery layer is not present."


def test_acquire_does_nothing_without_an_http_client() -> None:
    controller = _FakeController()
    controller.repos.candidates = [_candidate()]
    orch = _orch(controller)
    orch.engine = SimpleNamespace()
    orch._acquire("s")
    orch.engine = None
    orch._acquire("s")


def test_candidate_pngs_skip_images_without_bytes() -> None:
    candidate = _candidate()
    candidate.images = [
        ListingImage(listing_image_id="a", candidate_id="c", remote_url="https://x"),
    ]
    assert _orch()._candidate_pngs("s", candidate) == {}
