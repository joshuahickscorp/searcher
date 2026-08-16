"""§22.5 human feedback. Signed local evidence; never an immediate re-rank."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from searcher.api.dependencies import ApiError, get_state
from searcher.contracts.enums import EvidencePolarity, FactClass, FeedbackVerdict
from searcher.contracts.primitives import SearcherModel
from searcher.core.ids import canonical_dumps, new_id, sha256_hex
from searcher.core.time import utc_now
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord
from searcher.receipts.types import FeedbackReceipt

router = APIRouter()


class FeedbackRequest(SearcherModel):
    verdict: FeedbackVerdict
    note: str | None = Field(default=None)


@router.post("/v1/results/{result_id}/feedback")
def submit_feedback(result_id: str, request: Request, body: FeedbackRequest) -> JSONResponse:
    state = get_state(request)
    row = state.controller.repos.get_result_row(result_id)
    if row is None or state.controller.repos.is_deleted(str(row["search_id"])):
        raise ApiError(404, "result_not_found", "This result is no longer available.")
    search_id = str(row["search_id"])
    digest_payload = {
        "result_id": result_id,
        "search_id": search_id,
        "verdict": body.verdict.value,
        "note": body.note or "",
    }
    digest = sha256_hex(canonical_dumps(digest_payload).encode("utf-8"))
    record = EvidenceRecord(
        evidence_id=new_id(),
        search_id=search_id,
        content_digest=digest,
        family_id=f"feedback:{result_id}",
        polarity=EvidencePolarity.SUPPORTING,
        fact_class=FactClass.USER_SUPPLIED,
        accepted=True,
        lineage=raw_lineage(input_digests=[digest], process="human_feedback"),
        created_at=utc_now(),
        label="human_feedback",
        notes=[body.verdict.value],
    )
    state.controller.record_evidence(record)
    feedback_id = new_id()
    state.controller.repos.insert_feedback(
        search_id,
        feedback_id,
        body.verdict.value,
        {"result_id": result_id, "verdict": body.verdict.value, "note": body.note},
        result_id=result_id,
    )
    receipt = FeedbackReceipt(
        search_id=search_id,
        result_id=result_id,
        verdict=body.verdict.value,
        input_digests=[digest],
        output_digests=[record.evidence_id],
    ).seal()
    state.controller.store_receipt(receipt)
    payload: dict[str, Any] = {
        "ok": True,
        "feedback_id": feedback_id,
        "receipt_id": receipt.receipt_id,
        "applied": False,
    }
    return JSONResponse(payload, status_code=202)
