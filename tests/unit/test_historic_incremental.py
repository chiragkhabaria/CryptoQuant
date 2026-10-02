"""Unit tests for incremental mode in ``run_ingestion`` (no network or DB)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from cryptoquant.ingestion import historic

EMPTY = {"inserted": 0, "skipped": 0, "errors": 0}


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


def test_skips_fetch_when_next_candle_is_in_the_future():
    # Latest stored candle is the current hour, so last + 1h is after now.
    last = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    result, fetch = _run(last)

    fetch.assert_not_called()
    assert result == EMPTY


def test_fetches_when_a_full_hour_is_missing():
    last = datetime.now(timezone.utc) - timedelta(hours=3)

    _, fetch = _run(last)

    fetch.assert_called_once()
    kwargs = fetch.call_args.kwargs
    assert kwargs["start_date"] == last + timedelta(hours=1)
    assert kwargs["start_date"] < kwargs["end_date"]
