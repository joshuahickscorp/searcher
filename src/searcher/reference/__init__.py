"""Reference ingestion and analysis."""

from __future__ import annotations

from searcher.reference.analysis import analyze_stored_references
from searcher.reference.ingest import ingest_paths
from searcher.reference.validation import validate_upload_bytes

__all__ = ["analyze_stored_references", "ingest_paths", "validate_upload_bytes"]
