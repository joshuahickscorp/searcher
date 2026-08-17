"""Authenticity evidence engine (§19). Independent of item match."""

from __future__ import annotations

from searcher.authenticity.completeness import completeness
from searcher.authenticity.engine import assess_authenticity
from searcher.authenticity.established import (
    UNESTABLISHED_CONSTRUCTION,
    established_claims,
    published_compare_parts,
)
from searcher.authenticity.profiles import profile_for

__all__ = [
    "UNESTABLISHED_CONSTRUCTION",
    "assess_authenticity",
    "completeness",
    "established_claims",
    "profile_for",
    "published_compare_parts",
]
