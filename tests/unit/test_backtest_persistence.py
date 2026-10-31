"""Tests for rescoring and backtest persistence using in-memory SQLite."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cryptoquant.analytics.rescore import rescore_pair
from cryptoquant.backtesting.engine import run_backtest
from cryptoquant.backtesting.repository import load_bars, save_result
from cryptoquant.database.models import (
    Asset,
    BacktestEquity,
    BacktestRun,
    BacktestTrade,
    Base,
    MarketPrice,
    TechnicalAnalysis,
    TradingPair,
)
from cryptoquant.strategies.signal_strategy import SignalStrategy


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def attach(dbapi_conn, _):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS crypto")

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([Asset(id=1, symbol="BTC", name="Bitcoin"), Asset(id=2, symbol="USD", name="USD")])
    s.add(TradingPair(id=1, base_asset_id=1, quote_asset_id=2, symbol="BTC-USD"))
    t0 = datetime(2025, 1, 1)
    for i in range(6):
        price = 100 + i
        s.add(MarketPrice(id=i + 1, trading_pair_id=1, timestamp=t0 + timedelta(hours=i),
                          open=price, high=price + 1, low=price - 1, close=price, volume=1))
        s.add(TechnicalAnalysis(market_price_id=i + 1, trading_pair_id=1, timestamp=t0 + timedelta(hours=i),
                                ema_200=Decimal("90"), rsi_14=Decimal("25"), macd_histogram=Decimal("0.5"),
                                atr_14=Decimal("0.2")))
    s.commit()
    yield s
    s.close()


def test_rescore_populates_scores_and_signal(session):
    assert rescore_pair(session, 1, batch_size=4) == 6
    rows = session.query(TechnicalAnalysis).all()
    assert all(r.signal == "BUY" and r.technical_score is not None for r in rows)


def test_load_bars_and_save_result_round_trip(session):
    rescore_pair(session, 1)
    bars = load_bars(session, 1)
    assert len(bars) == 6 and bars[0].signal == "BUY"
    result = run_backtest(bars, SignalStrategy())
    run_id = save_result(session, 1, result)
    run = session.get(BacktestRun, run_id)
    assert run.num_trades == len(result.trades) == session.query(BacktestTrade).filter_by(run_id=run_id).count()
    assert session.query(BacktestEquity).filter_by(run_id=run_id).count() == 6
