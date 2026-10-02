"""Unit tests for incremental mode in ``run_ingestion`` and the recent-candle refresh (no network or DB)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptoquant.ingestion import historic

EMPTY = {"inserted": 0, "skipped": 0, "errors": 0, "updated": 0}


def _run(last_time):
    with (
        patch.object(historic, "CoinbaseClient"),
        patch.object(historic, "get_session", return_value=MagicMock()),
        patch.object(historic, "get_tracked_pairs", return_value=[("BTC-USD", 1)]),
        patch.object(historic, "get_last_ingestion_time", return_value=last_time),
        patch.object(historic, "fetch_and_store_candles", return_value=dict(EMPTY)) as fetch,
    ):
        result = historic.run_ingestion(incremental=True)
    return result, fetch


def _this_hour():
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def test_up_to_date_pair_refetches_recent_window_instead_of_future_range():
    # last + 1h is in the future, which Coinbase rejects with 400.
    _, fetch = _run(_this_hour())

    kwargs = fetch.call_args.kwargs
    expected = _this_hour() - timedelta(hours=historic.INCREMENTAL_REFRESH_HOURS)
    assert kwargs["start_date"] == expected
    assert kwargs["refresh_from"] == expected
    assert kwargs["start_date"] < kwargs["end_date"]


def test_pair_far_behind_resumes_after_last_candle():
    last = _this_hour() - timedelta(hours=10)

    _, fetch = _run(last)

    assert fetch.call_args.kwargs["start_date"] == last + timedelta(hours=1)


def _candle(start, close, volume="1"):
    return SimpleNamespace(
        start=start, open="1", high="2", low="0.5", close=close, volume=volume
    )


def _row(ts, close, volume="1"):
    return SimpleNamespace(
        timestamp=ts.replace(tzinfo=None),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def test_refresh_updates_changed_candle_and_leaves_unchanged_and_new_alone():
    t = _this_hour()
    stale, same = _row(t - timedelta(hours=1), "5", "1"), _row(t - timedelta(hours=2), "7")
    session = MagicMock()
    session.query.return_value.filter.return_value = [stale, same]
    candles = [
        _candle(t - timedelta(hours=2), "7"),
        _candle(t - timedelta(hours=1), "9", "3"),
        _candle(t, "4"),
    ]

    remaining, updated = historic._refresh_existing_candles(
        session, 1, candles, t - timedelta(hours=2), MagicMock()
    )

    assert updated == 1
    assert (stale.close, stale.volume) == (Decimal("9"), Decimal("3"))
    assert same.close == Decimal("7")
    assert [c.start for c in remaining] == [t]
    session.commit.assert_called_once()
