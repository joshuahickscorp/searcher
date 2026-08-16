"""§19.5 evidence completeness by expected view."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile


def completeness(
    *,
    profile: CategoryProfile,
    present_views: set[str],
) -> tuple[float, list[str]]:
    expected = list(profile.expected_views)
    critical = list(profile.critical_views)
    if not expected:
        return 0.0, ["no-expected-views"]
    have = sum(1 for view in expected if view in present_views)
    cov = have / len(expected)
    crit = sum(1 for view in critical if view in present_views) / len(critical) if critical else 1.0
    value = 0.6 * cov + 0.4 * crit
    missing = [view for view in expected if view not in present_views]
    return round(value, 4), missing
