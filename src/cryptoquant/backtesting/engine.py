"""
Backtest engine (pure: no database, no I/O).

Execution model (no look-ahead):
- A decision is made from bar i (its close and the analysis computed at that
  close) and filled at the OPEN of bar i+1.
- Long-only, fully invested (all cash in on entry, all out on exit).
- Fees and slippage are charged on each fill, in basis points.
- Optional ATR stop: stop = entry fill - stop_atr_mult * ATR at the decision
  bar. If a bar's low touches the stop it exits at the stop (or the open if the
  bar gaps below it).
- Equity is marked to the close of every bar.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from cryptoquant.strategies.base import Action, Bar, Strategy


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    fee_bps: float = 40.0
    slippage_bps: float = 5.0
    stop_atr_mult: Optional[float] = None
    periods_per_year: float = 8760.0


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    fees: float
    pnl: float
    return_pct: float
    bars_held: int
    exit_reason: str


@dataclass
class EquityPoint:
    timestamp: datetime
    equity: float
    drawdown: float
    benchmark_equity: float
    in_position: bool


@dataclass
class BacktestResult:
    config: BacktestConfig
    strategy_name: str
    strategy_params: dict
    metrics: dict
    trades: List[Trade] = field(default_factory=list)
    equity: List[EquityPoint] = field(default_factory=list)


def run_backtest(
    bars: Sequence[Bar], strategy: Strategy, config: BacktestConfig = BacktestConfig()
) -> BacktestResult:
    """Replay ``bars`` (oldest first) through ``strategy``."""
    if len(bars) < 2:
        raise ValueError("Need at least 2 bars to backtest")

    fee = config.fee_bps / 10_000
    slip = config.slippage_bps / 10_000

    cash = config.initial_capital
    qty = 0.0
    entry_bar = 0
    entry_cost = 0.0
    entry_fee = 0.0
    stop_price: Optional[float] = None
    pending: Optional[Action] = None
    pending_atr: Optional[float] = None

    trades: List[Trade] = []
    equity: List[EquityPoint] = []
    peak = config.initial_capital
    bench_start = bars[0].close

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal cash, qty, stop_price
        proceeds = qty * price
        exit_fee = proceeds * fee
        cash = proceeds - exit_fee
        total_fees = entry_fee + exit_fee
        pnl = cash - entry_cost
        trades.append(
            Trade(
                entry_time=bars[entry_bar].timestamp,
                exit_time=bars[i].timestamp,
                entry_price=entry_cost_price,
                exit_price=price,
                quantity=qty,
                fees=total_fees,
                pnl=pnl,
                return_pct=pnl / entry_cost,
                bars_held=i - entry_bar,
                exit_reason=reason,
            )
        )
        qty = 0.0
        stop_price = None

    entry_cost_price = 0.0

    for i, bar in enumerate(bars):
        # 1. Fill the order decided on the previous bar at this bar's open.
        if pending is not None:
            if pending is Action.ENTER and qty == 0:
                fill = bar.open * (1 + slip)
                entry_cost = cash
                entry_fee = cash * fee
                qty = (cash - entry_fee) / fill
                entry_cost_price = fill
                cash = 0.0
                entry_bar = i
                stop_price = (
                    fill - config.stop_atr_mult * pending_atr
                    if config.stop_atr_mult and pending_atr
                    else None
                )
            elif pending is Action.EXIT and qty > 0:
                close_position(i, bar.open * (1 - slip), "signal")
            pending = None

        # 2. Intrabar stop.
        if qty > 0 and stop_price is not None and bar.low <= stop_price:
            close_position(i, min(bar.open, stop_price) * (1 - slip), "stop")

        # 3. Mark to market and record.
        value = cash + qty * bar.close
        peak = max(peak, value)
        equity.append(
            EquityPoint(
                timestamp=bar.timestamp,
                equity=value,
                drawdown=value / peak - 1,
                benchmark_equity=config.initial_capital * bar.close / bench_start,
                in_position=qty > 0,
            )
        )

        # 4. Decide for the next bar's open (not on the final bar).
        if i < len(bars) - 1:
            action = strategy.decide(bar, in_position=qty > 0)
            if action is not Action.HOLD:
                pending = action
                pending_atr = bar.atr

    if qty > 0:
        close_position(len(bars) - 1, bars[-1].close * (1 - slip), "end_of_data")
        equity[-1] = EquityPoint(
            timestamp=bars[-1].timestamp,
            equity=cash,
            drawdown=min(equity[-1].drawdown, cash / peak - 1),
            benchmark_equity=equity[-1].benchmark_equity,
            in_position=False,
        )

    return BacktestResult(
        config=config,
        strategy_name=strategy.name,
        strategy_params=strategy.params(),
        metrics=compute_metrics(equity, trades, config),
        trades=trades,
        equity=equity,
    )


def compute_metrics(
    equity: Sequence[EquityPoint], trades: Sequence[Trade], config: BacktestConfig
) -> dict:
    values = [p.equity for p in equity]
    end = values[-1]
    total_return = end / config.initial_capital - 1
    bench_return = equity[-1].benchmark_equity / config.initial_capital - 1

    years = len(values) / config.periods_per_year
    cagr = (end / config.initial_capital) ** (1 / years) - 1 if years > 0 and end > 0 else None

    rets = [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]
    sharpe = None
    if len(rets) > 1:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        if var > 0:
            sharpe = mean / math.sqrt(var) * math.sqrt(config.periods_per_year)

    wins = [t for t in trades if t.pnl > 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in trades if t.pnl <= 0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    return {
        "total_return": total_return,
        "benchmark_return": bench_return,
        "excess_return": total_return - bench_return,
        "cagr": cagr,
        "max_drawdown": min(p.drawdown for p in equity),
        "sharpe": sharpe,
        "num_trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else None,
        "profit_factor": profit_factor,
        "avg_trade_return": sum(t.return_pct for t in trades) / len(trades) if trades else None,
        "avg_bars_held": sum(t.bars_held for t in trades) / len(trades) if trades else None,
        "exposure": sum(1 for p in equity if p.in_position) / len(equity),
        "total_fees": sum(t.fees for t in trades),
        "final_equity": end,
        "num_bars": len(values),
    }
