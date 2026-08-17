"""A walk-only source must not read as a complete search of that source.

Discovery over a source without text_search walks collections, a catalogue
feed, and the sitemap. The campaign can publish five confident hits and still
never have looked at the user's item. The report has to say so.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from searcher.api.views import _keyhole_coverage_note, project_search


def _caps(*names: str) -> list[str]:
    return list(names)


def _coverage(
    *sources: str,
    pages: int = 51,
    normalized: int = 24,
    names: dict[str, str] | None = None,
) -> dict[str, object]:
    labels = names or {}
    return {
        "sources_completed": [
            {
                "id": source_id,
                "name": labels.get(source_id, source_id),
                "status": "SEARCHED_MATCHES_FOUND",
            }
            for source_id in sources
        ],
        "sources_blocked": [],
        "pages_fetched": pages,
        "candidates_normalized": normalized,
    }


def _lookup(table: dict[str, list[str]]):
    def capabilities_for(source_id: str) -> list[str]:
        return list(table.get(source_id) or [])

    return capabilities_for


def test_source_without_text_search_is_named_as_walked() -> None:
    note = _keyhole_coverage_note(
        _coverage("kind"),
        capabilities_for=_lookup({"kind": _caps("listing_fetch", "live_check")}),
    )
    assert note is not None
    assert "kind" in note
    assert "walked" in note
    assert "catalogue" in note
    assert "searched" in note
    assert "absence is not evidence of absence" in note
    assert "51 pages" in note
    assert "24 candidates" in note
    assert "%" not in note
    assert "percent" not in note.lower()


def test_source_with_text_search_produces_no_note() -> None:
    note = _keyhole_coverage_note(
        _coverage("wikimedia"),
        capabilities_for=_lookup({"wikimedia": _caps("text_search", "listing_fetch")}),
    )
    assert note is None


def test_note_is_absent_when_no_source_was_walked() -> None:
    empty = _keyhole_coverage_note(
        _coverage(),
        capabilities_for=_lookup({}),
    )
    assert empty is None
    unknown = _keyhole_coverage_note(
        _coverage("kind"),
        capabilities_for=_lookup({}),
    )
    assert unknown is None


def test_two_walked_sources_are_both_named() -> None:
    note = _keyhole_coverage_note(
        _coverage("kind", "komehyo"),
        capabilities_for=_lookup(
            {
                "kind": _caps("listing_fetch", "live_check"),
                "komehyo": _caps("listing_fetch", "live_check"),
            }
        ),
    )
    assert note is not None
    assert "kind" in note
    assert "komehyo" in note
    assert "were walked through their catalogues" in note


def test_mixed_sources_name_only_the_walked_one() -> None:
    note = _keyhole_coverage_note(
        _coverage("wikimedia", "kind"),
        capabilities_for=_lookup(
            {
                "wikimedia": _caps("text_search"),
                "kind": _caps("listing_fetch", "live_check"),
            }
        ),
    )
    assert note is not None
    assert "kind" in note
    assert "wikimedia" not in note
    assert "was walked through its catalogue" in note


class _Repos:
    def __init__(self, coverage: dict[str, object], hidden_note: str | None = None) -> None:
        self._runtime = {
            "coverage": coverage,
            "hidden_policy_note": hidden_note,
            "missing_reference_views": [],
        }

    def get_runtime(self, _search_id: str) -> dict[str, Any]:
        return self._runtime

    def get_campaign_meta(self, _search_id: str) -> dict[str, Any]:
        return {}

    def get_intent(self, _search_id: str) -> Any:
        return SimpleNamespace(text="", tags=[])

    def list_results(self, _search_id: str) -> list[dict[str, Any]]:
        return []


class _Controller:
    def __init__(self, repos: _Repos) -> None:
        self.repos = repos


def _campaign() -> Any:
    return SimpleNamespace(
        search_id="s1",
        state=SimpleNamespace(value="PUBLISHING"),
        state_version=1,
        coverage={},
        terminal_status=None,
        terminal_reason=None,
    )


def test_campaign_payload_surfaces_the_note_alongside_hidden_policy_note(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "searcher.api.views._capabilities_for",
        lambda source_id: (
            ["listing_fetch", "live_check"] if source_id == "kind" else ["text_search"]
        ),
    )
    body = project_search(
        _Controller(_Repos(_coverage("kind"))),  # type: ignore[arg-type]
        _campaign(),
    )
    note = body["keyhole_coverage_note"]
    assert note is not None
    assert "kind" in note
    assert "walked" in note
    assert "catalogue" in note
    assert body["hidden_policy_note"] == note


def test_walk_note_appends_to_an_existing_hidden_policy_note(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "searcher.api.views._capabilities_for",
        lambda source_id: ["listing_fetch"] if source_id == "kind" else ["text_search"],
    )
    hidden = "Hidden: 3 because the evidence did not establish the same item."
    body = project_search(
        _Controller(_Repos(_coverage("kind"), hidden_note=hidden)),  # type: ignore[arg-type]
        _campaign(),
    )
    assert body["keyhole_coverage_note"]
    assert str(body["hidden_policy_note"]).startswith("Hidden:")
    assert "kind" in str(body["hidden_policy_note"])
    assert "walked" in str(body["hidden_policy_note"])


def test_campaign_with_text_search_has_no_keyhole_note(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "searcher.api.views._capabilities_for",
        lambda _source_id: ["text_search"],
    )
    body = project_search(
        _Controller(_Repos(_coverage("wikimedia"))),  # type: ignore[arg-type]
        _campaign(),
    )
    assert body["keyhole_coverage_note"] is None
    assert body["hidden_policy_note"] is None


def test_campaign_with_no_completed_source_has_no_keyhole_note(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "searcher.api.views._capabilities_for",
        lambda _source_id: ["listing_fetch"],
    )
    body = project_search(
        _Controller(_Repos(_coverage())),  # type: ignore[arg-type]
        _campaign(),
    )
    assert body["keyhole_coverage_note"] is None
    assert body["hidden_policy_note"] is None
