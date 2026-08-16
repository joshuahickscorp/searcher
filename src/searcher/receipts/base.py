"""Generic hash-chained receipt. Tampering makes verify() fail."""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field

from searcher import CODE_VERSION, SCHEMA_VERSION
from searcher.contracts.primitives import SearcherModel
from searcher.core.errors import ReceiptVerificationError
from searcher.core.ids import canonical_dumps, new_id, sha256_hex
from searcher.core.policy import POLICY_VERSION
from searcher.core.time import UtcDateTime, utc_now


class ReceiptBase(SearcherModel):
    receipt_id: str = Field(default_factory=new_id)
    receipt_type: str = "ReceiptBase"
    search_id: str | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now)
    code_version: str = CODE_VERSION
    schema_version: str = SCHEMA_VERSION
    policy_version: str = POLICY_VERSION
    input_digests: list[str] = Field(default_factory=list)
    output_digests: list[str] = Field(default_factory=list)
    predecessor: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    digest: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data.pop("digest", None)
        return data

    def compute_digest(self) -> str:
        return sha256_hex(canonical_dumps(self.canonical_payload()).encode("utf-8"))

    def seal(self) -> Self:
        digest = self.compute_digest()
        return self.model_copy(update={"digest": digest})

    def verify(self) -> bool:
        if not self.digest:
            return False
        return self.digest == self.compute_digest()

    def verify_or_raise(self) -> None:
        if not self.verify():
            raise ReceiptVerificationError(
                f"receipt {self.receipt_id} ({self.receipt_type}) failed verification"
            )


def verify_payload(payload: dict[str, Any]) -> ReceiptBase:
    receipt = ReceiptBase.model_validate(payload)
    receipt.verify_or_raise()
    return receipt
