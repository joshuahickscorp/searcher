"""The live orchestrator path cannot reach canned fixture identity or scores."""

from __future__ import annotations

import ast
from pathlib import Path

CANNED_URL = "https://fixture.local/listings/dior-gat-07-001"


def test_campaign_package_has_no_scripted_identity() -> None:
    root = Path("src/searcher/campaigns")
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "dior" in lowered or "general army" in lowered:
            hits.append(str(path))
    assert hits == [], f"scripted identity leaked into {hits}"


def test_orchestrator_does_not_import_scripted_fixture() -> None:
    path = Path("src/searcher/campaigns/orchestrator.py")
    source = path.read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert "searcher.fixtures.scripted" not in imported
    assert "searcher.campaigns.runner" not in imported
    assert "searcher.fixtures" not in imported
    assert "FixtureRunner" not in source
    assert "dior_minimal" not in source
    assert CANNED_URL not in source
    assert "0.94" not in source
    assert "0.91" not in source
