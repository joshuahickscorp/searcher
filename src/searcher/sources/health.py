"""§14.6 source health. Changes planning only, never historical results."""

from __future__ import annotations

from datetime import timedelta

from searcher.contracts.enums import SourceHealthState, SourceOutcome
from searcher.contracts.models import SourceHealth
from searcher.core.time import format_utc, parse_utc, utc_now
from searcher.sources.statuses import is_block, is_failure
from searcher.storage.repositories import Repositories

BREAKER_THRESHOLD = 3
BREAKER_OPEN_HOURS = 4


def state_from_outcome(
    outcome: SourceOutcome,
    *,
    consecutive_failures: int,
    circuit_open: bool,
    policy_disabled: bool,
) -> SourceHealthState:
    if policy_disabled:
        return SourceHealthState.POLICY_DISABLED
    if circuit_open or outcome is SourceOutcome.BLOCKED_BY_ACCESS:
        return SourceHealthState.BLOCKED
    if outcome is SourceOutcome.SOURCE_UNAVAILABLE:
        return SourceHealthState.UNAVAILABLE
    if outcome is SourceOutcome.PARSER_FAILED:
        return SourceHealthState.PARSER_DRIFT
    if consecutive_failures > 0 or outcome is SourceOutcome.RATE_LIMITED:
        return SourceHealthState.DEGRADED
    return SourceHealthState.HEALTHY


def may_plan(state: SourceHealthState) -> bool:
    """Whether the broker may schedule new work. Historical results stay put."""
    return state in {
        SourceHealthState.HEALTHY,
        SourceHealthState.DEGRADED,
        SourceHealthState.PARSER_DRIFT,
    }


class HealthStore:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def get(self, source_id: str) -> SourceHealth | None:
        row = self.repos.get_source_health_row(source_id)
        if row is None:
            return None
        last = row.get("last_outcome") or SourceOutcome.NOT_ATTEMPTED.value
        checked = row.get("updated_at")
        return SourceHealth(
            source_id=source_id,
            last_outcome=SourceOutcome(str(last)),
            consecutive_failures=int(row.get("consecutive_failures") or 0),
            circuit_open=bool(row.get("breaker_open_until")),
            last_checked_at=parse_utc(str(checked)) if checked else utc_now(),
            state=SourceHealthState(str(row.get("state") or "HEALTHY")),
            breaker_open_until=(
                parse_utc(str(row["breaker_open_until"])) if row.get("breaker_open_until") else None
            ),
            last_block_class=row.get("last_block_class"),
            last_success_at=(
                parse_utc(str(row["last_success_at"])) if row.get("last_success_at") else None
            ),
        )

    def record(
        self,
        source_id: str,
        outcome: SourceOutcome,
        *,
        policy_disabled: bool = False,
    ) -> SourceHealth:
        existing = self.repos.get_source_health_row(source_id)
        failures = int((existing or {}).get("consecutive_failures") or 0)
        open_until = (existing or {}).get("breaker_open_until")
        last_success = (existing or {}).get("last_success_at")
        now = utc_now()
        if outcome in {SourceOutcome.SEARCHED_MATCHES_FOUND, SourceOutcome.SEARCHED_NO_MATCH}:
            failures = 0
            open_until = None
            last_success = format_utc(now)
        elif is_block(outcome) or is_failure(outcome):
            failures += 1
            if failures >= BREAKER_THRESHOLD or is_block(outcome):
                open_until = format_utc(now + timedelta(hours=BREAKER_OPEN_HOURS))
        circuit_open = False
        if open_until:
            until = parse_utc(str(open_until))
            circuit_open = until > now
            if not circuit_open:
                open_until = None
        state = state_from_outcome(
            outcome,
            consecutive_failures=failures,
            circuit_open=circuit_open,
            policy_disabled=policy_disabled,
        )
        self.repos.upsert_source_health_row(
            {
                "source_id": source_id,
                "consecutive_failures": failures,
                "breaker_open_until": open_until,
                "last_success_at": last_success,
                "last_block_class": outcome.value if is_block(outcome) else None,
                "last_outcome": outcome.value,
                "state": state.value,
                "payload": {},
            }
        )
        return SourceHealth(
            source_id=source_id,
            last_outcome=outcome,
            consecutive_failures=failures,
            circuit_open=circuit_open,
            last_checked_at=now,
            state=state,
            breaker_open_until=parse_utc(str(open_until)) if open_until else None,
            last_block_class=outcome.value if is_block(outcome) else None,
            last_success_at=parse_utc(str(last_success)) if last_success else None,
        )
