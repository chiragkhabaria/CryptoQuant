# Ingestion Resume and Watermark Guide

## Overview

This guide explains how the ingestion system handles restarts and uses watermark logic to avoid re-fetching data.

## Restart Behavior

### Historic Ingestion (Initial 3-Year Load)

**Question**: *If I restart historic ingestion after an error, does it resume or start from scratch?*

**Answer**: **It starts from scratch** by default, but **duplicates are automatically skipped**.

#### How It Works

1. **Script Behavior**:
   - The script always fetches the full date range you specify (e.g., 3 years)
   - Each candle has a timestamp that serves as a natural unique key
   - When inserting candles:
     - ✅ **New candles**: Inserted successfully
     - ⏭️ **Duplicate candles**: Skipped (database constraint prevents duplicates)
     - ❌ **Error candles**: Counted as errors

2. **Database Protection**:
   ```sql
   -- Unique constraint prevents duplicate timestamps per pair
   CONSTRAINT UQ_market_prices_pair_timestamp 
   UNIQUE (trading_pair_id, timestamp)
   ```

3. **Restart Example**:
   ```bash
   # Initial run: Fetches Jan 2023 - Dec 2025 (3 years)
   python scripts/collect_historic_data.py --days 1095 --granularity hourly
   # Progress: 50% complete → ERROR (communication failure)
   # Stats: 13,140 inserted, 0 skipped, 1 error
   
   # Restart: Fetches Jan 2023 - Dec 2025 again
   python scripts/collect_historic_data.py --days 1095 --granularity hourly
   # Progress: 100% complete
   # Stats: 13,140 inserted, 13,140 skipped, 0 errors
   #         └─ New data ──┘ └─ Already exists ─┘
   ```

#### Performance Considerations

- **Network**: Re-fetches from Coinbase API (uses bandwidth)
- **Processing**: Re-processes all candles in memory
- **Database**: Only writes new records (skips duplicates)

**Recommendation**: This approach is safe and idempotent. If you restart, you'll waste some API calls but won't corrupt data.

---

### Incremental Ingestion (Daily Updates)

**Question**: *How does incremental ingestion know where to start?*

**Answer**: **It uses watermark logic** - starts from the last ingested timestamp.

#### How Watermark Logic Works

1. **Check Last Timestamp**:
   ```python
   last_time = get_last_ingestion_time(session, trading_pair_id)
   # Returns: 2026-08-22 14:00:00 UTC (last candle in database)
   ```

2. **Calculate Start Date**:
   ```python
   if last_time:
       # Resume from last timestamp + 1 hour
       start_date = last_time + timedelta(hours=1)
   else:
       # No previous data - fetch 7 days as initial seed
       start_date = now - timedelta(days=7)
   ```

3. **Fetch Only New Data**:
   ```python
   # Fetch from last timestamp to now
   candles = client.get_candles(
       product_id="BTC-USD",
       granularity=CandleGranularity.ONE_HOUR,
       start=start_date,  # 2026-08-22 15:00:00
       end=now            # 2026-08-23 10:00:00
   )
   # Returns: Only 19 hours of new candles
   ```

#### Scheduled Incremental Job

The scheduler runs this automatically every 4 hours:

```yaml
# config/jobs.yaml
- id: incremental_ingestion
  name: "Incremental OHLCV Data Ingestion"
  enabled: true
  type: interval
  interval_minutes: 240  # Every 4 hours
  function: incremental_ingestion_job
```

**Timeline Example**:
```
00:00 UTC → Job runs → Fetches last 4 hours of data
04:00 UTC → Job runs → Fetches last 4 hours of data
08:00 UTC → Job runs → Fetches last 4 hours of data
12:00 UTC → Job runs → Fetches last 4 hours of data
```

---

## Error Recovery

### New Features (Fixed Issues)

#### 1. **Retry Logic**
- **Attempts**: 3 retries per operation
- **Delay**: 30 seconds between retries
- **Scope**: Applied to both individual candle insertion and batch commits

```python
# Automatic retry example
retry_count = 0
while retry_count <= 3:
    try:
        session.commit()
        break  # Success
    except OperationalError as exc:
        retry_count += 1
        if retry_count <= 3:
            log.warning("Retry %d/3 in 30s...", retry_count)
            time.sleep(30)
        else:
            log.error("Failed after 3 attempts")
```

#### 2. **Transaction Cleanup**
- **Old Behavior**: Communication failures left invalid transactions
- **New Behavior**: Automatic `session.rollback()` after any error

```python
except (OperationalError, DBAPIError) as exc:
    session.rollback()  # Clean up invalid transaction
    # Retry logic continues...
```

#### 3. **Robust Logging**
- **Log Directory**: Auto-created with fallback
- **File Errors**: Falls back to console-only logging
- **Encoding**: UTF-8 with error handling for Windows

---

## Best Practices

### For 3-Year Historic Load

```bash
# 1. Start the ingestion
python scripts/collect_historic_data.py --days 1095 --granularity hourly

# 2. If it fails midway, just restart it
#    (Duplicates will be skipped automatically)
python scripts/collect_historic_data.py --days 1095 --granularity hourly

# 3. Check the logs
tail -f logs/historic_ingestion_*.log

# 4. Verify data integrity
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
```

### For Daily Updates

```bash
# 1. Enable the scheduled job
# Edit config/jobs.yaml:
#   incremental_ingestion:
#     enabled: true

# 2. Start the scheduler
python scripts/run_scheduler.py

# 3. Monitor logs
tail -f logs/scheduler.log
```

### For Manual Incremental Run

```python
from cryptoquant.ingestion.historic import run_ingestion

# Fetch only new data from last timestamp
stats = run_ingestion(
    granularity="hourly",
    incremental=True  # Uses watermark logic
)

print(f"Inserted: {stats['inserted']}, Skipped: {stats['skipped']}")
```

---

## Troubleshooting

### Issue: "Communication link failure"

**Cause**: Azure SQL connection timeout or network interruption

**Solution**: The system now automatically retries 3 times with 30s delay

**Logs**:
```
[WARNING] Database error inserting candle (attempt 1/3): Communication link failure. Retrying in 30s...
[WARNING] Database error inserting candle (attempt 2/3): Communication link failure. Retrying in 30s...
[INFO] Successfully inserted candle on attempt 3
```

### Issue: "Can't reconnect until invalid transaction is rolled back"

**Cause**: Previous error left transaction in invalid state

**Solution**: Fixed in latest version - automatic `session.rollback()` after errors

**Old Code** (caused issue):
```python
except Exception as exc:
    log.error(f"Error: {exc}")
    # Missing: session.rollback()
```

**New Code** (fixed):
```python
except (OperationalError, DBAPIError) as exc:
    session.rollback()  # Clean up transaction
    # Retry logic...
```

### Issue: "Logs not created"

**Cause**: Permission errors or missing log directory

**Solution**: Enhanced logging with automatic fallback

**Behavior**:
1. Try to create `logs/` directory
2. If fails → Fall back to console-only logging
3. Always log something (never silent failure)

---

## Summary

| Scenario | Behavior | Watermark? | Safe to Restart? |
|----------|----------|------------|------------------|
| **Historic ingestion** | Fetches full date range | ❌ No | ✅ Yes (skips duplicates) |
| **Incremental ingestion** | Fetches from last timestamp | ✅ Yes | ✅ Yes (idempotent) |
| **Scheduled job** | Runs every 4 hours | ✅ Yes | ✅ Yes (automatic) |

**Key Takeaway**: You can safely restart any ingestion process. Duplicates are automatically handled, and the watermark logic ensures you don't miss data.
