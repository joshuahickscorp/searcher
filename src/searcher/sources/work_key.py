# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.db.upsert_job PK (company, source_job_id)
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Deduplicated work keys. Same (source, kind, canonical target) is one row."""

from __future__ import annotations

from searcher.core.ids import sha256_hex
from searcher.normalization.url import canonicalize_url, looks_like_url


def work_key(*, source_id: str, kind: str, target: str) -> str:
    canon = canonicalize_url(target) if looks_like_url(target) else " ".join(target.lower().split())
    return sha256_hex(f"{source_id}|{kind}|{canon}".encode())
