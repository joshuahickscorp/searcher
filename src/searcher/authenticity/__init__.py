"""Authenticity evidence engine (§19). Independent of item match."""

from __future__ import annotations

from searcher.authenticity.completeness import completeness
from searcher.authenticity.engine import assess_authenticity
from searcher.authenticity.profiles import profile_for

__all__ = ["assess_authenticity", "completeness", "profile_for"]
