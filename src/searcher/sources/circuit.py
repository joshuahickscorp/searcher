# Ported idea from Job Scraper frozen snapshot
# path: <home>/.searcher-donors/jobscraper-frozen-20260816/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.db.is_breaker_open / record_company_failure / record_company_success
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Per-source_id circuit breaker. Success resets. Never opens a stealth bypass."""

from __future__ import annotations

from searcher.contracts.enums import SourceOutcome
from searcher.core.errors import ErrorClass, SearcherError
from searcher.sources.health import HealthStore
from searcher.sources.statuses import is_block


class CircuitOpen(SearcherError):
    def __init__(self, source_id: str) -> None:
        super().__init__(
            f"circuit open for {source_id}",
            error_class=ErrorClass.ACCESS_BLOCK,
            details={"source_id": source_id},
        )
        self.source_id = source_id


class CircuitBreaker:
    def __init__(self, health: HealthStore) -> None:
        self.health = health

    def assert_closed(self, source_id: str) -> None:
        record = self.health.get(source_id)
        if record is not None and record.circuit_open:
            raise CircuitOpen(source_id)

    def is_open(self, source_id: str) -> bool:
        record = self.health.get(source_id)
        return bool(record and record.circuit_open)

    def record(self, source_id: str, outcome: SourceOutcome) -> None:
        self.health.record(source_id, outcome)
        if is_block(outcome) and outcome is SourceOutcome.BLOCKED_BY_ACCESS:
            # Access block is final for this circuit window. No stealth path exists.
            return
