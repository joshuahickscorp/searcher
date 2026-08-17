"""The source budget must bound the list it is derived from, not a stale number.

`source_limit` was hardcoded to 8 while nine sources were answerable, so
archive_org was planned, counted as reach, and never attempted. The number and
the list were maintained in two places and drifted. Admitting a tenth source
would have silently starved another.
"""

from __future__ import annotations

import inspect

from searcher.core.config import Settings
from searcher.workers import api_campaign
from searcher.workers.api_campaign import uncredentialed_source_names


def test_source_limit_is_derived_not_written_twice() -> None:
    source = inspect.getsource(api_campaign.create_api_campaign)
    assert "source_limit=len(uncredentialed_source_names())" in source, (
        "source_limit must be derived from the source list, not written as a literal"
    )


def test_no_answerable_source_is_beyond_the_budget() -> None:
    settings = Settings.from_env()
    if not settings.live_discovery:
        return
    answerable = uncredentialed_source_names()
    assert answerable, "no answerable sources; this test would prove nothing"
    limit = len(answerable)
    starved = answerable[limit:]
    assert starved == [], f"sources planned but unreachable by budget: {starved}"
