# CryptoQuant — Current Status & Wrap-up Plan

> Branch: `dev` (latest). Written 2026-10-31. Complements `ROADMAP.md` (10-phase vision) and `docs/functionality/FUNCTIONALITY.md` (what exists today).

## 1. Where we are

| Phase | Name | Status |
|-------|------|--------|
| 1 | Market Data Platform (Coinbase client, Azure SQL, Alembic, ingestion, scheduler) | **Done** (hardening gaps below) |
| 2 | Indicator Engine (EMA200, RSI14, MACD, ATR14, `technical_analysis`, backfill) | **Done** (ADX / Bollinger / SMA from roadmap not built) |
| 3 | Scoring & Backtesting | **Done (MVP)** — scoring engine, backtest engine, `backtest_*` tables (migration 007), `daily_backtest` job, validation notebook. See `docs/backtesting/BACKTESTING.md` |
| 4 | Strategy Engine | **Started** — `Strategy` protocol + `SignalStrategy` (long/flat on BUY/AVOID). Momentum / trend / mean-reversion / DCA, optimizer, registry not built |
| 5 | UI Dashboard (Streamlit + Plotly, `src/cryptoquantui/`) | **Done** — Coins, Data quality, Backtests & score pages; `crypto.job_runs` run log + job queue (migration 008). See `docs/ui-dashboard.md` |
| 5b | AI Intelligence | Deferred (empty stub) |
| 6-10 | Approval, Execution, Portfolio, Web dashboard/API, Expansion | Empty stubs |

Implemented beyond the original roadmap: Ed25519 JWT auth, historic + incremental ingestion, gap detection/backfill with ignore list, APScheduler + Dagu, `tracked_pairs`, mini-PC deployment docs, job run log (`job_runs`) written by every scheduler job.

Unit tests in `tests/unit` (scoring, backtest engine/persistence, strategy, scheduler, UI services and pages) run on the project venv.

## 2. Phase 3 wrap-up plan (historical — completed)

1. **Housekeeping (15 min)** — commit current doc/notebook changes; mark stale Phase-1 items done; delete `__pycache__` from tests tree (confirm gitignored).
2. **Test safety net (1.5 h)** — unit tests for `indicators.py` (compare against hand-computed / pandas reference, no-lookahead), `coinbase_client.py` (mocked HTTP: pagination, 429 retry, auth header), `scoring.py`, `analytics_pipeline.py`.
3. **Scoring engine (1.5 h)** — implement `calculate_scores()` / `calculate_signal()`. **Needs your input on thresholds**; proposed defaults to confirm:
   - EMA: price vs EMA200 (above = bullish) · RSI: <30 oversold, >70 overbought · MACD: histogram sign/slope · ATR: volatility percentile
   - technical_score = weighted average (0-100); signal: ≥65 BUY, 35-65 HOLD, <35 AVOID
   - Add migration only if columns change (none expected); re-run analysis to populate.
4. **Fill script gaps (45 min)** — implement `generate_indicators.py` (batch regenerate) and `seed_database.py`; resolve migration numbering gap (004) by documenting it.
5. **Backtesting MVP (2 h)** — `backtesting/` event-loop replay over `market_prices` + `technical_analysis`, signal-driven long/flat strategy, fees/slippage params, metrics (return, CAGR, max drawdown, Sharpe, win rate), results table or CSV; notebook demo.
6. **Docs & wrap-up (30 min)** — update FUNCTIONALITY.md, ROADMAP status, commit to `dev`, open PR to `main`.

Stretch (if time): FastAPI read endpoints (`/pairs`, `/candles`, `/analysis`, `/signals`); ADX/Bollinger/SMA indicators.

## 3. Next / deferred

Next: finish Phase 4 (additional strategies, optimizer, comparison, registry). Deferred: AI intelligence (5b), approval workflow (6), live execution (7, needs safety design), portfolio analytics (8), REST API / FastAPI (9), Azure App Service deployment of the UI (container is ready).

## 4. Risks / open questions

- Scoring thresholds are business decisions — confirm defaults above.
- Python 3.14 is the target but venv is 3.12; verify pins before relying on CI.
- Execution (phase 7) must stay disabled until backtests and approval workflow exist.
