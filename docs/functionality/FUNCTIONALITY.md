# CryptoQuant — Implemented Functionality

> **Status as of 2026-09-14** | Phases 1 & 2 complete. Phase 3 in progress.

---

## Table of Contents

1. [Overview](#overview)
2. [Data Model](#data-model)
3. [Data Collection — Coinbase Client](#data-collection--coinbase-client)
4. [Data Ingestion Pipeline](#data-ingestion-pipeline)
5. [Backfill & Gap Detection](#backfill--gap-detection)
6. [Technical Analysis — Indicators](#technical-analysis--indicators)
7. [Technical Analysis — Pipeline](#technical-analysis--pipeline)
8. [Scheduler & Jobs](#scheduler--jobs)
9. [Database & Migrations](#database--migrations)
10. [CLI Scripts](#cli-scripts)
11. [Tests](#tests)
12. [Phase Status & Pending Features](#phase-status--pending-features)

---

## Overview

CryptoQuant is a cryptocurrency data platform that:

- Fetches hourly/daily OHLCV candle data from the **Coinbase Advanced API**
- Persists market data to an **Azure SQL Server** database (`crypto` schema)
- Calculates **technical indicators** (EMA 200, RSI 14, MACD, ATR 14) on stored candles
- Runs **scheduled jobs** via APScheduler for incremental ingestion and analysis
- Provides **backfill utilities** to detect and fill gaps in historical data

```
Coinbase API
    │
    ▼
CoinbaseClient (Ed25519 JWT auth, rate-limited)
    │
    ▼
fetch_and_store_candles()  ──►  crypto.market_prices  (OHLCV time-series)
    │
    ▼
run_technical_analysis()   ──►  crypto.technical_analysis  (EMA, RSI, MACD, ATR)
    │
    ▼
[Phase 3] scoring / signals / API / strategies
```

---

## Data Model

**Schema:** `crypto` (all tables live in this SQL Server schema)

### `crypto.assets`

Stores individual cryptocurrency definitions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | Auto-increment |
| `symbol` | VARCHAR(20) UNIQUE | Ticker (e.g., `BTC`) |
| `name` | VARCHAR(100) | Full name (e.g., `Bitcoin`) |
| `product_id` | VARCHAR(50) | Sample Coinbase product ID |
| `display_symbol` | VARCHAR(20) | UI-friendly symbol |
| `asset_type` | VARCHAR(20) | Default `cryptocurrency` |
| `decimals` | INT | Decimal precision (default 8) |
| `active` | BIT | Whether asset is enabled |

### `crypto.trading_pairs`

Tradeable pairs (e.g., BTC-USD) as returned by the Coinbase Products API.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | |
| `symbol` | VARCHAR(20) UNIQUE | e.g., `BTC-USD` |
| `base_asset_id` | INT FK | → `crypto.assets` |
| `quote_asset_id` | INT FK | → `crypto.assets` |
| `status` | VARCHAR(20) | `online` / `offline` |
| `trading_disabled` | BIT | |
| `base_increment` | NUMERIC(18,8) | Min order size |
| `quote_increment` | NUMERIC(18,8) | Min price increment |

### `crypto.tracked_pairs`

Controls which trading pairs are actively monitored. Only pairs with `is_tracking_active = 1` are fetched by the scheduler.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | |
| `product_id` | VARCHAR(20) | Coinbase product ID (e.g., `BTC-USD`) |
| `is_tracking_active` | BIT | Master on/off switch |

### `crypto.market_prices`

Core OHLCV time-series data (millions of rows).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | |
| `trading_pair_id` | INT FK | → `crypto.trading_pairs` |
| `timestamp` | DATETIME | Candle open time (UTC) |
| `open` | NUMERIC(18,8) | Opening price |
| `high` | NUMERIC(18,8) | High price |
| `low` | NUMERIC(18,8) | Low price |
| `close` | NUMERIC(18,8) | Closing price |
| `volume` | NUMERIC(18,8) | Trade volume |

Unique constraint: `(trading_pair_id, timestamp)`

### `crypto.technical_analysis`

Calculated indicator values per candle (millions of rows).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | |
| `trading_pair_id` | INT FK | → `crypto.trading_pairs` |
| `timestamp` | DATETIME | Candle timestamp (UTC) |
| `ema_200` | NUMERIC(18,8) | EMA 200 value |
| `rsi_14` | NUMERIC(5,2) | RSI 14 value (0–100) |
| `macd` | NUMERIC(18,8) | MACD line |
| `macd_signal` | NUMERIC(18,8) | Signal line |
| `macd_histogram` | NUMERIC(18,8) | Histogram (MACD − signal) |
| `atr_14` | NUMERIC(18,8) | ATR 14 value |
| `ema_score` | NUMERIC(5,2) | Phase 3 placeholder (NULL) |
| `rsi_score` | NUMERIC(5,2) | Phase 3 placeholder (NULL) |
| `macd_score` | NUMERIC(5,2) | Phase 3 placeholder (NULL) |
| `atr_score` | NUMERIC(5,2) | Phase 3 placeholder (NULL) |
| `technical_score` | NUMERIC(5,2) | Phase 3 placeholder (NULL) |
| `signal` | VARCHAR(20) | Phase 3 placeholder (NULL) |
| `calculation_version` | VARCHAR(10) | e.g., `v1` |

Unique constraint: `(trading_pair_id, timestamp, calculation_version)`

---

## Data Collection — Coinbase Client

**Module:** `src/cryptoquant/collectors/coinbase_client.py`

### `CoinbaseClient`

Production-ready API client for the Coinbase Advanced Trade API.

**Authentication:** Ed25519 JWT — each request gets a short-lived signed token. Keys are loaded from environment variables (`COINBASE_API_KEY`, `COINBASE_API_SECRET`).

**Retry strategy:** Automatic retry on HTTP 429, 500, 502, 503, 504 — 3 attempts with exponential backoff (factor = 2).

| Method | Description |
|--------|-------------|
| `get_products()` | List all available trading pairs from Coinbase |
| `get_candles(product_id, granularity, start, end)` | Fetch OHLCV candles for a date range |

**Supported granularities (via `CandleGranularity` enum):**

| Key | Seconds | Description |
|-----|---------|-------------|
| `ONE_MINUTE` | 60 | 1 minute |
| `FIVE_MINUTE` | 300 | 5 minutes |
| `FIFTEEN_MINUTE` | 900 | 15 minutes |
| `THIRTY_MINUTE` | 1800 | 30 minutes |
| `ONE_HOUR` | 3600 | 1 hour |
| `TWO_HOUR` | 7200 | 2 hours |
| `SIX_HOUR` | 21600 | 6 hours |
| `ONE_DAY` | 86400 | 1 day |

**Exceptions:**
- `CoinbaseAPIError` — base exception
- `CoinbaseAuthenticationError` — 401/403 responses
- `CoinbaseRateLimitError` — 429 rate limit

**Data models (`collectors/models.py`):**
- `Candle` — Pydantic model (timestamp, open, high, low, close, volume)
- `Product` — Pydantic model (product_id, status, base/quote increment)
- `ProductsResponse` — Wrapper for products list

---

## Data Ingestion Pipeline

**Module:** `src/cryptoquant/ingestion/historic.py`

### `run_ingestion()`

Top-level entry point used by both the CLI script and the scheduler.

**Modes:**
- **Historical:** Fetches `lookback_days` of candles ending at `end_date`
- **Incremental:** Fetches from `get_last_ingestion_time()` to now

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `granularity` | `"hourly"` | Candle interval key |
| `lookback_days` | `30` | Days to backfill (historical mode) |
| `end_date` | `now()` | End of date range |
| `incremental` | `False` | Enable incremental mode |
| `product_id` | `None` | Target specific pair; else all active tracked pairs |

### `fetch_and_store_candles()`

Core batch-insert function. Splits the requested date range into chunks (Coinbase returns max 300 candles per call), fetches each chunk, and bulk-inserts into `crypto.market_prices`.

**Duplicate handling:** Uses `IGNORE` / `try-except IntegrityError` — silently skips duplicate `(trading_pair_id, timestamp)` rows without failing.

**Watermark tracking:** `get_last_ingestion_time()` queries `MAX(timestamp)` for a given pair to determine the start of the next incremental window.

### `get_tracked_pairs()`

Returns `(symbol, trading_pair_id)` tuples for all pairs where `TrackedPair.is_tracking_active = True`. Supports optional `product_id` filter for single-pair operations.

### `GRANULARITY_MAP`

Maps string keys from `config/jobs.yaml` to `CandleGranularity` enums:

```python
{
  "minute": ONE_MINUTE, "five_minute": FIVE_MINUTE,
  "fifteen_minute": FIFTEEN_MINUTE, "thirty_minute": THIRTY_MINUTE,
  "hourly": ONE_HOUR, "two_hour": TWO_HOUR,
  "six_hour": SIX_HOUR, "daily": ONE_DAY
}
```

---

## Backfill & Gap Detection

**Module:** `src/cryptoquant/ingestion/backfill.py`

### `backfill_candle_gap()`

Fills a specific known gap in `crypto.market_prices` for one trading pair.

```python
backfill_candle_gap(
    product_id="BTC-USD",
    start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 7, 15, tzinfo=timezone.utc),
    granularity="hourly"
)
```

- Validates timezone-awareness (raises `ValueError` if naive)
- Returns stats dict: `{inserted, skipped, errors}`

### `backfill_multiple_gaps()`

Processes a list of gap tuples sequentially, calling `backfill_candle_gap()` for each.

```python
backfill_multiple_gaps(
    gaps=[
        ("BTC-USD", start1, end1),
        ("ETH-USD", start2, end2),
    ],
    granularity="hourly"
)
```

**Gap detection notebooks** are located in `tests/backfill/`:
- `detect_candle_gaps.ipynb` — Identifies missing candles in `market_prices`
- `detect_analysis_gaps.ipynb` — Identifies missing rows in `technical_analysis`

---

## Technical Analysis — Indicators

**Module:** `src/cryptoquant/analytics/indicators.py`

All functions are **pure** — no database access, no side effects. Same inputs always produce the same output. Returns `None` during the warm-up period (insufficient history).

### `calculate_ema(closes, period)`

Exponential Moving Average.

- Initializes with SMA of the first `period` values
- Applies `EMA = (close × multiplier) + (prev_EMA × (1 − multiplier))` for each subsequent value
- `multiplier = 2 / (period + 1)`
- **Warm-up:** requires ≥ `period` candles
- Precision: 8 decimal places (`Decimal` arithmetic)

**Usage (EMA 200):**
```python
ema_200 = calculate_ema(closes, period=200)
```

### `calculate_rsi(closes, period=14)`

Relative Strength Index.

- Calculates average gain / average loss over `period` periods
- `RSI = 100 − (100 / (1 + RS))` where `RS = avg_gain / avg_loss`
- **Overbought:** > 70 | **Oversold:** < 30
- **Warm-up:** requires ≥ `period + 1` candles

### `calculate_macd(closes, fast=12, slow=26, signal=9)`

Moving Average Convergence Divergence.

- Returns three values: `(macd_line, signal_line, histogram)`
- `MACD line = EMA(fast) − EMA(slow)`
- `Signal line = EMA(MACD line, signal_period)`
- `Histogram = MACD line − Signal line`
- **Warm-up:** requires ≥ `slow + signal` candles (≥ 35 default)

### `calculate_atr(candles, period=14)`

Average True Range.

- `True Range = max(high−low, |high−prev_close|, |low−prev_close|)`
- ATR = rolling average of True Range over `period` bars
- **Warm-up:** requires ≥ `period + 1` candles

### `calculate_all_indicators(candles)`

Convenience wrapper that calls all four indicators and returns a single dict:

```python
{
  "ema_200": Decimal | None,
  "rsi_14":  Decimal | None,
  "macd":    Decimal | None,
  "macd_signal":    Decimal | None,
  "macd_histogram": Decimal | None,
  "atr_14":  Decimal | None,
}
```

---

## Technical Analysis — Pipeline

**Module:** `src/cryptoquant/analytics/analytics_pipeline.py`

### `run_technical_analysis()`

End-to-end orchestrator for indicator calculation and persistence.

**Modes:**

| Mode | Trigger | Description |
|------|---------|-------------|
| Historical | `start_date` + `end_date` provided | Backfill indicators for a date range |
| Incremental | `incremental=True` | Process candles since `get_last_analysis_timestamp()` |

**Returns** a stats dict:

```python
{
  "mode": "historical" | "incremental",
  "trading_pair_id": int,
  "start_date": datetime,
  "end_date": datetime,
  "candles_processed": int,
  "candles_skipped_warmup": int,  # candles with < 200 prior candles
  "analyses_saved": int,
  "errors": int,
  "success": bool
}
```

**No look-ahead bias:** `market_data_reader.py` enforces that each candle only uses data up to and including its own timestamp — future candles are never included in the lookback window.

**Warm-up handling:** Any candle that lacks the minimum 200 prior candles (for EMA 200) is recorded as `candles_skipped_warmup` and skipped — no NULL records are written.

**Lookback window:** `MAX_LOOKBACK_PERIODS = 200` (EMA 200 requirement)

### `technical_repository.py`

Persistence layer for `crypto.technical_analysis`.

- **UPSERT logic:** Uses `UPDATE` if record exists for `(trading_pair_id, timestamp, version)`, else `INSERT`
- Ensures idempotent re-runs

### `scoring.py` (Phase 3 placeholder)

| Function | Status | Description |
|----------|--------|-------------|
| `calculate_scores(indicators)` | **NULL stub** | Will score EMA, RSI, MACD, ATR |
| `calculate_signal(scores)` | **NULL stub** | Will return `BUY` / `SELL` / `HOLD` |

---

## Scheduler & Jobs

**Module:** `src/cryptoquant/scheduling/`

### Scheduler (`scheduler.py`)

- Backed by **APScheduler** (in-process scheduler)
- Reads job definitions from `config/jobs.yaml` on startup — no code changes needed to add/modify jobs
- Supports `cron` and `interval` trigger types
- Graceful shutdown on `SIGINT` / `SIGTERM`
- All times in **UTC**

### Configured Jobs (`config/jobs.yaml`)

| Job ID | Type | Schedule | Enabled | Function |
|--------|------|----------|---------|----------|
| `incremental_ingestion` | interval | Every 240 min (4 hrs) | ✅ | `incremental_ingestion_job()` |
| `incremental_technical_analysis` | interval | Every 240 min (4 hrs) | ✅ | `incremental_technical_analysis_job()` |
| `historic_ingestion` | cron | Daily 02:00 UTC | ❌ disabled | `historic_ingestion_job()` |
| `weekly_backfill` | cron | Sundays 03:00 UTC | ✅ | `weekly_backfill_job()` |

### Job Functions (`jobs.py`)

| Function | Description |
|----------|-------------|
| `incremental_ingestion_job()` | Fetches new hourly candles for all active tracked pairs since last watermark |
| `historic_ingestion_job()` | Fetches `lookback_days` of daily candles (used for manual catch-up) |
| `incremental_technical_analysis_job()` | Calculates indicators for all candles since last analysis timestamp |
| `weekly_backfill_job()` | Runs gap detection and fills missing candles every Sunday |

**Fault isolation:** Each job catches its own exceptions — a failed job does not kill the scheduler.

**Retry logic:** 3 attempts with 60-second backoff for transient database errors.

---

## Database & Migrations

**Module:** `src/cryptoquant/database/`

### Session Management (`session.py`)

- SQLAlchemy connection pool: 10 connections, max overflow 20
- `pool_pre_ping=True` — validates connections before use (handles Azure SQL idle drops)
- Connection recycling: 1-hour lifetime

### Alembic Migrations (`alembic/versions/`)

| File | Description |
|------|-------------|
| `001_initial_schema.py` | Base schema (superseded) |
| `002_crypto_schema.py` | Core `crypto` schema: assets, trading_pairs, market_prices |
| `003_add_product_id_to_assets.py` | Adds `product_id` column to `assets` |
| `005_create_tracked_pairs.py` | Creates `tracked_pairs` table |
| `006_technical_analysis.py` | Creates `technical_analysis` table with all indicator columns |

---

## CLI Scripts

Located in `scripts/`:

| Script | Status | Description |
|--------|--------|-------------|
| `collect_historic_data.py` | ✅ | Fetch historical OHLCV candles from Coinbase |
| `calculate_technical_analysis.py` | ✅ | Run indicator calculation (historical or incremental) |
| `run_scheduler.py` | ✅ | Start the APScheduler daemon |
| `run_backfill.py` | ✅ | Detect and fill data gaps |
| `db_init.py` | ✅ | Initialize the database schema |
| `db_migrate.py` | ✅ | Apply pending Alembic migrations |
| `db_reset.py` | ✅ | Drop and recreate all tables (destructive) |
| `verify_technical_analysis.py` | ✅ | Display stored analysis records for validation |
| `seed_database.py` | ⚠️ TODO | Seed reference data (assets, trading_pairs) |
| `collect_market_data.py` | ⚠️ TODO | Collect current spot prices |
| `generate_indicators.py` | ⚠️ TODO | Batch indicator generation from existing history |
| `update_azure_firewall.ps1` | ✅ | Update Azure SQL firewall with current IP |

---

## Tests

**Location:** `tests/ingestion/`

| File | Type | Coverage |
|------|------|----------|
| `test_db_connection.py` | Script | Database connectivity, engine creation, schema checks |
| `test_candle_ingestion.py` | Script | Historical ingestion (30-day), incremental ingestion, duplicate handling |
| `test_candle_ingestion.ipynb` | Notebook | Interactive candle ingestion exploration |
| `test_analysis_ingestion.ipynb` | Notebook | Interactive technical analysis exploration |

**Gap detection notebooks** (`tests/backfill/`):
- `detect_candle_gaps.ipynb` — Query for missing candles in `market_prices`
- `detect_analysis_gaps.ipynb` — Query for missing rows in `technical_analysis`

---

## Phase Status & Pending Features

### ✅ Phase 1 — Data Infrastructure (Complete)

- Azure SQL schema (`crypto.assets`, `crypto.trading_pairs`, `crypto.market_prices`)
- Coinbase API client with Ed25519 JWT auth
- Historical and incremental OHLCV ingestion
- APScheduler with YAML-driven job config
- Alembic migrations

### ✅ Phase 2 — Technical Analysis (Complete)

- `crypto.technical_analysis` table
- EMA 200, RSI 14, MACD (12/26/9), ATR 14 calculation
- No look-ahead bias enforcement
- Incremental and historical analysis modes
- Backfill utilities with gap detection notebooks
- `weekly_backfill_job` scheduler entry
- `tracked_pairs` table for monitoring control

### 🚧 Phase 3 — Signals & Intelligence (Pending)

These modules exist as empty stubs or placeholder implementations:

| Module | File | What's Needed |
|--------|------|---------------|
| **Scoring engine** | `analytics/scoring.py` | Implement `calculate_scores()` and `calculate_signal()` with business rules |
| **REST API** | `api/` | FastAPI endpoints for market data and analysis queries |
| **Trading strategies** | `strategies/` | Strategy definitions using indicator signals |
| **Backtesting** | `backtesting/` | Replay historical data against strategies |
| **Portfolio tracking** | `portfolio/` | Position management and P&L |
| **Trade execution** | `execution/` | Order placement via Coinbase API |
| **ML / Intelligence** | `intelligence/` | ML models for price prediction |
| **Dashboard** | `dashboard/` | UI visualisation of data and signals |
| **Common utilities** | `common/` | Shared helpers |
| **Serverless functions** | `functions/` | Azure Function triggers |

### ⚠️ Known Gaps & TODOs

| Area | Gap | Priority |
|------|-----|----------|
| Scoring | `calculate_scores()` returns all NULLs | Phase 3 blocker |
| Signal | `calculate_signal()` returns NULL | Phase 3 blocker |
| Scripts | `seed_database.py` not implemented | Setup friction |
| Scripts | `collect_market_data.py` not implemented | Spot price support missing |
| Scripts | `generate_indicators.py` not implemented | Batch re-generation not possible without it |
| Migration | No migration `004` (gap in sequence) | Minor — cosmetic only |
| Tests | No unit tests for `indicators.py` | Risk for regression |
| Tests | No unit tests for `coinbase_client.py` | Risk for regression |
| Tests | No integration tests in `tests/integration/` | Empty folder |
| Tests | No tests for `scoring.py` or `analytics_pipeline.py` | Risk for Phase 3 |
