# Backfill System Documentation

## Overview

The backfill system is designed to detect and fill specific data gaps in both market prices (candles) and technical analysis, without needing to re-ingest entire historical periods.

## Components

### 1. Gap Detection Notebooks

Located in `tests/backfill/`:

#### `detect_candle_gaps.ipynb`
- Detects all gaps in market_prices data (> 1 hour)
- Shows exact timestamps for each gap
- Generates Python code to backfill specific gaps
- Provides gap summary by trading pair

**Key Query**: Identifies gaps by checking consecutive timestamps using LEAD window function.

#### `detect_analysis_gaps.ipynb`
- Detects market_prices without corresponding technical_analysis
- Identifies gaps in existing analysis sequences
- Generates commands to run incremental analysis
- Accounts for 200-hour EMA warmup period

### 2. Backfill Module

**File**: `src/cryptoquant/ingestion/backfill.py`

**Key Functions**:

- `backfill_candle_gap(product_id, start_date, end_date, granularity='hourly')`
  - Fills a single specific gap
  - Takes timezone-aware UTC datetime objects
  - Returns statistics: inserted, skipped, errors

- `backfill_multiple_gaps(gaps, granularity='hourly')`
  - Fills multiple gaps in sequence
  - Takes list of gap dictionaries
  - Returns aggregate statistics

**Example Usage**:
```python
from datetime import datetime, timezone
from cryptoquant.ingestion.backfill import backfill_candle_gap

stats = backfill_candle_gap(
    product_id='BTC-USD',
    start_date=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    end_date=datetime(2026, 8, 15, 15, 0, 0, tzinfo=timezone.utc),
    granularity='hourly'
)
print(f'Inserted: {stats["inserted"]}, Skipped: {stats["skipped"]}')
```

### 3. Backfill Script

**File**: `scripts/run_backfill.py`

**Usage**:
```bash
# Backfill candles only
python scripts/run_backfill.py --type candles

# Backfill analysis only
python scripts/run_backfill.py --type analysis

# Backfill both (default)
python scripts/run_backfill.py --type all
```

**Process**:
1. Queries database for gaps
2. Removes configured unfillable hours from candle and analysis gaps
3. For remaining candle gaps: calls `backfill_multiple_gaps()`
4. Runs incremental candle ingestion to catch up and refresh recent candles
5. For analysis: recalculates recent rows and catches up any newer candles
6. Logs all operations to `logs/backfill_YYYYMMDD_HHMMSS.log`

### Ignoring known-unfillable gaps

`config/backfill_ignore.yaml` lists inclusive UTC candle hours that Coinbase
does not return. The two ranges already observed across all tracked pairs are
configured there. Entries without `product_id` apply to every pair; specify a
pair to scope an exception. If an ignored range overlaps only part of a gap,
the uncovered hours are still backfilled. Add a new entry only after confirming
the source has no candles for that range. A missing config file means no gaps
are ignored.

```yaml
ignore:
   - start: "2026-05-08T02:00:00Z"
      end: "2026-05-08T06:00:00Z"
      reason: "Coinbase returns no candles for this range"
```

### Refreshing recent candles and analysis

Incremental candle ingestion re-fetches from two hours before the current UTC
hour. Existing candle timestamps are updated if Coinbase returns changed OHLCV
values, unchanged rows are counted as skipped, and new timestamps are inserted.
This corrects a recent candle if ingestion previously ran before its hour had
closed.

Incremental technical analysis uses the same two-hour refresh boundary. It
recalculates those candles and updates existing analysis rows by
`market_price_id`. If analysis is farther behind, it starts after the latest
analysis timestamp so older unprocessed candles are not missed. Running
`python scripts/run_backfill.py --type all` performs candle catch-up before
analysis, so refreshed candles are used as inputs.

### 4. Scheduled Job

**File**: `src/cryptoquant/scheduling/jobs.py`

**Function**: `weekly_backfill_job()`
- Configured to run weekly (Sunday at 3:00 AM)
- Executes `run_backfill.py --type all`
- Includes retry logic (3 attempts with 60s delays)
- 1-hour timeout per attempt

**Configuration**: `config/jobs.yaml`
```yaml
- id: weekly_backfill
  name: "Weekly Data Gap Backfill"
  enabled: true
  run_on_startup: false
  type: cron
  cron: "0 3 * * 0"  # Every Sunday at 3:00 AM
  function: weekly_backfill_job
```

## Workflow

### Interactive Backfill (Manual)

1. **Detect Gaps**:
   ```bash
   # Open Jupyter notebook
   jupyter notebook tests/backfill/detect_candle_gaps.ipynb
   
   # Run all cells to see gaps
   ```

2. **Review Gaps**:
   - Cell 3 shows all gaps with timestamps
   - Cell 4 shows summary by pair
   - Cell 5 generates Python code to backfill

