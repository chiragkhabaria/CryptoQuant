"""Tests that incremental analysis revisits recent candles after ingestion refreshes them."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from cryptoquant.analytics import analytics_pipeline


def _run(last_timestamp, target_candles):
    session = MagicMock()
    with (
        patch.object(analytics_pipeline, "get_last_analysis_timestamp", return_value=last_timestamp),
        patch.object(analytics_pipeline, "get_candles_range", return_value=target_candles) as get_range,
        patch.object(analytics_pipeline, "get_candles_for_calculation", return_value=[object()]),
        patch.object(analytics_pipeline, "has_sufficient_data", return_value=True),
        patch.object(analytics_pipeline, "calculate_all_indicators", return_value={}),
        patch.object(analytics_pipeline, "calculate_scores", return_value={"technical_score": None}),
        patch.object(analytics_pipeline, "calculate_signal", return_value=None),
        patch.object(analytics_pipeline, "save_technical_analysis", return_value=object()) as save,
    ):
        result = analytics_pipeline._run_incremental(session, 1, "v1")
    return result, get_range, save


def test_recent_existing_analysis_is_recalculated():
    now_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    candle = MagicMock(timestamp=now_hour - timedelta(hours=1), id=42)

    result, get_range, save = _run(now_hour, [candle])

    refresh_start = now_hour - timedelta(hours=2)
    assert get_range.call_args.args[2] == refresh_start
    assert save.call_count == 1
    assert save.call_args.kwargs["market_price_id"] == 42
    assert result["analyses_saved"] == 1


def test_analysis_far_behind_still_catches_up_from_next_unprocessed_candle():
    now_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    last = now_hour - timedelta(hours=10)

    _, get_range, _ = _run(last, [])

    assert get_range.call_args.args[2] == last + timedelta(hours=1)
