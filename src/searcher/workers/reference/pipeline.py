"""Campaign-wired reference analysis, hypothesis, and query planning."""

from __future__ import annotations

from pathlib import Path

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import EvidencePacket
from searcher.contracts.enums import CampaignState, PublicEventName
from searcher.contracts.models import (
    IntentBudget,
    PrivacySettings,
    ReferenceAnalysis,
    SearchConstraints,
    SearchIntent,
)
from searcher.contracts.primitives import ArtifactRef
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.hypotheses.contradictions import apply_contradictions
from searcher.hypotheses.graph import build_graph
from searcher.hypotheses.item import seed_portfolio
from searcher.hypotheses.updates import bound_portfolio
from searcher.integrations.visionmcp.adapter import SearcherVisionAdapter
from searcher.queries.compiler import compile_queries
from searcher.receipts.types import (
    HypothesisUpdateReceipt,
    QueryPlanReceipt,
    ReferenceAnalysisReceipt,
    ReferenceIngestionReceipt,
)
from searcher.reference.analysis import analyze_stored_references
from searcher.reference.ingest import ingest_paths
from searcher.reference.report import write_report

_STEPS = (
    CampaignState.VALIDATING_INPUT,
    CampaignState.INGESTING_REFERENCES,
    CampaignState.CALIBRATING_REFERENCES,
    CampaignState.DECOMPOSING_REFERENCES,
    CampaignState.FORMING_HYPOTHESES,
    CampaignState.PLANNING_QUERIES,
)


def _progress(controller: CampaignController, search_id: str, phase: str) -> None:
    controller.emit(
        search_id,
        PublicEventName.SEARCH_PROGRESS.value,
        payload={"stage": phase, "detail": None, "phase": phase},
        actor="reference_worker",
    )
    controller.set_runtime(search_id, progress={"stage": phase, "detail": None})


def create_reference_campaign(
    controller: CampaignController,
    *,
    image_paths: list[Path],
    text: str | None,
    tags: list[str],
    settings: Settings | None = None,
) -> str:
    cfg = settings or controller.settings
    search_id = new_id()
    intent = SearchIntent(
        search_id=search_id,
        created_at=utc_now(),
        images=[],
        text=text,
        tags=list(tags),
        constraints=SearchConstraints(),
        budget=IntentBudget(
            wall_seconds=120,
            source_limit=0,
            page_limit=0,
            browser_page_limit=0,
            image_limit=cfg.max_images_per_search,
            model_call_limit=0,
            byte_limit=cfg.max_upload_bytes * cfg.max_images_per_search,
            monetary_limit=None,
        ),
        privacy=PrivacySettings(),
    )
    budget = Budget.from_dict(
        {
            **intent.budget.model_dump(mode="json"),
            "retry_limit": 2,
            "storage_limit": 200_000_000,
            "per_host_rate": {},
        }
    )
    controller.create(intent, budget=budget)
    controller.set_runtime(search_id, image_paths=[str(p.name) for p in image_paths])
    # Persist the real paths only in-process; runtime stores names, not paths.
    controller.set_runtime(search_id, image_count=len(image_paths))
    return search_id


