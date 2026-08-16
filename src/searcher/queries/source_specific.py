"""Source-appropriate query syntax for admitted sources only."""

from __future__ import annotations

from searcher.queries.languages import sources_for


def source_queries(
    *,
    language: str,
    brand: str | None,
    model: str | None,
    local_condition: str | None,
    local_category: str | None,
) -> list[tuple[str, str, str]]:
    """Return (source_id, query_text, family)."""
    core = " ".join(part for part in (brand, model) if part).strip()
    if not core:
        return []
    rows: list[tuple[str, str, str]] = []
    for source in sources_for(language):
        if source.startswith("wikipedia"):
            rows.append((source, core, "source_specific"))
            continue
        if source in {"komehyo", "kind"} and local_condition:
            rows.append((source, f"{core} {local_condition}", "source_specific"))
            continue
        if source == "ebay_browse_api":
            rows.append((source, core, "source_specific"))
            continue
        extra = " ".join(part for part in (local_category, local_condition) if part)
        text = f"{core} {extra}".strip() if extra else core
        rows.append((source, text, "source_specific"))
    return rows[:4]
