"""International adapters carry language tags so translated queries reach them."""

from __future__ import annotations

from searcher.contracts.enums import QueryType, SourceAdmission
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.adapters import resolve_adapter
from searcher.sources.broker import SourceBroker


def test_japanese_adapters_declare_ja() -> None:
    for name in ("komehyo", "kind", "mercari_jp", "yahoo_auctions", "buyee"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        assert "ja" in manifest.languages, name


def test_western_and_archive_adapters_declare_en() -> None:
    for name in ("the_realreal", "rebag", "byronesque", "heroine", "wikimedia", "marginalia"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        assert manifest.languages
        assert "en" in manifest.languages or name == "wikimedia"


def test_translated_ja_query_plans_japanese_sources() -> None:
    query = QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language="ja",
        query_text="ディオール スニーカー",
        query_type=QueryType.TRANSLATED,
        expected_gain=0.5,
    )
    plans = SourceBroker().plan([query])
    adapters = {plan.source_adapter for plan in plans}
    assert "komehyo" in adapters
    assert "kind" in adapters
    for name in ("mercari_jp", "yahoo_auctions", "buyee"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        if manifest.admission_status is SourceAdmission.REVIEW_REQUIRED:
            assert name not in adapters
