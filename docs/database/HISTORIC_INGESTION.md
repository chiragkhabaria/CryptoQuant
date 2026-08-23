# Historic Data Ingestion Guide

This guide explains how to load historical OHLCV (Open, High, Low, Close, Volume) market data into the CryptoQuant database.

## Overview

The historic ingestion system uses a **tracked pairs** approach:
1. Define which trading pairs to monitor in the `crypto.tracked_pairs` table
2. Run the ingestion script to fetch historical candle data from Coinbase API
3. Data is stored in `crypto.market_prices` table for analysis and backtesting

## Architecture

```
crypto.tracked_pairs (BTC-USD, ETH-USD, etc.)
        ↓
    Query active pairs
        ↓
Coinbase API (get_candles)
        ↓
crypto.market_prices (OHLCV data)
```

### Key Tables

**crypto.tracked_pairs** - Controls which pairs to monitor
- `product_id`: Trading pair identifier (e.g., "BTC-USD")
- `symbol`: Display name
- `is_tracking_active`: Enable/disable tracking (1=active, 0=inactive)

**crypto.trading_pairs** - Trading pair metadata (prerequisite)
- Must be populated before historic ingestion
- Contains base/quote asset relationships and trading constraints
- Populated via: `tests/integration/populate_trading_pairs.ipynb`

**crypto.market_prices** - Time-series OHLCV data
- `trading_pair_id`: Foreign key to crypto.trading_pairs
- `timestamp`: Candle timestamp (UTC)
- `open`, `high`, `low`, `close`, `volume`: Price and volume data
- Unique constraint on (trading_pair_id, timestamp) prevents duplicates

## Prerequisites

### 1. Database Setup Complete

Ensure all migrations are applied:
```powershell
alembic upgrade head
```

Verify schema exists:
```sql
SELECT * FROM crypto.tracked_pairs;
SELECT COUNT(*) FROM crypto.trading_pairs;  -- Should be ~912 pairs
SELECT COUNT(*) FROM crypto.assets;  -- Should be ~400+ assets
```

### 2. TradingPair Table Populated

The `crypto.trading_pairs` table must contain all trading pair data from Coinbase:

**Run the population notebook:**
```powershell
# Open and execute all cells
tests/integration/populate_trading_pairs.ipynb
```

This notebook:
- Fetches all products from Coinbase API (~912 products)
- Creates missing assets (base/quote currencies)
- Inserts trading pairs with constraints (base_increment, quote_increment, min/max sizes)
- Verifies tracked pairs (BTC-USD, ETH-USD, XRP-USD, SOL-USD) are present

**Verification:**
```sql
-- Check tracked pairs exist in trading_pairs
SELECT tp.id, tp.symbol, tp.status, tp.base_min_size
FROM crypto.trading_pairs tp
WHERE tp.symbol IN ('BTC-USD', 'ETH-USD', 'XRP-USD', 'SOL-USD');
```

### 3. Environment Configuration

Ensure `.env` file has valid Coinbase API credentials:
```
COINBASE_API_KEY=organizations/.../apiKeys/...
COINBASE_API_SECRET=<base64-encoded-secret>
```

## Initial Historic Load

### Command Syntax

```powershell
python scripts/collect_historic_data.py [OPTIONS]
```

### Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--granularity` | Candle interval (daily, hourly, etc.) | daily | `--granularity daily` |
| `--days` | Number of days of history to fetch | 30 | `--days 1095` |
| `--start-date` | Start date (YYYY-MM-DD) | None | `--start-date 2023-08-01` |
| `--end-date` | End date (YYYY-MM-DD) | None | `--end-date 2026-08-11` |
| `--product-id` | Specific pair to load (optional) | None | `--product-id BTC-USD` |

**Note:** Specify either `--days` (relative) or `--start-date`/`--end-date` (absolute), not both.

### Initial 3-Year Daily Load

**Recommended initial load for all tracked pairs (3 years of daily data):**

```powershell
python scripts/collect_historic_data.py --granularity daily --days 1095
```

**Expected results:**
- 4 tracked pairs (BTC-USD, ETH-USD, XRP-USD, SOL-USD)
- ~1095 daily candles per pair
- **Total records:** ~4,380 candles
- **API calls:** ~16 calls (300 candles per call)
- **Execution time:** ~1-2 minutes

