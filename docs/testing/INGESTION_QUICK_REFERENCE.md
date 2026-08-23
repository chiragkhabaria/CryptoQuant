# Ingestion Testing - Quick Reference

## Quick Start

```powershell
# Test all functionality
python tests/ingestion/test_candle_ingestion.py

# Test specific product
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# Test only historical ingestion
python tests/ingestion/test_candle_ingestion.py --test historical

# Test only incremental ingestion
python tests/ingestion/test_candle_ingestion.py --test incremental
```

## Command Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--test` | `all`, `historical`, `incremental` | `all` | Which test to run |
| `--product-id` | Trading pair (e.g., `BTC-USD`) | All active pairs | Test specific pair |
| `--granularity` | `minute`, `five_minute`, `fifteen_minute`, `thirty_minute`, `hourly`, `two_hour`, `six_hour`, `daily` | `daily` | Candle timeframe |

## Test Details

### Test 1: Historical Ingestion
- **Date Range**: 30 days ago → Yesterday
- **Purpose**: Validate bulk historical data ingestion
- **Expected**: Data inserted for the 30-day period

### Test 2: Incremental Ingestion
- **Date Range**: Yesterday → Today
- **Purpose**: Validate incremental/daily update process
- **Expected**: Recent data inserted successfully

## Output Files

- **Logs**: `logs/test_candle_ingestion_YYYYMMDD_HHMMSS.log`
- **Console**: Real-time test progress and results

## Success Criteria

✅ **Test Passes When**:
- Records are successfully inserted
- Data integrity checks pass (no NULL values, valid OHLCV relationships)
- No critical errors during ingestion

❌ **Test Fails When**:
- No data inserted and none existed before
- Data integrity violations found
- API or database errors occur

## Common Use Cases

```powershell
# Daily validation (run after scheduled ingestion)
python tests/ingestion/test_candle_ingestion.py --test incremental

# New pair validation
python tests/ingestion/test_candle_ingestion.py --product-id SOL-USD --test all

# Performance testing (high volume)
python tests/ingestion/test_candle_ingestion.py --granularity minute --test historical

# Quick smoke test
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --test incremental
```

## Prerequisites

1. Database initialized: `python scripts/db_init.py`
2. Migrations applied: `python scripts/db_migrate.py`
3. Tracked pairs configured: `python scripts/seed_database.py`
4. Environment variables set (`.env` file)
5. Virtual environment activated: `.venv\Scripts\activate`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No tracked pairs | Run `python scripts/seed_database.py` |
| API auth error | Check `.env` file credentials |
| Database error | Verify connection string in `.env` |
| Test hangs | Try single pair: `--product-id BTC-USD` |

## Files

- **Test Script**: `tests/ingestion/test_candle_ingestion.py`
- **Documentation**: `tests/ingestion/README.md`
- **Quick Reference**: `tests/ingestion/QUICK_REFERENCE.md` (this file)

For detailed information, see [README.md](README.md).
