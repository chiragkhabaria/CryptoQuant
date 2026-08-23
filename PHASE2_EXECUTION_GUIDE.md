# Phase II Implementation - Summary and Execution Guide

## ✅ Files Created/Modified

### Phase II - New Files

**Tracked Pairs System:**
- `src/cryptoquant/database/models.py` - Added `TrackedPair` model
- `scripts/sql/seed_tracked_pairs.sql` - INSERT statements for BTC-USD, ETH-USD, XRP-USD, SOL-USD
- `alembic/versions/005_create_tracked_pairs.py` - Migration to create tracked_pairs table

**Notebooks:**
- `tests/integration/populate_trading_pairs.ipynb` - Populates trading_pairs table from Coinbase API (912 pairs)
- `tests/integration/verify_tracked_pairs.ipynb` - Verifies tracked pairs insertion

**Historic Ingestion:**
- `scripts/collect_historic_data.py` - CLI script for loading historical OHLCV data

**Documentation:**
- `docs/database/HISTORIC_INGESTION.md` - Complete historic ingestion guide
- `docs/database/DATABASE_SETUP_GUIDE.md` - Updated with Phase II sections

## 📋 Execution Steps

### Step 1: Verify Migration Completed

You already ran this, but verify:

```powershell
# Check current migration
alembic current

# Should show: 005 (head)
```

### Step 2: Verify Tracked Pairs

Run the verification notebook (manually execute all cells):
```
tests/integration/verify_tracked_pairs.ipynb
```

**Expected:** 4 tracked pairs (BTC-USD, ETH-USD, XRP-USD, SOL-USD) with `is_tracking_active = 1`

### Step 3: Populate Trading Pairs (CRITICAL)

This must be done before historic data collection:

```
Execute all cells in: tests/integration/populate_trading_pairs.ipynb
```

**What it does:**
- Fetches 912 products from Coinbase API
- Creates missing assets (base/quote currencies)
- Inserts all trading pairs with order constraints
- Verifies tracked pairs are present

**Expected results:**
- ~100 new assets inserted (currencies not in Asset table)
- 912 trading pairs inserted
- Verification shows BTC-USD, ETH-USD, XRP-USD, SOL-USD exist

**Verification query:**
```sql
SELECT COUNT(*) FROM crypto.trading_pairs;  -- Should be ~912
SELECT tp.symbol, tp.status, tp.base_min_size
FROM crypto.trading_pairs tp
WHERE tp.symbol IN ('BTC-USD', 'ETH-USD', 'XRP-USD', 'SOL-USD');
```

### Step 4: Test Historic Ingestion (Optional but Recommended)

Test with a small date range first:

```powershell
python scripts/collect_historic_data.py --granularity daily --days 7 --product-id BTC-USD
```

**Expected:**
- Fetches 7 daily candles for BTC-USD
- Inserts into crypto.market_prices
- Log file created in `logs/` directory

**Verification query:**
```sql
SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
WHERE tp.symbol = 'BTC-USD';
```

### Step 5: Run Full Historic Load (3 Years Daily)

Load 3 years of daily data for all 4 tracked pairs:

```powershell
python scripts/collect_historic_data.py --granularity daily --days 1095
```

**Expected:**
- Processes: BTC-USD, ETH-USD, XRP-USD, SOL-USD
- ~1095 daily candles per pair
- Total: ~4,380 records
- Execution time: ~2-5 minutes
- Log file: `logs/historic_ingestion_{timestamp}.log`

**Verification query:**
```sql
SELECT tp.symbol, 
       COUNT(*) as candle_count, 
       MIN(mp.timestamp) as earliest, 
       MAX(mp.timestamp) as latest
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
GROUP BY tp.symbol
ORDER BY tp.symbol;
```

**Expected result:**
```
BTC-USD  | ~1095 | 2023-08-11 | 2026-08-11
ETH-USD  | ~1095 | 2023-08-11 | 2026-08-11
XRP-USD  | ~1095 | 2023-08-11 | 2026-08-11
SOL-USD  | ~1095 | 2023-08-11 | 2026-08-11
```

