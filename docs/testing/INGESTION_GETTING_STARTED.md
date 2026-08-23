# 🚀 Getting Started with Ingestion Testing

## What Was Created

✅ **Complete test infrastructure for candle ingestion functionality**

```
tests/ingestion/
├── __init__.py                    # Package initialization
├── test_candle_ingestion.py       # Main test script (620+ lines)
├── README.md                       # Comprehensive guide (500+ lines)
├── QUICK_REFERENCE.md              # Quick command reference
└── IMPLEMENTATION_SUMMARY.md       # Implementation details
```

---

## Quick Start (3 Steps)

### Step 1: Ensure Prerequisites

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Ensure database is setup
python scripts/db_init.py
python scripts/db_migrate.py
python scripts/seed_database.py
```

### Step 2: Run Your First Test

```powershell
# Test with a single pair first (recommended)
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --test historical
```

### Step 3: Review Results

- Check console output for pass/fail status
- Review log file in `logs/test_candle_ingestion_*.log`
- Verify data in database

---

## Common Commands

```powershell
# 🎯 Most Common: Test everything with defaults
python tests/ingestion/test_candle_ingestion.py

# 📊 Daily Check: Test incremental ingestion
python tests/ingestion/test_candle_ingestion.py --test incremental

# 🔍 Debug Single Pair: Test specific product
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# ⚡ High Frequency: Test with hourly data
python tests/ingestion/test_candle_ingestion.py --granularity hourly

# 🏃 Quick Smoke Test: Fast validation
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --test incremental
```

---

## What Each Test Does

### Test 1: Historical Ingestion ⏰
**Date Range**: 30 days ago → Yesterday  
**Purpose**: Validates bulk historical data loading  
**When to Use**: Initial setup, after database reset, adding new pairs

### Test 2: Incremental Ingestion 📈
**Date Range**: Yesterday → Today  
**Purpose**: Validates daily update process  
**When to Use**: Daily validation, testing scheduled jobs

---

## Expected Output

```
================================================================================
CANDLE INGESTION TEST SUITE
================================================================================
Test mode: all
Granularity: daily
Product ID: All active tracked pairs
Started at: 2026-08-21 10:30:00 UTC
================================================================================

Processing BTC-USD...
✅ Fetched 30 candles
✅ Completed: 30 inserted, 0 skipped, 0 errors
✅ Data integrity: PASSED

================================================================================
Status: ✅ PASSED
Records inserted: 30
Errors: 0
Duration: 0:00:15
================================================================================
```

---

## Understanding Test Results

### ✅ PASSED means:
- Data was successfully ingested from Coinbase API
- Records were inserted into the database
- Data integrity checks passed (no NULL values, valid OHLCV relationships)
- No critical errors occurred

### ❌ FAILED means:
- Review error messages in console output
- Check detailed log file in `logs/` directory
- Common causes: API errors, database issues, invalid data

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| "No tracked pairs found" | Run `python scripts/seed_database.py` |
| "Authentication failed" | Check `.env` file for valid Coinbase API credentials |
| "Database connection error" | Verify `DATABASE_URL` in `.env` file |
| Test hangs | Try single pair: `--product-id BTC-USD` |

---

## Documentation

- **📚 Full Guide**: [tests/ingestion/README.md](README.md) - Complete documentation
- **⚡ Quick Reference**: [tests/ingestion/QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Command cheatsheet
- **📋 Implementation**: [tests/ingestion/IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details

---

## Recommended Testing Schedule

| Frequency | Command | Purpose |
|-----------|---------|---------|
| **Daily** | `--test incremental` | Validate daily data updates |
| **Weekly** | `--test all` | Full validation of pipeline |
| **After Changes** | `--test all` | Verify changes don't break ingestion |
| **New Pair** | `--product-id XXX-USD --test all` | Validate new pair ingestion |

---

## Next Steps

1. ✅ **Test infrastructure is ready** - You can start testing immediately
2. 🔄 **Run your first test** - Use the commands above
3. 📊 **Review results** - Check logs and database
4. 🔁 **Integrate into workflow** - Add to your regular testing schedule
5. 📈 **Expand testing** - Use this pattern for other functionality (indicators, strategies, etc.)

---

## Real-World Examples

### Example 1: Initial Setup Validation
```powershell
# Test one pair first
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --test historical

# If successful, test all pairs
python tests/ingestion/test_candle_ingestion.py --test all
```

### Example 2: Daily Operations
```powershell
# Morning: Check yesterday's data ingestion
python tests/ingestion/test_candle_ingestion.py --test incremental --granularity hourly
```

### Example 3: Adding New Pair
```powershell
# After adding SOL-USD to tracked pairs
python tests/ingestion/test_candle_ingestion.py --product-id SOL-USD --test all
```

### Example 4: Debugging Issues
```powershell
# Test specific pair with detailed logging
python tests/ingestion/test_candle_ingestion.py --product-id ETH-USD --test historical

# Check the log file
cat logs/test_candle_ingestion_*.log | Select-String "ERROR"
```

---

## Test Features

✅ **Comprehensive** - Tests complete pipeline end-to-end  
✅ **Safe** - Non-destructive, can run multiple times  
✅ **Flexible** - Configure pairs, granularity, test type  
✅ **Validated** - Automatic data integrity checks  
✅ **Logged** - Detailed logs for debugging  
✅ **Documented** - Extensive documentation and examples  
✅ **Extensible** - Pattern for future test modules  

---

## Support

- **Documentation**: See [README.md](README.md) for comprehensive guide
- **Quick Help**: See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for commands
- **Log Files**: Check `logs/test_candle_ingestion_*.log` for detailed execution traces

---

## Summary

🎉 **You now have a complete testing infrastructure for ingestion!**

**Start here**:
```powershell
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
```

**Get help**:
```powershell
python tests/ingestion/test_candle_ingestion.py --help
```

**Full test**:
```powershell
python tests/ingestion/test_candle_ingestion.py
```

Happy testing! 🚀
