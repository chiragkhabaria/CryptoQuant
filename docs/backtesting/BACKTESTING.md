# Phase 3: Scoring & Backtesting

## Scoring (`analytics/scoring.py`)
Scores are 0-100 (50 = neutral), weighted: EMA200 0.35, MACD 0.35, RSI 0.20 (mean-reversion), ATR 0.10 (low volatility = high).
Signal: BUY >= 65, AVOID < 35, else HOLD. All values are `None` during indicator warm-up. Tunables live in `ScoringConfig`.

## Engine (`backtesting/engine.py`)
Long-only, fully invested. A decision on bar *i* close fills at bar *i+1* open (no look-ahead). Default 40 bps fee + 5 bps slippage; optional ATR stop (intrabar).
Metrics: total/benchmark/excess return, CAGR, max drawdown, Sharpe, trades, win rate, profit factor, exposure, fees.

## Storage (Azure SQL, migration 007)
`crypto.backtest_runs`, `crypto.backtest_trades`, `crypto.backtest_equity`, view `crypto.vw_backtest_summary`.

## Strategies (Phase 4, started)
`strategies/base.py` defines the `Strategy` protocol (`Bar`, `Action`); `strategies/signal_strategy.py` is the long/flat `SignalStrategy` (enter on BUY, exit on AVOID by default). More strategies, optimizer and registry are pending (see ROADMAP).

## Viewing results (Phase 5)
The Streamlit dashboard's **Backtests & score** page shows per-pair results with verdicts, equity/drawdown curves, a score explainer and score-vs-forward-return. See [../ui-dashboard.md](../ui-dashboard.md).

## Run it
```
python scripts/db_migrate.py          # apply migration 007
python scripts/rescore_analysis.py    # backfill scores on existing technical_analysis rows
python scripts/run_backtest.py        # backtest all tracked pairs, persists results
```
Then open `tests/validation/phase3_scoring_backtest_validation.ipynb`. The `daily_backtest` job (04:30) reruns it on live pipeline data.