3. **Execute Backfill**:
   - Copy generated code from Cell 5
   - Paste into Cell 6 and run
   - OR use the CLI script:
     ```bash
     python scripts/run_backfill.py --type candles
     ```

### Automated Backfill (Scheduled)

1. **Enable Job** (already enabled by default):
   ```yaml
   # config/jobs.yaml
   - id: weekly_backfill
     enabled: true
   ```

2. **Start Scheduler**:
   ```bash
   python scripts/run_scheduler.py
   ```

3. **Monitor Logs**:
   ```bash
   # Scheduler logs
   tail -f logs/scheduler_*.log
   
   # Backfill logs
   tail -f logs/backfill_*.log
   ```

## Key Features

### Smart Gap Detection

Unlike full re-ingestion, the system:
- Identifies exact gap boundaries
- Only fetches missing data
- Avoids duplicate API calls
- Minimizes database writes

**Example**: If you have a 5-hour gap from 2026-08-15 10:00 to 2026-08-15 15:00, the system:
- Detects: gap_start=10:00, gap_end=15:00
- Fetches: Only those 5 hours of data
- Inserts: Only the missing candles

### Timezone Handling

All datetime objects MUST be timezone-aware (UTC):
```python
# ✅ Correct
start = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)

# ❌ Wrong (will raise ValueError)
start = datetime(2026, 8, 15, 10, 0, 0)  # No timezone
```

### Error Handling

- Database connection retries (3 attempts)
- Individual gap failures don't stop batch processing
- Comprehensive logging at INFO level
- Errors logged with full stack traces

## Testing

### Test Candle Backfill

1. **Create a controlled gap**:
   ```sql
   -- Delete 5 hours of BTC-USD data
   DELETE FROM crypto.market_prices
   WHERE trading_pair_id = (SELECT id FROM crypto.trading_pairs WHERE symbol = 'BTC-USD')
     AND timestamp BETWEEN '2026-08-15 10:00:00' AND '2026-08-15 15:00:00'
   ```

2. **Detect the gap**:
   ```bash
   jupyter notebook tests/backfill/detect_candle_gaps.ipynb
   # Run all cells - should show the 5-hour gap
   ```

3. **Backfill the gap**:
   ```bash
   python scripts/run_backfill.py --type candles
   ```

4. **Verify**:
   ```bash
   # Re-run detection notebook - gap should be gone
   ```

### Test Analysis Backfill

1. **Create missing analysis**:
   ```sql
   -- Delete some technical_analysis records
   DELETE TOP (100) FROM crypto.technical_analysis
   WHERE trading_pair_id = (SELECT id FROM crypto.trading_pairs WHERE symbol = 'BTC-USD')
   ```

2. **Detect the gap**:
   ```bash
   jupyter notebook tests/backfill/detect_analysis_gaps.ipynb
   # Run all cells - should show missing records
   ```

3. **Backfill**:
   ```bash
   python scripts/run_backfill.py --type analysis
   ```

4. **Verify**:
   ```bash
   # Re-run detection notebook - should be complete
   ```

## Best Practices

1. **Run Detection First**: Always check for gaps before running backfill
2. **Review Generated Code**: Check the generated Python code before executing
3. **Monitor Logs**: Watch logs during backfill to catch issues early
4. **Test in Dev**: Test backfill on development database first
5. **Schedule Wisely**: Weekly schedule catches gaps without overloading the system

## Troubleshooting

### Issue: "No gaps detected" but data looks incomplete

**Solution**: Check if tracked_pairs are configured correctly:
```sql
SELECT * FROM crypto.tracked_pairs WHERE is_tracking_active = 1
```

### Issue: Backfill takes too long

**Solution**: 
- Large gaps can take time due to API rate limits
- Coinbase API chunks requests into 300-hour segments
- Monitor logs for progress: "Processing batch N/M"

### Issue: "Trading pair not found"

**Solution**: Ensure the pair exists in database:
```sql
SELECT * FROM crypto.trading_pairs WHERE symbol = 'BTC-USD'
```

### Issue: Timezone errors

**Solution**: Always use UTC timezone-aware datetimes:
```python
from datetime import datetime, timezone
start = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
```

## Performance Notes

- **Candle backfill**: ~300 hours per API request chunk
- **Analysis backfill**: Processes all eligible candles incrementally
- **Weekly job**: Typically completes in < 10 minutes for small gaps
- **Large gaps**: May take 30-60 minutes depending on size

## Future Enhancements

- [ ] Email notifications on gap detection
- [ ] Prometheus metrics for gap counts
- [ ] Auto-prioritization of critical gaps
- [ ] Parallel gap filling for multiple pairs
- [ ] Dashboard for gap visualization