def run_reference_query_wave(
    controller: CampaignController,
    search_id: str,
    image_paths: list[Path],
    *,
    settings: Settings | None = None,
    demoted: set[str] | None = None,
) -> dict[str, object]:
    cfg = settings or controller.settings
    intent = controller.repos.get_intent(search_id)
    adapter = SearcherVisionAdapter(controller.store, search_id=search_id, settings=cfg)

    for state in _STEPS:
        campaign = controller.get(search_id)
        if campaign.state is not state:
            controller.transition(search_id, state)
        if state is CampaignState.VALIDATING_INPUT:
            _progress(controller, search_id, "Understanding the item")
        elif state is CampaignState.INGESTING_REFERENCES:
            runtime = controller.repos.get_runtime(search_id)
            existing = [str(d) for d in (runtime.get("reference_digests") or [])]
            if existing:
                refs = [ArtifactRef(digest=d) for d in existing]
                byte_count = int(runtime.get("reference_bytes") or 0)
            else:
                refs = ingest_paths(
                    controller.store, image_paths, search_id=search_id, settings=cfg
                )
                byte_count = sum(p.stat().st_size for p in image_paths)
            usage = controller.usage(search_id)
            usage.consume(images=len(refs), bytes=byte_count)
            controller.persist_usage(search_id)
            receipt = ReferenceIngestionReceipt(
                search_id=search_id,
                reference_image_ids=[ref.digest[:16] for ref in refs],
                byte_count=byte_count,
                input_digests=[ref.digest for ref in refs],
                output_digests=[ref.digest for ref in refs],
            ).seal()
            controller.store_receipt(receipt)
            controller.set_runtime(
                search_id,
                has_visual_representation=True,
                reference_digests=[ref.digest for ref in refs],
                reference_bytes=byte_count,
                ingestion_receipt=receipt.receipt_id,
            )
            _progress(controller, search_id, "Reading visible labels")
        elif state is CampaignState.CALIBRATING_REFERENCES:
            digests = list(controller.repos.get_runtime(search_id).get("reference_digests") or [])
            refs = [ArtifactRef(digest=d) for d in digests]
            analysis = analyze_stored_references(
                controller.store,
                refs,
                text=intent.text,
                tags=list(intent.tags),
                search_id=search_id,
                settings=cfg,
                donor_inspect=adapter.inspect_via_donor if adapter.donor_available() else None,
            )
            controller.store.put_private(
                search_id,
                "analysis.json",
                analysis.model_dump_json().encode("utf-8"),
            )
            analysis_receipt = ReferenceAnalysisReceipt(
                search_id=search_id,
                analysis_id=analysis.analysis_id,
                crop_count=sum(len(img.derived.crops) for img in analysis.images),
                ocr_count=len(analysis.text_and_marks),
                cluster_count=1 + len(analysis.alternate_clusters),
                donor_invoked=analysis.donor_invoked,
                promotion_blocked=analysis.promotion_blocked,
                blocked_lanes=[lane.name for lane in analysis.lanes if lane.blocked],
                input_digests=digests,
                output_digests=[analysis.analysis_id],
                payload={"promotion_blocked": analysis.promotion_blocked},
            ).seal()
            controller.store_receipt(analysis_receipt)
            controller.set_runtime(
                search_id,
                analysis_id=analysis.analysis_id,
                analysis_receipt=analysis_receipt.receipt_id,
                calibrated=True,
            )
        elif state is CampaignState.DECOMPOSING_REFERENCES:
            controller.set_runtime(search_id, decomposed=True)
        elif state is CampaignState.FORMING_HYPOTHESES:
            _progress(controller, search_id, "Building possible identities")
            raw = controller.store.get_private(search_id, "analysis.json")
            analysis = ReferenceAnalysis.model_validate_json(raw)
            hypotheses = seed_portfolio(
                search_id=search_id,
                text=intent.text,
                tags=list(intent.tags),
                analysis=analysis,
                ceiling=cfg.hypothesis_ceiling,
            )
            hypotheses = apply_contradictions(hypotheses, analysis)
            hypotheses = bound_portfolio(hypotheses, ceiling=cfg.hypothesis_ceiling)
            for hyp in hypotheses:
                controller.repos.upsert_hypothesis(hyp)
            graph = build_graph(search_id, hypotheses)
            controller.set_runtime(
                search_id,
                hypothesis_ids=[h.hypothesis_id for h in hypotheses],
                graph_id=graph.graph_id,
            )
            hyp_receipt = HypothesisUpdateReceipt(
                search_id=search_id,
                hypothesis_ids=[h.hypothesis_id for h in hypotheses],
                active_count=sum(1 for h in hypotheses if h.status.value == "active"),
                archived_count=sum(1 for h in hypotheses if h.status.value == "archived"),
                contradiction_count=sum(len(h.contradictions) for h in hypotheses),
                input_digests=[analysis.analysis_id],
                output_digests=[h.hypothesis_id for h in hypotheses],
            ).seal()
            controller.store_receipt(hyp_receipt)
        elif state is CampaignState.PLANNING_QUERIES:
            _progress(controller, search_id, "Searching exact names")
            analysis = ReferenceAnalysis.model_validate_json(
                controller.store.get_private(search_id, "analysis.json")
            )
            hypotheses = controller.repos.list_hypotheses(search_id)
            queries = compile_queries(
                hypotheses,
                analysis,
                ceiling=cfg.query_ceiling,
                demoted=demoted,
            )
            for query in queries:
                controller.repos.upsert_query(search_id, query)
            languages = sorted({q.language for q in queries})
            families = sorted({q.family for q in queries if q.family})
            plan_receipt = QueryPlanReceipt(
                search_id=search_id,
                query_ids=[q.query_id for q in queries],
                languages=languages,
                families=families,
                max_round=max((q.round for q in queries), default=0),
                query_count=len(queries),
                input_digests=[h.hypothesis_id for h in hypotheses],
                output_digests=[q.query_id for q in queries],
            ).seal()
            controller.store_receipt(plan_receipt)
            controller.set_runtime(search_id, query_ids=[q.query_id for q in queries])
        controller.checkpoint(search_id, state.value)
        controller.mark_step(search_id, state.value)

    analysis = ReferenceAnalysis.model_validate_json(
        controller.store.get_private(search_id, "analysis.json")
    )
    hypotheses = controller.repos.list_hypotheses(search_id)
    queries = controller.repos.list_queries(search_id)
    export_dir = controller.settings.data_root / "exports" / search_id
    html_path, json_path = write_report(
        export_dir, analysis, hypotheses=hypotheses, queries=queries
    )
    capsule = controller.make_capsule(
        search_id,
        "reference_query_wave",
        input_digests=list(controller.repos.get_runtime(search_id).get("reference_digests") or []),
        parameters={"wave": "reference-query"},
        adapter_version="searcher-visionmcp-1",
    )

    def worker(cap: object) -> EvidencePacket:
        return EvidencePacket(
            task_id=capsule.task_id,
            search_id=search_id,
            idempotency_key=capsule.idempotency_key,
            outputs={
                "task_type": "reference_query_wave",
                "report_html": str(html_path.name),
                "report_json": str(json_path.name),
            },
        )

    controller.run_task(capsule, worker)
    return {
        "search_id": search_id,
        "state": controller.get(search_id).state.value,
        "hypotheses": len(hypotheses),
        "queries": len(queries),
        "report_html": str(html_path),
        "report_json": str(json_path),
        "donor_invoked": analysis.donor_invoked,
        "promotion_blocked": analysis.promotion_blocked,
    }
