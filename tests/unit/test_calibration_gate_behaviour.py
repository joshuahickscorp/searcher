"""The calibration module decides whether Real can open at all.

`apply_calibration`, `public_label` and `public_number` are what make Real
reachable for designer footwear and unreachable for everything else. The §32.1
measurement found this module at 61.5% branch coverage with ten uncovered
branches, so the rules that gate the product's strongest claim were largely
untested.
"""

from __future__ import annotations

from searcher.authenticity.calibration import (
    apply_calibration,
    load_table,
    locate_default_table,
    public_label,
    public_number,
    table_applies,
)
from searcher.authenticity.contracts import EvidenceLabel
from searcher.matching.scores import make_interval


def _table():
    return load_table(locate_default_table())


def test_uncalibrated_interval_is_wide_and_says_so() -> None:
    interval, calibrated, ceiling = apply_calibration(1.0, None)
    assert calibrated is False
    assert ceiling == "uncalibrated"
    # A raw 1.0 still cannot clear the 0.80 Real gate uncalibrated.
    assert interval.lower_bound < 0.80


def test_a_calibrated_bin_narrows_the_interval() -> None:
    table = _table()
    if table is None:
        return
    interval, calibrated, ceiling = apply_calibration(0.95, table)
    assert calibrated is True
    assert ceiling.startswith("fixture-calibrated:")
    wide, _, _ = apply_calibration(0.95, None)
    assert (interval.upper_bound - interval.lower_bound) < (wide.upper_bound - wide.lower_bound)


def test_a_raw_mean_outside_every_bin_still_reports_calibrated() -> None:
    table = _table()
    if table is None:
        return
    interval, calibrated, ceiling = apply_calibration(5.0, table)
    assert calibrated is True
    assert ceiling.startswith("fixture-calibrated:")
    assert interval is not None


def test_table_applies_only_to_its_own_profile() -> None:
    table = _table()
    if table is None:
        return
    assert table_applies(table, table.profile) is True
    assert table_applies(table, "handbag") is False
    assert table_applies(None, table.profile) is False


def test_public_number_is_withheld_until_calibrated() -> None:
    interval = make_interval(0.9, spread=0.05)
    assert public_number(interval, calibrated=False) is None
    assert public_number(interval, calibrated=True) is not None


def test_public_label_refuses_high_without_calibration() -> None:
    interval = make_interval(0.95, spread=0.02)
    label = public_label(interval=interval, calibrated=False, hard=[], completeness_value=1.0)
    assert label == EvidenceLabel.INCOMPLETE


def test_a_hard_contradiction_outranks_a_strong_interval() -> None:
    interval = make_interval(0.95, spread=0.02)
    label = public_label(
        interval=interval, calibrated=True, hard=["colourway"], completeness_value=1.0
    )
    assert label == EvidenceLabel.CONTRADICTORY


def test_thin_evidence_is_incomplete_however_strong_the_number() -> None:
    interval = make_interval(0.95, spread=0.02)
    label = public_label(interval=interval, calibrated=True, hard=[], completeness_value=0.2)
    assert label == EvidenceLabel.INCOMPLETE


def test_the_label_bands_follow_the_lower_bound() -> None:
    high = public_label(
        interval=make_interval(0.9, spread=0.05), calibrated=True, hard=[], completeness_value=1.0
    )
    moderate = public_label(
        interval=make_interval(0.6, spread=0.05), calibrated=True, hard=[], completeness_value=1.0
    )
    weak = public_label(
        interval=make_interval(0.2, spread=0.05), calibrated=True, hard=[], completeness_value=1.0
    )
    assert high == EvidenceLabel.HIGH
    assert moderate == EvidenceLabel.MODERATE
    assert weak == EvidenceLabel.INCOMPLETE