### Test Run (Single Pair, 7 Days)

Before running the full load, test with a single pair:

```powershell
python scripts/collect_historic_data.py --granularity daily --days 7 --product-id BTC-USD
```

**Verification query:**
```sql
SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
WHERE tp.symbol = 'BTC-USD';
```

## Granularity Options

The script supports multiple granularities from the Coinbase API:

| Granularity | Use Case | Records/Day | 3-Year Total (4 pairs) |
|-------------|----------|-------------|------------------------|
| `daily` | Initial load, long-term analysis | 1 | ~4,380 |
| `hourly` | Intraday strategies | 24 | ~105,120 |
| `minute` | High-frequency strategies | 1,440 | ~6,307,200 |

**Transition to hourly after initial analysis:**
```powershell
# Load last 90 days of hourly data for refined strategies
python scripts/collect_historic_data.py --granularity hourly --days 90
```

## Data Management

### Adding New Tracked Pairs

**Option 1: SQL File (Recommended)**

Edit `scripts/sql/seed_tracked_pairs.sql`:
```sql
INSERT INTO crypto.tracked_pairs (product_id, symbol, is_tracking_active)
VALUES ('AVAX-USD', 'AVAX-USD', 1);
```

Run the SQL file in Azure Data Studio or via sqlcmd.

**Option 2: Direct SQL**
```sql
INSERT INTO crypto.tracked_pairs (product_id, symbol, is_tracking_active)
VALUES ('MATIC-USD', 'MATIC-USD', 1);
```

Then run the ingestion script to backfill historical data for the new pair.

### Temporarily Disable Tracking

```sql
UPDATE crypto.tracked_pairs
SET is_tracking_active = 0
WHERE product_id = 'XRP-USD';
```

The ingestion script will skip pairs where `is_tracking_active = 0`.

### Remove Tracked Pair

```sql
-- Disable tracking first (keeps historical data)
UPDATE crypto.tracked_pairs
SET is_tracking_active = 0
WHERE product_id = 'SOL-USD';

-- Or delete entirely (historical data remains in market_prices)
DELETE FROM crypto.tracked_pairs
WHERE product_id = 'SOL-USD';
```

## Script Behavior

### Duplicate Handling

The script safely handles duplicates via the unique constraint on `(trading_pair_id, timestamp)`:
- Existing candles are skipped automatically
- No errors thrown for duplicate inserts
- Safe to re-run script for the same date range

### API Rate Limiting

Coinbase API has rate limits. The script includes:
- Batch processing: 300 candles per API call (Coinbase max)
- Automatic rate limiting (if implemented)
- Progress tracking with retry logic

If you encounter rate limit errors:
```
HTTP 429: Too Many Requests
```

Wait 1-2 minutes and re-run the script. Already-loaded candles will be skipped.

### Gap Detection

To find missing data ranges:
```sql
-- Find gaps in daily data for BTC-USD
WITH daily_candles AS (
    SELECT mp.timestamp,
           LEAD(mp.timestamp) OVER (ORDER BY mp.timestamp) as next_timestamp
    FROM crypto.market_prices mp
    JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
    WHERE tp.symbol = 'BTC-USD'
)
SELECT timestamp as gap_start,
       next_timestamp as gap_end,
       DATEDIFF(day, timestamp, next_timestamp) as gap_days
FROM daily_candles
WHERE DATEDIFF(day, timestamp, next_timestamp) > 1
ORDER BY timestamp;
```

## Ongoing Maintenance

### Daily Updates

After the initial 3-year load, keep data current with daily updates:

**Manual approach:**
```powershell
# Run daily to fetch last 2 days (catches any missed data)
python scripts/collect_historic_data.py --granularity daily --days 2
```

**Scheduled approach (future):**

Create a separate script `scripts/update_recent_data.py` for automated daily runs:
- Scheduled via Windows Task Scheduler or cron
- Fetches last 1-2 days for all active tracked pairs
- Logs results to `logs/daily_update_{date}.log`

### Data Quality Checks

