"""§15.6 reconstruction of a campaign from disk."""

from __future__ import annotations

from typing import Any

from searcher.campaigns.models import Checkpoint, ResumeSnapshot
from searcher.contracts.enums import HypothesisStatus, QueryStatus
from searcher.storage.repositories import Repositories


def reconstruct(repos: Repositories, search_id: str) -> ResumeSnapshot:
    campaign = repos.get_campaign(search_id)
    if campaign is None:
        raise KeyError(search_id)
    hypotheses = [
        h for h in repos.list_hypotheses(search_id) if h.status is HypothesisStatus.ACTIVE
    ]
    queries = [
        q
        for q in repos.list_queries(search_id)
        if q.status in {QueryStatus.EXHAUSTED, QueryStatus.BLOCKED, QueryStatus.SUPERSEDED}
    ]
    cursors: dict[str, str] = {}
    for run in repos.list_source_runs(search_id):
        cursor = run.get("cursor_json")
        if cursor:
            cursors[str(run["source_id"])] = str(cursor)
    pages = repos.list_discovery_pages(search_id)
    candidates = repos.list_candidates(search_id)
    decisions = repos.list_decisions(search_id)
    evidence = repos.list_evidence(search_id, accepted_only=True)
    last = repos.last_checkpoint(search_id)
    checkpoint = Checkpoint.model_validate(last) if last else None
    runtime = repos.get_runtime(search_id)
    completed = list(runtime.get("completed_steps") or [])
    pending = list(runtime.get("pending_comparisons") or [])
    stored_budget = repos.get_budget_usage(search_id)
    return ResumeSnapshot(
        search_id=search_id,
        state=campaign.state,
        state_version=campaign.state_version,
        active_hypotheses=hypotheses,
        completed_queries=queries,
        source_cursors=cursors,
        fetched_pages=pages,
        normalized_candidates=candidates,
        pending_comparisons=[str(x) for x in pending],
        budget_used=stored_budget or dict(campaign.budget_used),
        result_state=decisions,
        last_checkpoint=checkpoint,
        accepted_evidence_ids=[e.evidence_id for e in evidence],
        completed_steps=[str(s) for s in completed],
    )


def snapshot_as_dict(snapshot: ResumeSnapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")
