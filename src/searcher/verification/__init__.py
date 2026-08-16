"""Listing-page verification: re-open the candidate, extract, compare."""

from __future__ import annotations

from searcher.verification.compare import compare_fields, statements_for
from searcher.verification.extract import extract_structured
from searcher.verification.runner import (
    merge_verification,
    verify_candidate,
    verify_candidates,
)

__all__ = [
    "compare_fields",
    "extract_structured",
    "merge_verification",
    "statements_for",
    "verify_candidate",
    "verify_candidates",
]