**Check for recent data:**
```sql
SELECT tp.symbol,
       COUNT(*) as candle_count,
       MAX(mp.timestamp) as latest_candle,
       DATEDIFF(day, MAX(mp.timestamp), GETDATE()) as days_since_last
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
JOIN crypto.tracked_pairs tpr ON tp.symbol = tpr.product_id
WHERE tpr.is_tracking_active = 1
GROUP BY tp.symbol
ORDER BY tp.symbol;
```

**Expected result:** `days_since_last` should be 0 or 1 for active tracking.

## Troubleshooting

### Error: "Trading pair not found"

**Cause:** The product_id in tracked_pairs doesn't exist in trading_pairs table.

**Solution:**
```powershell
# Re-run TradingPair population notebook
tests/integration/populate_trading_pairs.ipynb
```

### Error: "No active tracked pairs found"

**Cause:** All pairs have `is_tracking_active = 0`.

**Solution:**
```sql
SELECT * FROM crypto.tracked_pairs;

-- Enable tracking
UPDATE crypto.tracked_pairs
SET is_tracking_active = 1
WHERE product_id IN ('BTC-USD', 'ETH-USD', 'XRP-USD', 'SOL-USD');
```

### Error: "Coinbase API authentication failed"

**Cause:** Invalid or expired API credentials.

**Solution:**
1. Verify `.env` file has correct `COINBASE_API_KEY` and `COINBASE_API_SECRET`
2. Test with: `tests/integration/test_coinbase_client.ipynb`
3. Regenerate API keys if necessary from Coinbase Developer Portal

### Script Hangs or Times Out

**Cause:** Large date range or API slowness.

**Solution:**
- Break into smaller batches: `--days 365` instead of `--days 1095`
- Check API status: https://status.coinbase.com/
- Reduce concurrent requests (if script supports parallelism)

## Logging

Execution logs are stored in `logs/historic_ingestion_{timestamp}.log`:
```
logs/
├── historic_ingestion_20260811_120530.log
├── historic_ingestion_20260811_143022.log
└── daily_update_20260812.log
```

**Log contents:**
- Pairs processed
- Date ranges fetched
- Records inserted/skipped
- API errors and retries
- Execution duration

## Next Steps

After successful historic ingestion:

1. **Verify Data Quality**
   ```sql
   SELECT tp.symbol, COUNT(*) as candles, MIN(mp.timestamp) as earliest, MAX(mp.timestamp) as latest
   FROM crypto.market_prices mp
   JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
   GROUP BY tp.symbol
   ORDER BY tp.symbol;
   ```

2. **Run Indicator Generation**
   ```powershell
   python scripts/generate_indicators.py
   ```

3. **Start Backtesting**
   ```powershell
   # Open backtesting notebook
   notebooks/03_Backtesting.ipynb
   ```

4. **Set Up Daily Updates**
   - Schedule daily script execution
   - Monitor for gaps or failures

## Advanced Usage

### Custom Date Range

Load specific historical period:
```powershell
# Load Q1 2024 hourly data
python scripts/collect_historic_data.py \
    --granularity hourly \
    --start-date 2024-01-01 \
    --end-date 2024-03-31
```

### Single Pair Refresh

Reload data for one pair:
```powershell
# Refresh last 30 days of BTC-USD
python scripts/collect_historic_data.py \
    --product-id BTC-USD \
    --granularity daily \
    --days 30
```

### Parallel Loading (Future)

For faster bulk loads, consider parallel execution:
```powershell
# Terminal 1
python scripts/collect_historic_data.py --product-id BTC-USD --days 1095

# Terminal 2
python scripts/collect_historic_data.py --product-id ETH-USD --days 1095

# Terminal 3
python scripts/collect_historic_data.py --product-id XRP-USD --days 1095

# Terminal 4
python scripts/collect_historic_data.py --product-id SOL-USD --days 1095
```

## References

- [Coinbase Advanced Trade API Docs](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)
- [DATABASE_SETUP_GUIDE.md](DATABASE_SETUP_GUIDE.md) - Database schema and migrations
- [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) - System architecture overview
- [ROADMAP.md](../roadmap/ROADMAP.md) - Platform development roadmap
