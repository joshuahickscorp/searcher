# Ported idea from Job Scraper frozen snapshot
# path: <home>/.searcher-donors/jobscraper-frozen-20260816/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.db.log_fetch / trim_fetch_log
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Append-only fetch attempts on the Wave 1 fetch_attempts table."""

from __future__ import annotations

from searcher.contracts.models import FetchAttempt
from searcher.storage.repositories import Repositories


class FetchLog:
    def __init__(self, repos: Repositories, search_id: str) -> None:
        self.repos = repos
        self.search_id = search_id

    def append(self, attempt: FetchAttempt) -> None:
        self.repos.insert_fetch_attempt(self.search_id, attempt)

    def list(self) -> list[FetchAttempt]:
        return self.repos.list_fetch_attempts(self.search_id)
