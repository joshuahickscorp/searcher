"""Calibrated intervals. Uncalibrated numbers are never shown as percentages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from searcher.authenticity.contracts import EvidenceLabel
from searcher.contracts.primitives import ScoreInterval
from searcher.matching.scores import clamp01, make_interval


@dataclass(frozen=True, slots=True)
class CalibrationTable:
    profile: str
    version: str
    method: str
    provenance: dict[str, object]
    bins: tuple[tuple[float, float, float, float], ...]  # raw_lo, raw_hi, cal_mean, spread

    @property
    def calibrated(self) -> bool:
        return bool(self.bins)


def load_table(path: Path | None) -> CalibrationTable | None:
    if path is None or not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    bins = tuple(
        (
            float(item["raw_lo"]),
            float(item["raw_hi"]),
            float(item["cal_mean"]),
            float(item["spread"]),
        )
        for item in raw.get("bins", [])
    )
    return CalibrationTable(
        profile=str(raw.get("profile", "unknown")),
        version=str(raw.get("version", "unknown")),
        method=str(raw.get("method", "unknown")),
        provenance=dict(raw.get("provenance") or {}),
        bins=bins,
    )


def locate_default_table() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "fixtures" / "calibration" / "footwear_v1.json"
        if candidate.is_file():
            return candidate
    cwd = Path.cwd() / "fixtures" / "calibration" / "footwear_v1.json"
    return cwd if cwd.is_file() else None


def apply_calibration(
    raw_mean: float, table: CalibrationTable | None
) -> tuple[ScoreInterval, bool, str]:
    if table is None or not table.calibrated:
        # Honest uncalibrated interval: wide, labelled as such.
        return make_interval(raw_mean, spread=0.22), False, "uncalibrated"
    for lo, hi, cal, spread in table.bins:
        if lo <= raw_mean < hi:
            return make_interval(cal, spread=spread), True, f"fixture-calibrated:{table.version}"
    return make_interval(raw_mean, spread=0.16), True, f"fixture-calibrated:{table.version}"


def public_label(
    *,
    interval: ScoreInterval,
    calibrated: bool,
    hard: list[str],
    completeness_value: float,
) -> str:
    if not calibrated:
        return EvidenceLabel.INCOMPLETE
    if hard:
        return EvidenceLabel.CONTRADICTORY
    if completeness_value < 0.5:
        return EvidenceLabel.INCOMPLETE
    if interval.lower_bound >= 0.80:
        return EvidenceLabel.HIGH
    if interval.lower_bound >= 0.50:
        return EvidenceLabel.MODERATE
    return EvidenceLabel.INCOMPLETE


def public_number(interval: ScoreInterval, *, calibrated: bool) -> float | None:
    """Never expose a number that has not been calibrated."""
    if not calibrated:
        return None
    return clamp01(interval.lower_bound)
