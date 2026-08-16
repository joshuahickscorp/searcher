"""Donor-facing receipt helpers. Searcher receipts stay in searcher.receipts."""

from __future__ import annotations

from typing import Any

from searcher.contracts.primitives import ArtifactRef, SearcherModel
from searcher.core.errors import CapabilityUnavailable, ReceiptVerificationError
from searcher.receipts.base import ReceiptBase
from searcher.receipts.types import typed_from_payload


class VerificationResult(SearcherModel):
    ok: bool
    reason: str
    receipt_type: str | None = None
    digest: str | None = None


def verify_searcher_receipt(payload: dict[str, Any]) -> VerificationResult:
    receipt = typed_from_payload(payload)
    if not isinstance(receipt, ReceiptBase):
        return VerificationResult(ok=False, reason="not a Searcher receipt")
    try:
        receipt.verify_or_raise()
    except ReceiptVerificationError as exc:
        return VerificationResult(
            ok=False,
            reason=str(exc),
            receipt_type=receipt.receipt_type,
            digest=receipt.digest,
        )
    return VerificationResult(
        ok=True,
        reason="recomputed digest matches",
        receipt_type=receipt.receipt_type,
        digest=receipt.digest,
    )


def verify_receipt_ref(ref: ArtifactRef) -> VerificationResult:
    """Verify a Searcher receipt. Donor receipts.public is not imported.

    visionmcp.receipts.public eagerly imports visionmcp.compiler.service
    (kernels wheel). This wave does not wrap it. A typed unavailable is
    the honest result for a non-Searcher receipt.
    """
    del ref
    raise CapabilityUnavailable(
        "RECEIPT_VERIFY.donor",
        wave="this wave",
        reason=(
            "donor receipt verification is not available in this wave "
            "(visionmcp.receipts.public imports compiler kernels)"
        ),
    )
