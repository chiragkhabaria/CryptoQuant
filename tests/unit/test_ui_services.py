"""Tests for the UI service layer and the job run log (in-memory SQLite)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cryptoquant.database import job_runs
from cryptoquant.database.models import (
    Asset,
    BacktestEquity,
    BacktestRun,
    BacktestTrade,
    Base,
    JobRun,
    MarketPrice,
    TechnicalAnalysis,
    TrackedPair,
    TradingPair,
)
from cryptoquantui.services import backtests, coins, data_quality

NOW = datetime(2026, 1, 10, 12, 30)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def attach(dbapi_conn, _):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS crypto")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    s.add_all([Asset(id=1, symbol="BTC", name="Bitcoin"), Asset(id=2, symbol="USD", name="USD"),
               Asset(id=3, symbol="ETH", name="Ether")])
    s.add_all([
        TradingPair(id=1, base_asset_id=1, quote_asset_id=2, symbol="BTC-USD"),
        TradingPair(id=2, base_asset_id=3, quote_asset_id=2, symbol="ETH-USD"),
    ])
    s.add_all([TrackedPair(product_id="BTC-USD", symbol="BTC", is_tracking_active=True),
               TrackedPair(product_id="ETH-USD", symbol="ETH", is_tracking_active=True)])

    # BTC: hourly for 48h ending 10:00 with 3 missing hours, one zero-volume, one 30% spike.
    end = datetime(2026, 1, 10, 10)
    missing = {end - timedelta(hours=h) for h in (5, 6, 7)}
    mp_id = 0
    for i in range(48):
        ts = end - timedelta(hours=47 - i)
        if ts in missing:
            continue
        mp_id += 1
        price = 100.0 + (30 if i == 20 else 0)
        s.add(MarketPrice(id=mp_id, trading_pair_id=1, timestamp=ts, open=price, high=price + 1,
                          low=price - 1, close=price, volume=0 if i == 10 else 5))
        s.add(TechnicalAnalysis(market_price_id=mp_id, trading_pair_id=1, timestamp=ts,
                                ema_200=Decimal("95"), rsi_14=Decimal("40"),
                                technical_score=Decimal("70") if i % 2 else Decimal("30"),
                                signal="BUY" if i % 2 else "AVOID"))
    # ETH: stale (last candle 20h ago)
    s.add(MarketPrice(id=1000, trading_pair_id=2, timestamp=NOW - timedelta(hours=20), open=10, high=11,
                      low=9, close=10, volume=1))
    s.commit()
    yield s
    s.close()


def test_freshness_status_thresholds():
    assert data_quality.freshness_status(1) == "fresh"
    assert data_quality.freshness_status(8) == "stale"
    assert data_quality.freshness_status(30) == "old"
    assert data_quality.freshness_status(None) == "no data"


def test_freshness_per_pair(session):
    df = data_quality.freshness(session, NOW).set_index("symbol")
    assert df.loc["BTC-USD", "status"] == "fresh"
    assert df.loc["ETH-USD", "status"] == "old"
    assert df.loc["BTC-USD", "candles"] == 45


def test_completeness_counts_missing_hours(session):
    candles = data_quality.load_candles(session, NOW - timedelta(days=30))
    fresh = data_quality.freshness(session, NOW)
    first = fresh.set_index("symbol")["first_candle"]
    df = data_quality.completeness(candles, first, NOW)
    btc24 = df[(df.symbol == "BTC-USD") & (df.window_hours == 24)].iloc[0]
    # last full hour is 11:00; candles stop at 10:00 so hour 11 is missing plus the 3 earlier gaps
    assert btc24.missing == 4
    assert btc24.expected == 24


def test_find_gaps_and_integrity(session):
    candles = data_quality.load_candles(session, NOW - timedelta(days=30))
    gaps = data_quality.find_gaps(candles, "BTC-USD")
    assert list(gaps["missing_candles"]) == [3]
    integ = data_quality.integrity(candles).set_index("symbol")
    assert integ.loc["BTC-USD", "zero_volume"] == 1
    assert integ.loc["BTC-USD", "outlier_moves"] == 2  # up-spike and the return
    assert integ.loc["BTC-USD", "invalid_ohlc"] == 0


def test_analysis_coverage(session):
    df = data_quality.analysis_coverage(session, NOW - timedelta(days=30)).set_index("symbol")
    assert df.loc["BTC-USD", "scored_rows"] == 45
    assert df.loc["ETH-USD", "unanalysed_candles"] == 1


def test_coin_overview(session):
    df = coins.coin_overview(session, 24, NOW).set_index("symbol")
    assert df.loc["BTC-USD", "signal"] in ("BUY", "AVOID")
    assert df.loc["BTC-USD", "trend"] == "Above EMA200"
    assert coins.default_symbol(list(df.index)) == "BTC-USD"


def test_resample_candles(session):
    df = coins.candles_with_indicators(session, "BTC-USD", NOW - timedelta(days=30))
    daily = coins.resample_candles(df, "1D")
    assert len(daily) <= 3
    assert daily["volume"].sum() == df["volume"].sum()


def _add_run(session, pair_id, run_id, total, bench, trades=5):
    session.add(BacktestRun(
        id=run_id, trading_pair_id=pair_id, strategy_name="signal", strategy_params="{}",
        start_time=NOW - timedelta(days=30), end_time=NOW, initial_capital=10000, fee_bps=40,
        slippage_bps=5, total_return=total, benchmark_return=bench, excess_return=total - bench,
        sharpe=1.2, num_trades=trades))
    session.commit()


def test_latest_runs_and_verdict(session):
    _add_run(session, 1, 1, 0.01, 0.05)
    _add_run(session, 1, 2, 0.10, 0.05)  # newer run for the same pair wins
    _add_run(session, 2, 3, -0.02, 0.01)
    runs = backtests.latest_runs(session).set_index("symbol")
    assert runs.loc["BTC-USD", "run_id"] == 2
    assert runs.loc["BTC-USD", "verdict"] == "Beats buy & hold"
    assert runs.loc["ETH-USD", "verdict"] == "Loses money"
    summary = backtests.aggregate_summary(runs.reset_index())
    assert summary["runs"] == 2 and summary["beating"] == 1


def test_equity_and_trades(session):
    _add_run(session, 1, 1, 0.1, 0.05)
    session.add(BacktestEquity(run_id=1, timestamp=NOW, equity=10100, drawdown=0, benchmark_equity=10050, in_position=True))
    session.add(BacktestTrade(run_id=1, entry_time=NOW, exit_time=NOW, entry_price=1, exit_price=2, quantity=1,
                              fees=0, pnl=1, return_pct=1, bars_held=3, exit_reason="signal"))
    session.commit()
    assert len(backtests.equity_curve(session, 1)) == 1
    assert backtests.trades(session, 1).iloc[0]["exit_reason"] == "signal"


def test_score_explainer_weights_sum_to_100():
    info = backtests.score_explainer()
    assert info["components"]["weight_pct"].sum() == 100
    assert info["buy_threshold"] == 65.0


def test_score_vs_forward_returns_buckets(session):
    df = backtests.score_vs_forward_returns(session, "BTC-USD", horizon_hours=1, now=NOW)
    assert list(df["bucket"])[0].startswith("AVOID")
    assert df["observations"].sum() > 0


def test_signal_distribution(session):
    df = backtests.signal_distribution(session, NOW - timedelta(days=30)).set_index("symbol")
    assert df.loc["BTC-USD", "BUY"] + df.loc["BTC-USD", "AVOID"] == 45


# --- job run log ------------------------------------------------------------

@pytest.fixture()
def log_on(monkeypatch):
    monkeypatch.setenv("JOB_LOG_ENABLED", "1")


def test_track_job_success_and_failure(session_factory, log_on):
    with job_runs.track_job("ingest", session_factory=session_factory) as handle:
        handle.rows_written = 7
    with job_runs.track_job("ingest", session_factory=session_factory) as handle:
        handle.fail("boom")
    with pytest.raises(ValueError):
        with job_runs.track_job("backtest", session_factory=session_factory):
            raise ValueError("bad")

    rows = session_factory().query(JobRun).order_by(JobRun.id).all()
    assert [r.status for r in rows] == ["success", "failed", "failed"]
    assert rows[0].rows_written == 7
    assert rows[1].error == "boom"
    assert "ValueError" in rows[2].error


def test_track_job_never_breaks_job_when_db_unavailable(log_on):
    def broken():
        raise RuntimeError("db down")

    with job_runs.track_job("ingest", session_factory=broken) as handle:
        handle.rows_written = 1  # must not raise


def test_tracked_job_decorator_reports(session_factory, log_on, monkeypatch):
    monkeypatch.setattr(job_runs, "_default_session_factory", session_factory)

    @job_runs.tracked_job("analytics")
    def job():
        job_runs.report_rows(3)

    job()
    row = session_factory().query(JobRun).one()
    assert (row.job_type, row.status, row.rows_written, row.triggered_by) == ("analytics", "success", 3, "scheduler")


def test_queue_claim_and_finish(session_factory):
    s = session_factory()
    first = job_runs.enqueue_job(s, "rescore")
    job_runs.enqueue_job(s, "backtest", {"fee_bps": 10})
    assert job_runs.has_active_job(s, "rescore")
    claimed = job_runs.claim_next_queued(s)
    assert claimed.id == first and claimed.status == "running"
    job_runs.finish_job(s, first, rows_written=4)
    assert s.get(JobRun, first).status == "success"
    assert job_runs.claim_next_queued(s).job_type == "backtest"
    assert job_runs.claim_next_queued(s) is None
    with pytest.raises(ValueError):
        job_runs.enqueue_job(s, "nope")


def test_fail_stale_running(session_factory):
    s = session_factory()
    s.add(JobRun(job_type="ingest", status="running", triggered_by="ui", started_at=datetime.utcnow() - timedelta(hours=5),
                 created_at=datetime.utcnow()))
    s.commit()
    assert job_runs.fail_stale_running(s, older_than_minutes=60) == 1
    assert s.query(JobRun).one().status == "failed"