### Step 6: Git Commit (After Verification)

**Phase I Files to Commit:**
```powershell
git add src/cryptoquant/collectors/coinbase_client.py
git add src/cryptoquant/collectors/models.py
git add src/cryptoquant/database/models.py
git add src/cryptoquant/database/session.py
git add src/cryptoquant/config/settings.py
git add alembic/env.py
git add alembic/versions/002_crypto_schema.py
git add alembic/versions/003_add_product_id_to_assets.py
git add tests/integration/test_coinbase_client.ipynb
git add tests/integration/test_data_ingestion.ipynb
git add docs/database/DATABASE_SETUP_GUIDE.md
git add .env

git commit -m "Phase I: Coinbase API client, crypto schema, and asset ingestion

- Implemented Ed25519 JWT authentication for Coinbase Advanced Trade API
- Created crypto schema with assets, trading_pairs, market_prices tables
- Populated 409 assets from Coinbase Product API
- All API tests passing (912 products, candle data working)
- Comprehensive database setup documentation"
```

**Phase II Files to Commit:**
```powershell
git add src/cryptoquant/database/models.py
git add scripts/sql/seed_tracked_pairs.sql
git add alembic/versions/005_create_tracked_pairs.py
git add tests/integration/populate_trading_pairs.ipynb
git add tests/integration/verify_tracked_pairs.ipynb
git add scripts/collect_historic_data.py
git add docs/database/HISTORIC_INGESTION.md
git add docs/database/DATABASE_SETUP_GUIDE.md

git commit -m "Phase II: Tracked pairs and historic data ingestion system

- Created tracked_pairs table for selective monitoring (BTC-USD, ETH-USD, XRP-USD, SOL-USD)
- Implemented TradingPair population from Coinbase API (912 pairs)
- Built flexible historic ingestion CLI with configurable granularity
- Initial 3-year daily data load completed (~4,380 candles)
- Comprehensive historic ingestion documentation"
```

## 🎯 Success Criteria

✅ **Phase I Complete:**
- [x] Coinbase client working (Ed25519 JWT auth)
- [x] Crypto schema created with all tables
- [x] 409 assets loaded from Coinbase API
- [x] Documentation complete

✅ **Phase II Complete When:**
- [ ] Migration 005 executed (tracked_pairs table created)
- [ ] 4 tracked pairs verified in database
- [ ] 912 trading pairs loaded from Coinbase API
- [ ] Historic test load successful (7-day BTC-USD)
- [ ] Full 3-year daily load successful (~4,380 records)
- [ ] All verification queries return expected results

## 📚 Documentation References

- [HISTORIC_INGESTION.md](../docs/database/HISTORIC_INGESTION.md) - Complete historic ingestion guide
- [DATABASE_SETUP_GUIDE.md](../docs/database/DATABASE_SETUP_GUIDE.md) - Database setup and Phase II instructions

## 🔍 Troubleshooting

**Issue:** "No active tracked pairs found"
```sql
-- Check tracked pairs
SELECT * FROM crypto.tracked_pairs;

-- Enable if needed
UPDATE crypto.tracked_pairs SET is_tracking_active = 1;
```

**Issue:** "Trading pair 'BTC-USD' not found"
```
Execute: tests/integration/populate_trading_pairs.ipynb
```

**Issue:** Script errors or API failures
```
Check log file: logs/historic_ingestion_{timestamp}.log
Verify .env has valid COINBASE_API_KEY and COINBASE_API_SECRET
```

## 🚀 Next Steps After Phase II

1. **Daily Updates:** Set up scheduled script execution for keeping data current
2. **Indicator Generation:** Run `scripts/generate_indicators.py` (once implemented)
3. **Backtesting:** Use `notebooks/03_Backtesting.ipynb` for strategy testing
4. **Transition to Hourly:** Load hourly data for refined strategies
5. **Monitor Data Quality:** Regular gap detection and verification queries
