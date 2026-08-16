"""Raw vs derived separation and the provenance chain."""

from __future__ import annotations

from pydantic import Field

from searcher.contracts.primitives import SearcherModel


class Lineage(SearcherModel):
    """Every derived claim stays linked to the exact input bytes and process."""

    input_digests: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    process: str
    raw: bool = True
    adapter_version: str = "none"
    backend_version: str = "none"
    policy_version: str = "provisional-1"


def raw_lineage(*, input_digests: list[str], process: str) -> Lineage:
    return Lineage(
        input_digests=list(input_digests),
        derived_from=[],
        process=process,
        raw=True,
    )


def derived_lineage(
    *,
    input_digests: list[str],
    derived_from: list[str],
    process: str,
    adapter_version: str = "none",
    backend_version: str = "none",
    policy_version: str = "provisional-1",
) -> Lineage:
    if not input_digests and not derived_from:
        raise ValueError("derived lineage requires input or parent evidence")
    return Lineage(
        input_digests=list(input_digests),
        derived_from=list(derived_from),
        process=process,
        raw=False,
        adapter_version=adapter_version,
        backend_version=backend_version,
        policy_version=policy_version,
    )
