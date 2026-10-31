"""Unit tests for the backtest engine."""

from datetime import datetime, timedelta

import pytest

from cryptoquant.backtesting.engine import BacktestConfig, run_backtest
from cryptoquant.backtesting.synthetic import make_synthetic_bars
from cryptoquant.strategies.base import Bar
from cryptoquant.strategies.signal_strategy import SignalStrategy

T0 = datetime(2025, 1, 1)
ZERO_COST = BacktestConfig(fee_bps=0, slippage_bps=0)


def bar(i, o, c=None, signal=None, low=None, atr=1.0):
    c = o if c is None else c
    return Bar(
        timestamp=T0 + timedelta(hours=i),
        open=o,
        high=max(o, c),
        low=min(o, c) if low is None else low,
        close=c,
        atr=atr,
        signal=signal,
    )


def test_requires_two_bars():
    with pytest.raises(ValueError):
        run_backtest([bar(0, 100)], SignalStrategy())


def test_fill_happens_next_open_not_signal_bar():
    bars = [bar(0, 100, 100, "BUY"), bar(1, 110, 110), bar(2, 120, 120, "AVOID"), bar(3, 130, 130)]
    r = run_backtest(bars, SignalStrategy(), ZERO_COST)
    t = r.trades[0]
    assert t.entry_price == 110  # bar 1 open, not bar 0 close
    assert t.exit_price == 130  # bar 3 open
    assert t.pnl == pytest.approx(10_000 * (130 / 110 - 1))
    assert t.exit_reason == "signal"


def test_fees_and_slippage_reduce_pnl():
    bars = [bar(0, 100, 100, "BUY"), bar(1, 100, 100), bar(2, 100, 100, "AVOID"), bar(3, 100, 100)]
    r = run_backtest(bars, SignalStrategy(), BacktestConfig(fee_bps=50, slippage_bps=10))
    assert r.trades[0].pnl < 0
    assert r.metrics["total_fees"] > 0


def test_no_signals_means_no_trades_and_flat_equity():
    bars = [bar(i, 100 + i) for i in range(10)]
    r = run_backtest(bars, SignalStrategy(), ZERO_COST)
    assert r.trades == []
    assert r.metrics["total_return"] == 0
    assert r.metrics["exposure"] == 0


def test_open_position_closed_at_end_of_data():
    bars = [bar(0, 100, 100, "BUY"), bar(1, 100, 100), bar(2, 120, 120)]
    r = run_backtest(bars, SignalStrategy(), ZERO_COST)
    assert r.trades[0].exit_reason == "end_of_data"
    assert r.equity[-1].equity == pytest.approx(12_000)


def test_atr_stop_exits_at_stop_price():
    bars = [
        bar(0, 100, 100, "BUY", atr=2),
        bar(1, 100, 100, atr=2),
        bar(2, 100, 90, low=90, atr=2),
    ]
    cfg = BacktestConfig(fee_bps=0, slippage_bps=0, stop_atr_mult=2.0)
    r = run_backtest(bars, SignalStrategy(), cfg)
    assert r.trades[0].exit_reason == "stop"
    assert r.trades[0].exit_price == pytest.approx(96)  # 100 - 2*2


def test_drawdown_and_benchmark():
    bars = [bar(0, 100, 100, "BUY"), bar(1, 100, 100), bar(2, 100, 50), bar(3, 50, 50)]
    r = run_backtest(bars, SignalStrategy(), ZERO_COST)
    assert r.metrics["max_drawdown"] == pytest.approx(-0.5)
    assert r.metrics["benchmark_return"] == pytest.approx(-0.5)


def test_synthetic_end_to_end_is_deterministic_and_consistent():
    bars = make_synthetic_bars(n=1500)
    assert any(b.signal == "BUY" for b in bars)
    a = run_backtest(bars, SignalStrategy())
    b = run_backtest(bars, SignalStrategy())
    assert a.metrics == b.metrics
    assert a.metrics["num_trades"] == len(a.trades)
    assert a.equity[-1].equity == pytest.approx(
        BacktestConfig().initial_capital + sum(t.pnl for t in a.trades), rel=1e-6
    )
