#!/usr/bin/env python3
"""Generate the synthetic hard-negative corpus. No marketplace scraping."""

from __future__ import annotations

from pathlib import Path

from searcher.matching.synth import (
    ADJACENT_SHOE,
    CLOSE_COUNTERFEIT_SHOE,
    COLOURWAY_SHOE,
    REFERENCE_SHOE,
    REPLICA_SHOE,
    SEASON_SHOE,
    render_views,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "hard_negatives"
    root.mkdir(parents=True, exist_ok=True)
    for spec in (
        REFERENCE_SHOE,
        ADJACENT_SHOE,
        COLOURWAY_SHOE,
        REPLICA_SHOE,
        SEASON_SHOE,
        CLOSE_COUNTERFEIT_SHOE,
    ):
        folder = root / spec.name
        folder.mkdir(parents=True, exist_ok=True)
        for view, png in render_views(spec).items():
            (folder / f"{view}.png").write_bytes(png)
    print(f"wrote synthetic views under {root}")


if __name__ == "__main__":
    main()
