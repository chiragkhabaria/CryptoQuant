"""Unit tests for the backfill ignore list."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cryptoquant.ingestion.backfill_ignore import (
    DEFAULT_IGNORE_FILE,
    IgnoreWindow,
    filter_ignored_gaps,
    load_ignore_windows,
)

T0 = datetime(2025, 10, 25, 16, tzinfo=timezone.utc)


def _gap(pair, start_h, end_h):
    return {
        "product_id": pair,
        "start_date": T0 + timedelta(hours=start_h),
        "end_date": T0 + timedelta(hours=end_h),
    }


def _window(start_h, end_h, pair=None):
    return IgnoreWindow(T0 + timedelta(hours=start_h), T0 + timedelta(hours=end_h), pair)


def test_gap_fully_inside_window_is_dropped():
    assert filter_ignored_gaps([_gap("BTC-USD", 0, 4)], [_window(0, 4)]) == []


def test_partially_covered_gap_is_trimmed_on_both_sides():
    result = filter_ignored_gaps([_gap("BTC-USD", 0, 10)], [_window(3, 5)])

    assert [(g["start_date"], g["end_date"]) for g in result] == [
        (T0, T0 + timedelta(hours=2)),
        (T0 + timedelta(hours=6), T0 + timedelta(hours=10)),
    ]


def test_window_only_applies_to_its_product():
    gaps = [_gap("BTC-USD", 0, 4), _gap("ETH-USD", 0, 4)]

    result = filter_ignored_gaps(gaps, [_window(0, 4, pair="BTC-USD")])

    assert [g["product_id"] for g in result] == ["ETH-USD"]


def test_unrelated_gap_is_unchanged():
    gaps = [_gap("BTC-USD", 20, 24)]
    assert filter_ignored_gaps(gaps, [_window(0, 4)]) == gaps


def test_missing_file_means_nothing_ignored(tmp_path: Path):
    assert load_ignore_windows(tmp_path / "nope.yaml") == []


def test_end_before_start_is_rejected(tmp_path: Path):
    f = tmp_path / "ignore.yaml"
    f.write_text('ignore:\n  - start: "2025-01-02T00:00:00Z"\n    end: "2025-01-01T00:00:00Z"\n')
    with pytest.raises(ValueError):
        load_ignore_windows(f)


def test_shipped_config_ignores_the_known_empty_ranges():
    windows = load_ignore_windows(DEFAULT_IGNORE_FILE)
    gaps = [
        {"product_id": p, "start_date": s, "end_date": e}
        for p in ("BTC-USD", "SOL-USD")
        for s, e in [
            (datetime(2025, 10, 25, 16, tzinfo=timezone.utc), datetime(2025, 10, 25, 20, tzinfo=timezone.utc)),
            (datetime(2026, 5, 8, 2, tzinfo=timezone.utc), datetime(2026, 5, 8, 6, tzinfo=timezone.utc)),
        ]
    ]

    assert filter_ignored_gaps(gaps, windows) == []
