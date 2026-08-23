# Ingestion Testing Guide

This guide explains how to test the data ingestion functionality for the CryptoQuant platform. The tests validate that historical and incremental OHLCV (Open, High, Low, Close, Volume) candle data can be successfully fetched from Coinbase API and stored in the database.

## ⚠️ IMPORTANT: Azure SQL Firewall Setup

**Before running tests, you MUST whitelist your IP address in Azure SQL Server firewall.**

### Quick Fix (Automated)

Run this PowerShell script to automatically add your IP:

```powershell
# Replace with your Azure resource group name
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# Wait 2-5 minutes for changes to take effect
```

### Manual Fix

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your SQL Server: `fin-market-sqlserver`
3. Click **"Networking"** → **"+ Add client IP"** → **"Save"**
4. Wait 2-5 minutes

### Test Connection

After whitelisting your IP, test the connection:

```powershell
python tests/ingestion/test_db_connection.py
```

**For detailed troubleshooting, see: [AZURE_SQL_TROUBLESHOOTING.md](AZURE_SQL_TROUBLESHOOTING.md)**

---

## Table of Contents

- [Overview](#overview)
- [Test Suite Structure](#test-suite-structure)
- [Testing Candle Ingestion](#testing-candle-ingestion)
- [Running Tests](#running-tests)
- [Understanding Test Results](#understanding-test-results)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Future Testing Patterns](#future-testing-patterns)

---

## Overview

### What Gets Tested

The ingestion test suite validates the following aspects of the data pipeline:

1. **Historical Ingestion**: Ability to fetch bulk historical data (30 days until yesterday)
2. **Incremental Ingestion**: Ability to fetch recent data (yesterday to today)
3. **Data Integrity**: Validates OHLCV relationships, checks for NULL values, ensures timestamps are correct
4. **Error Handling**: Properly logs and reports errors during ingestion
5. **Duplicate Detection**: Verifies that duplicate records are skipped correctly
6. **API Integration**: Tests the connection to Coinbase API
7. **Database Operations**: Validates database writes and queries

### Test Philosophy

- **End-to-End**: Tests the complete pipeline from API fetch to database storage
- **Non-Destructive**: Tests don't delete existing data, only add new records
- **Idempotent**: Tests can be run multiple times safely (duplicates are skipped)
- **Comprehensive Logging**: All operations and errors are logged for debugging
- **Automated Validation**: Data integrity checks run automatically

---

## Test Suite Structure

```
tests/
├── ingestion/
│   ├── __init__.py
│   ├── test_candle_ingestion.py       # Main test script
│   └── README.md                       # This file
└── ...
```

### Test Script: `test_candle_ingestion.py`

This is the main test script that contains:

- **Test 1: Historical Ingestion** - Fetches 30 days of data until yesterday
- **Test 2: Incremental Ingestion** - Fetches data from yesterday to today
- **Data Validation** - Checks data integrity after ingestion
- **Results Reporting** - Comprehensive test result summaries

---

## Testing Candle Ingestion

### Prerequisites

Before running tests, ensure:

1. **Database is setup and migrated**:
   ```powershell
   python scripts/db_init.py
   python scripts/db_migrate.py
   ```

2. **Tracked pairs are configured**:
   ```powershell
   # Seed the database with tracked pairs
   python scripts/seed_database.py
   ```

3. **Environment variables are set** (`.env` file):
   ```
   COINBASE_API_KEY=your_api_key
   COINBASE_API_SECRET=your_api_secret
   DATABASE_URL=your_database_url
   ```

4. **Dependencies are installed**:
   ```powershell
   pip install -e .
   ```

### Test 1: Historical Ingestion (30 Days Until Yesterday)

**Purpose**: Validates that the system can fetch and store bulk historical data.

**What it does**:
- Fetches candle data for a 30-day period ending yesterday
- Stores data in the `crypto.market_prices` table
- Validates data integrity (no NULL values, valid OHLCV relationships)
- Reports statistics (inserted, skipped, errors)

**When to use**:
- Initial setup to populate historical data
- After database resets
- To validate bulk ingestion performance
- When adding new trading pairs

### Test 2: Incremental Ingestion (Yesterday to Today)

**Purpose**: Validates that the system can fetch and store recent/incremental data.

**What it does**:
- Fetches candle data from yesterday to today
- Simulates the daily update process
- Validates data integrity
- Checks that incremental updates work correctly

**When to use**:
- To test daily update workflows
- After historical data is loaded
- To validate near-real-time data ingestion
- Before scheduling automated ingestion jobs

---

## Running Tests

### Run All Tests

Run both historical and incremental tests with default settings:

```powershell
python tests/ingestion/test_candle_ingestion.py
```

### Run Specific Test

Run only the historical ingestion test:

```powershell
python tests/ingestion/test_candle_ingestion.py --test historical
```

Run only the incremental ingestion test:

```powershell
python tests/ingestion/test_candle_ingestion.py --test incremental
```

### Test Specific Trading Pair

Test a single trading pair instead of all active pairs:

```powershell
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
```

### Test Different Granularities

Test with hourly candles instead of daily:

```powershell
python tests/ingestion/test_candle_ingestion.py --granularity hourly
```

Available granularities:
- `minute` - 1-minute candles
- `five_minute` - 5-minute candles
- `fifteen_minute` - 15-minute candles
- `thirty_minute` - 30-minute candles
- `hourly` - 1-hour candles
- `two_hour` - 2-hour candles
- `six_hour` - 6-hour candles
- `daily` - 1-day candles (default)

### Common Test Scenarios

**Scenario 1: Initial Setup Validation**
```powershell
# Test with one pair first to validate setup
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --test historical

# If successful, test all pairs
python tests/ingestion/test_candle_ingestion.py --test all
```

**Scenario 2: Daily Update Validation**
```powershell
# Test incremental ingestion with hourly data
python tests/ingestion/test_candle_ingestion.py --test incremental --granularity hourly
```

**Scenario 3: Troubleshooting a Specific Pair**
```powershell
# Test a single pair with detailed logging
python tests/ingestion/test_candle_ingestion.py --product-id ETH-USD --test all
```

**Scenario 4: Performance Testing**
```powershell
# Test with minute-level granularity (high volume)
python tests/ingestion/test_candle_ingestion.py --granularity minute --test historical
```

---

## Understanding Test Results

### Test Output

Each test produces detailed output including:

1. **Test Configuration**: Date ranges, granularity, trading pairs
2. **Progress Logs**: Real-time ingestion progress
3. **Statistics**: Records inserted, skipped (duplicates), errors
4. **Data Validation**: Integrity checks results
5. **Test Summary**: Pass/fail status with detailed metrics

### Sample Output

```
================================================================================
CANDLE INGESTION TEST SUITE
================================================================================
Test mode: all
Granularity: daily
Product ID: All active tracked pairs
Started at: 2026-08-21 10:30:00 UTC
================================================================================

================================================================================
Starting Test: Historical Ingestion (30 days until yesterday, daily)
================================================================================
Date range: 2026-07-21 to 2026-08-20
Granularity: daily
Product ID: All active tracked pairs
Testing with 3 trading pair(s)

Processing BTC-USD...
Records before ingestion: 25
2026-08-21 10:30:15 [INFO] Fetching ONE_DAY candles for BTC-USD from 2026-07-21 to 2026-08-20
2026-08-21 10:30:18 [INFO] Fetched 30 candles for BTC-USD
2026-08-21 10:30:19 [INFO] Completed BTC-USD: 5 inserted, 25 skipped, 0 errors
Records after ingestion: 30
Found 30 records in date range

Processing ETH-USD...
Records before ingestion: 0
2026-08-21 10:30:20 [INFO] Fetching ONE_DAY candles for ETH-USD from 2026-07-21 to 2026-08-20
2026-08-21 10:30:23 [INFO] Fetched 30 candles for ETH-USD
2026-08-21 10:30:24 [INFO] Completed ETH-USD: 30 inserted, 0 skipped, 0 errors
Records after ingestion: 30
Found 30 records in date range

================================================================================
Test: Historical Ingestion (30 days until yesterday, daily)
Status: ✅ PASSED
Duration: 0:00:25
--------------------------------------------------------------------------------
Records before: 25
Records after: 60
Records inserted: 35
Records skipped (duplicates): 25
Errors during ingestion: 0
================================================================================
```

### Understanding Statistics

- **Records before/after**: Total count of records in the database for the test period
- **Records inserted**: New records added during the test
- **Records skipped**: Duplicate records that were skipped (normal behavior)
- **Errors during ingestion**: Number of errors encountered (should be 0)

### Test Status

- **✅ PASSED**: Test completed successfully
  - Data was ingested successfully
  - No critical errors occurred
  - Data integrity checks passed

- **❌ FAILED**: Test failed
  - Check the error messages in the output
  - Review the log file for detailed error information
  - Common causes: API errors, database connection issues, data validation failures

### Log Files

All test runs create timestamped log files in the `logs/` directory:

```
logs/test_candle_ingestion_20260821_103000.log
```

Log files contain:
- Detailed execution traces
- API requests and responses
- Database operations
- Error stack traces
- Data validation results

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "No active tracked pairs found"

**Cause**: The `crypto.tracked_pairs` table is empty or all pairs are inactive.

**Solution**:
```powershell
# Seed the database with tracked pairs
python scripts/seed_database.py

# Or manually activate pairs in the database
# UPDATE crypto.tracked_pairs SET is_tracking_active = 1 WHERE product_id = 'BTC-USD';
```

#### Issue: "Authentication failed" or "Invalid API key"

**Cause**: Coinbase API credentials are missing or invalid.

**Solution**:
1. Check your `.env` file has correct credentials
2. Verify credentials in Coinbase Developer Portal
3. Ensure the API key has the necessary permissions

#### Issue: "No records found after ingestion"

**Cause**: API returned no data for the requested period, or data already exists.

**Solution**:
1. Check if the trading pair is active on Coinbase
2. Verify the date range is valid (not too far in the past)
3. Check API rate limits haven't been exceeded
4. Review Coinbase API status page

#### Issue: "Found records with invalid OHLCV relationships"

**Cause**: Data integrity validation failed (e.g., high < low).

**Solution**:
1. This usually indicates an API or data quality issue
2. Check the specific records flagged in the error
3. Verify the API response is correct
4. Consider reporting to Coinbase if data is consistently invalid

#### Issue: Test hangs or times out

**Cause**: Network issues, API rate limiting, or large data volumes.

**Solution**:
1. Check network connectivity
2. Try testing with a single pair: `--product-id BTC-USD`
3. Use a smaller date range or lower granularity
4. Check Coinbase API rate limits

### Debugging Tips

1. **Run with a single pair first**:
   ```powershell
   python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
   ```

2. **Check the log file**: Look for detailed error messages in `logs/test_candle_ingestion_*.log`

3. **Test database connection**:
   ```powershell
   python scripts/db_init.py
   ```

4. **Verify API credentials**:
   ```powershell
   # Test with a simple script that calls the API
   python -c "from cryptoquant.collectors.coinbase_client import CoinbaseClient; client = CoinbaseClient(); print('API connected successfully')"
   ```

5. **Check database manually**:
   ```sql
   -- Check tracked pairs
   SELECT * FROM crypto.tracked_pairs WHERE is_tracking_active = 1;
   
   -- Check ingested data
   SELECT tp.symbol, COUNT(*) as record_count, MIN(timestamp) as earliest, MAX(timestamp) as latest
   FROM crypto.market_prices mp
   JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
   GROUP BY tp.symbol;
   ```

---

## Best Practices

### When to Run Tests

1. **Before deployment**: Validate the ingestion pipeline works correctly
2. **After database changes**: Ensure schema changes don't break ingestion
3. **When adding new pairs**: Test that new pairs ingest correctly
4. **Periodically**: Run weekly to ensure ongoing data quality
5. **After API changes**: Validate that API updates don't break integration

### Test Execution Patterns

1. **Start small**: Test with one pair before running all pairs
2. **Test both modes**: Always run both historical and incremental tests
3. **Review logs**: Don't just check pass/fail, review the detailed logs
4. **Monitor data quality**: Check the data integrity warnings
5. **Keep logs**: Archive test logs for troubleshooting historical issues

### Data Validation

After running tests, perform manual spot checks:

```sql
-- Check recent data for a pair
SELECT TOP 10 *
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
WHERE tp.symbol = 'BTC-USD'
ORDER BY mp.timestamp DESC;

-- Verify OHLCV relationships
SELECT *
FROM crypto.market_prices
WHERE high < low OR high < open OR high < close OR low > open OR low > close
LIMIT 10;

-- Check for gaps in data
WITH ordered_data AS (
    SELECT timestamp,
           LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
           trading_pair_id
    FROM crypto.market_prices
    WHERE trading_pair_id = (SELECT id FROM crypto.trading_pairs WHERE symbol = 'BTC-USD')
)
SELECT *
FROM ordered_data
WHERE DATEDIFF(hour, prev_timestamp, timestamp) > 25  -- For daily data
ORDER BY timestamp;
```

---

## Future Testing Patterns

As the platform grows, additional tests will be added following this pattern:

### Planned Test Categories

1. **Indicator Generation Tests** (`tests/indicators/`)
   - Test that technical indicators calculate correctly
   - Validate indicator values against known datasets
   - Test performance with large datasets

2. **Strategy Backtesting Tests** (`tests/backtesting/`)
   - Test strategy logic with historical data
   - Validate P&L calculations
   - Test risk management rules

3. **Execution Tests** (`tests/execution/`)
   - Test order placement (paper trading)
   - Validate order routing
   - Test error handling for rejected orders

4. **Portfolio Tests** (`tests/portfolio/`)
   - Test position tracking
   - Validate P&L calculations
   - Test rebalancing logic

5. **Scheduler Tests** (`tests/scheduling/`)
   - Test job scheduling and execution
   - Validate error recovery
   - Test concurrent job handling

### Creating New Test Modules

When creating new test modules, follow this template:

```python
#!/usr/bin/env python
"""
End-to-End Tests for [Functionality]

Description of what this test suite validates.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import logging
import click

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import necessary modules
from cryptoquant.database.session import get_session


class TestResults:
    """Container for test results and statistics."""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.started_at = datetime.now(timezone.utc)
        self.passed = False
        self.errors = []
        self.warnings = []
    
    def complete(self, passed: bool):
        self.passed = passed
        self.completed_at = datetime.now(timezone.utc)


def setup_logging() -> logging.Logger:
    """Configure logging for test execution."""
    # Same pattern as candle ingestion tests
    pass


def test_functionality_1(logger: logging.Logger) -> TestResults:
    """Test 1: Description."""
    # Test implementation
    pass


@click.command()
@click.option("--test", type=click.Choice(["all", "test1", "test2"]), default="all")
def main(test: str):
    """Run end-to-end tests for [functionality]."""
    logger = setup_logging()
    # Run tests
    pass


if __name__ == "__main__":
    main()
```

### Documentation Pattern

Each test directory should have a README.md with:

1. **Overview**: What gets tested
2. **Prerequisites**: Setup requirements
3. **Running Tests**: Command examples
4. **Understanding Results**: How to interpret output
5. **Troubleshooting**: Common issues
6. **Best Practices**: When and how to run tests

---

## Summary

The ingestion test suite provides comprehensive validation of the data pipeline:

- ✅ Tests both historical and incremental ingestion
- ✅ Validates data integrity automatically
- ✅ Provides detailed logging and error reporting
- ✅ Can be run for all pairs or specific pairs
- ✅ Supports multiple granularities
- ✅ Non-destructive and idempotent

**Quick Start**:
```powershell
# Test everything with defaults
python tests/ingestion/test_candle_ingestion.py

# Check the logs directory for detailed output
dir logs\test_candle_ingestion_*.log
```

For questions or issues, review the troubleshooting section or check the log files for detailed error information.
