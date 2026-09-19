# Scheduler Jobs Documentation

## Overview

The CryptoQuant scheduler runs automated jobs for data ingestion and technical analysis. Jobs are defined in `config/jobs.yaml` and implemented in `src/cryptoquant/scheduling/jobs.py`.

## Job Architecture

### Key Components

1. **Scheduler** (`scripts/run_scheduler.py`)
   - Long-running process that manages all scheduled jobs
   - Reads configuration from `config/jobs.yaml`
   - Handles job execution, error recovery, and logging

2. **Job Definitions** (`config/jobs.yaml`)
   - YAML configuration defining what jobs run and when
   - No code changes needed to modify schedules
   - Supports cron and interval scheduling

3. **Job Implementations** (`src/cryptoquant/scheduling/jobs.py`)
   - Python functions that execute the actual work
   - Thin wrappers around application layer functions
   - Built-in retry logic and error handling

### Job Execution Flow

```
┌─────────────────────────────────────────────────┐
│ scripts/run_scheduler.py                        │
│ - Reads config/jobs.yaml                        │
│ - Creates APScheduler instance                  │
│ - Registers enabled jobs                        │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│ Job Trigger (Interval or Cron)                  │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│ Job Function (in jobs.py)                       │
│ - Implements retry logic (3 attempts)           │
│ - Delegates to application layer                │
│ - Logs results and errors                       │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│ Application Layer                                │
│ - run_ingestion() for data collection           │
│ - analyze_all_pairs() for technical analysis    │
└─────────────────────────────────────────────────┘
```

---

## Available Jobs

### 1. Incremental OHLCV Data Ingestion

**Job ID**: `incremental_ingestion`  
**Function**: `incremental_ingestion_job()`  
**Schedule**: Every 4 hours (240 minutes)  
**Status**: ✅ Enabled by default

#### Purpose
Fetches new hourly OHLCV (Open, High, Low, Close, Volume) data from Coinbase for all tracked trading pairs. Uses watermark logic to only fetch data since the last ingestion timestamp.

#### Behavior
- **Incremental Mode**: Starts from last ingested timestamp for each pair
- **Fallback**: If no previous data exists, fetches 7 days as initial seed
- **Granularity**: Hourly candles
- **Retry Logic**: 3 attempts with 60-second delays
- **Error Handling**: Individual pair failures don't stop other pairs

#### Configuration
```yaml
- id: incremental_ingestion
  name: "Incremental OHLCV Data Ingestion"
  enabled: true
  run_on_startup: false
  type: interval
  interval_minutes: 240
  function: incremental_ingestion_job
  parameters:
    granularity: hourly
```

#### Manual Testing (PowerShell)

**Option 1: Test via Python REPL**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run incremental ingestion
python -c "from cryptoquant.scheduling.jobs import incremental_ingestion_job; incremental_ingestion_job()"
```

**Option 2: Test via dedicated script**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run incremental ingestion for 1 day
python scripts/collect_historic_data.py --incremental
```

**Option 3: Test specific pair**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Test BTC-USD only
python scripts/collect_historic_data.py --incremental --product-id BTC-USD
```

#### Expected Output
```
2026-08-26 18:05:01 [INFO] Incremental ingestion started
2026-08-26 18:05:02 [INFO] Processing 4 pair(s) in incremental mode
2026-08-26 18:05:02 [INFO] BTC-USD: Incremental from 2026-08-23 15:00:00
2026-08-26 18:05:05 [INFO] Completed BTC-USD: 72 inserted, 0 skipped, 0 errors
...
2026-08-26 18:05:15 [INFO] incremental_ingestion_job: completed — inserted=288, skipped=0, errors=0
```

#### Monitoring
- **Log Files**: `logs/scheduler_YYYYMMDD.log`
- **Database**: Check `crypto.market_prices` for new records
- **Validation SQL**: Run `tests/sql/test_ingestion_market_price.sql`

---

### 2. Incremental Technical Analysis

**Job ID**: `incremental_technical_analysis`  
**Function**: `incremental_technical_analysis_job()`  
**Schedule**: Every 4 hours (240 minutes)  
**Status**: ✅ Enabled by default

#### Purpose
Calculates technical indicators (EMA 200, RSI 14, MACD, ATR 14) for new candles. Processes data since the last analysis timestamp for each pair.

#### Behavior
- **Incremental Mode**: Starts from last analysis timestamp for each pair
- **Fallback**: If no previous analysis exists, processes from 7 days ago
- **Warm-up**: Requires 200 hourly candles (for EMA 200) before calculating
- **Retry Logic**: 3 attempts with 60-second delays
- **Dependency**: Requires `incremental_ingestion` to run first

#### Configuration
```yaml
- id: incremental_technical_analysis
  name: "Incremental Technical Analysis"
  enabled: true
  run_on_startup: false
  type: interval
  interval_minutes: 240
  function: incremental_technical_analysis_job
  parameters:
    calculation_version: v1
```

#### Manual Testing (PowerShell)

**Option 1: Test via Python REPL**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run incremental technical analysis
python -c "from cryptoquant.scheduling.jobs import incremental_technical_analysis_job; incremental_technical_analysis_job()"
```

**Option 2: Test via dedicated script (incremental mode)**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run incremental analysis for all pairs
python scripts/calculate_technical_analysis.py --mode incremental
```

**Option 3: Test specific pair**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Test BTC-USD only
python scripts/calculate_technical_analysis.py --mode incremental --pair BTC-USD
```

**Option 4: Test with specific date range (historical mode)**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Calculate for last 30 days
python scripts/calculate_technical_analysis.py --mode historical --days 30

# Or specific date range
python scripts/calculate_technical_analysis.py --mode historical --start 2026-07-01 --end 2026-07-31
```

#### Expected Output
```
2026-08-26 18:10:01 [INFO] incremental_technical_analysis_job: started
2026-08-26 18:10:02 [INFO] Analyzing 4 tracked pairs
2026-08-26 18:10:02 [INFO] Processing BTC-USD
2026-08-26 18:10:05 [INFO] BTC-USD: Processed 72 candles, saved 72 analyses
...
2026-08-26 18:10:15 [INFO] incremental_technical_analysis_job: completed — 4 pairs analyzed, 288 analyses saved, 0 errors
```

#### Monitoring
- **Log Files**: `logs/scheduler_YYYYMMDD.log`
- **Database**: Check `crypto.technical_analysis` for new records
- **Validation SQL**: Run `tests/sql/test_ingestion_technical_analysis.sql`
- **Verification**: Run `python scripts/verify_technical_analysis.py --pair BTC-USD`

---

### 3. Historic OHLCV Data Ingestion

**Job ID**: `historic_ingestion`  
**Function**: `historic_ingestion_job()`  
**Schedule**: Daily at 2:00 AM (cron: `0 2 * * *`)  
**Status**: ⚠️ Disabled by default (for manual backfills)

#### Purpose
Fetches historical OHLCV data for a specified lookback period. Used for initial data population or filling gaps.

#### Behavior
- **Historical Mode**: Fetches N days back from now
- **Configurable**: Reads from environment variables
- **Retry Logic**: 3 attempts with 60-second delays
- **Use Case**: Typically disabled; enabled temporarily for backfills

#### Configuration
```yaml
- id: historic_ingestion
  name: "Historic OHLCV Data Ingestion"
  enabled: false
  run_on_startup: false
  type: cron
  cron: "0 2 * * *"
  function: historic_ingestion_job
  parameters:
    granularity: daily
    lookback_days: 7
```

#### Manual Testing (PowerShell)

**Option 1: Test specific time range**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Backfill last 30 days
python scripts/collect_historic_data.py --granularity hourly --days 30
```

**Option 2: Test large backfill (3 years)**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Backfill 3 years of hourly data
python scripts/collect_historic_data.py --granularity hourly --days 1095

# Or use year calculation (3 * 365)
python scripts/collect_historic_data.py --granularity hourly --days 1095
```

**Option 3: Test specific pair**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Backfill BTC-USD only
python scripts/collect_historic_data.py --granularity hourly --days 30 --product-id BTC-USD
```

#### Expected Output
```
2026-08-26 02:00:01 [INFO] historic_ingestion_job: started
2026-08-26 02:00:02 [INFO] Processing 4 pair(s) in historical mode
2026-08-26 02:00:02 [INFO] BTC-USD: Historical load, fetching 7 days
2026-08-26 02:01:30 [INFO] Completed BTC-USD: 168 inserted, 0 skipped, 0 errors
...
2026-08-26 02:05:00 [INFO] historic_ingestion_job: completed — inserted=672, skipped=0, errors=0
```

#### When to Enable
- Initial setup: Load 2-3 years of historical data
- Gap filling: After extended downtime
- Data quality: Re-ingest after identifying coverage issues

---

### 4. Weekly Data Gap Backfill

**Job ID**: `weekly_backfill`  
**Function**: `weekly_backfill_job()`  
**Schedule**: Weekly (Sunday at 3:00 AM)  
**Status**: ✅ Enabled by default

#### Purpose
Detects and fills specific data gaps in market prices and technical analysis. Unlike full re-ingestion, this job identifies exact gap boundaries and only fetches missing data, making it efficient for routine maintenance.

#### Behavior
- **Gap Detection**: Uses SQL LEAD window function to find gaps > 1 hour
- **Smart Backfill**: Only fetches data for specific gap time ranges
- **Two-Phase Process**:
  1. Backfills missing candles (market_prices)
  2. Runs incremental technical analysis for any missing analysis records
- **Retry Logic**: 3 attempts with 60-second delays
- **Timeout**: 1 hour per attempt

#### Configuration
```yaml
- id: weekly_backfill
  name: "Weekly Data Gap Backfill"
  enabled: true
  run_on_startup: false
  type: cron
  cron: "0 3 * * 0"  # Every Sunday at 3:00 AM
  function: weekly_backfill_job
  parameters: {}
```

#### Manual Testing (PowerShell)

**Option 1: Backfill candles only**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Detect and backfill candle gaps
python scripts/run_backfill.py --type candles
```

**Option 2: Backfill analysis only**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Backfill technical analysis gaps
python scripts/run_backfill.py --type analysis
```

**Option 3: Backfill both (default)**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run full backfill (candles + analysis)
python scripts/run_backfill.py --type all
```

**Option 4: Interactive gap detection**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Open gap detection notebook
jupyter notebook tests/backfill/detect_candle_gaps.ipynb

# Or for analysis gaps
jupyter notebook tests/backfill/detect_analysis_gaps.ipynb
```

#### Expected Output
```
2026-08-31 22:34:24 [INFO] BACKFILL JOB STARTED
2026-08-31 22:34:24 [INFO] Type: candles
2026-08-31 22:34:26 [INFO] Detected 19 gap(s) to backfill
2026-08-31 22:34:26 [INFO]   BTC-USD: 6 gap(s), ~270 hours missing
2026-08-31 22:34:26 [INFO]   ETH-USD: 7 gap(s), ~246 hours missing
2026-08-31 22:34:26 [INFO] [1/19] Processing gap for BTC-USD
2026-08-31 22:34:26 [INFO] Gap period: 2024-05-04 09:00:00+00:00 to 2024-05-08 15:00:00+00:00
2026-08-31 22:35:01 [INFO] BACKFILL COMPLETE: BTC-USD - Inserted: 103, Skipped: 0, Errors: 0
...
2026-08-31 22:38:08 [INFO] BACKFILL COMPLETE - Total inserted: 653, Total skipped: 0, Total errors: 0
```

#### Monitoring
- **Log Files**: `logs/backfill_YYYYMMDD_HHMMSS.log`
- **Gap Detection**: Use notebooks in `tests/backfill/`
- **Validation**: Re-run gap detection notebooks after backfill

#### Key Benefits
- **Efficient**: Only fetches missing data, not entire historical periods
- **Automated**: Runs weekly without manual intervention
- **Precise**: Identifies exact gap boundaries down to the hour
- **Safe**: Doesn't duplicate existing data

#### Documentation
See [docs/backfill/BACKFILL_SYSTEM.md](../backfill/BACKFILL_SYSTEM.md) for comprehensive backfill documentation including:
- Gap detection notebooks
- Backfill module API
- Testing procedures
- Troubleshooting guide

---

## Job Management

### Starting the Scheduler

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Start scheduler (runs indefinitely)
python scripts/run_scheduler.py
```

### Stopping the Scheduler

Press `Ctrl+C` to gracefully shut down. Jobs will complete their current execution before stopping.

### Enabling/Disabling Jobs

Edit `config/jobs.yaml` and change the `enabled` field:

```yaml
- id: incremental_ingestion
  enabled: true  # Set to false to disable
```

Restart the scheduler to apply changes.

### Changing Schedules

**Interval Jobs** (run every N minutes):
```yaml
type: interval
interval_minutes: 240  # Change to desired interval
```

**Cron Jobs** (run at specific times):
```yaml
type: cron
cron: "0 2 * * *"  # Daily at 2:00 AM
```

Common cron patterns:
- `0 * * * *` - Every hour
- `0 */4 * * *` - Every 4 hours
- `0 2 * * *` - Daily at 2:00 AM
- `0 0 * * 0` - Every Sunday at midnight
- `30 1 * * 1-5` - Weekdays at 1:30 AM

---

## Monitoring and Troubleshooting

### Log Files

All job execution logs are written to:
```
logs/scheduler_YYYYMMDD.log
```

Example log entries:
```
2026-08-26 18:05:01 [INFO] apscheduler.executors.default - Running job "Incremental OHLCV Data Ingestion"
2026-08-26 18:05:01 [INFO] cryptoquant.scheduling.jobs - incremental_ingestion_job: started
2026-08-26 18:05:15 [INFO] cryptoquant.scheduling.jobs - incremental_ingestion_job: completed — inserted=288, skipped=0, errors=0
```

### Checking Job Status

**View recent logs:**
```powershell
# View last 50 lines
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log -Tail 50

# Follow logs in real-time
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log -Wait
```

**Check database for latest data:**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Check market prices
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(MarketPrice.timestamp)).scalar()}'); s.close()"

# Check technical analysis
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import TechnicalAnalysis; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(TechnicalAnalysis.timestamp)).scalar()}'); s.close()"
```

### Common Issues

#### Issue: Job fails with timezone error
**Symptom**: `can't subtract offset-naive and offset-aware datetimes`  
**Solution**: Ensure you've pulled the latest code with timezone fix (commit `56b022f`)

```powershell
git pull origin dev
```

#### Issue: Technical analysis job reports "insufficient data"
**Symptom**: Job completes but saves 0 analyses  
**Solution**: EMA 200 requires 200 candles (8.33 days). Ensure you have sufficient market_prices data.

```powershell
# Check if you have enough data
python scripts/verify_technical_analysis.py --pair BTC-USD
```

#### Issue: Connection pool errors
**Symptom**: Job hangs or fails with "connection pool ping failure"  
**Solution**: Already fixed in Phase 1 (commit `c19a556`). Ensure you have the latest code.

#### Issue: Scheduler stops unexpectedly
**Solution**: Check system resources, ensure Azure SQL database is accessible, review logs for exceptions.

---

## Production Deployment

### Recommended Configuration

For production on the mini PC, use these settings in `config/jobs.yaml`:

```yaml
jobs:
  # Every 4 hours - collect new data
  - id: incremental_ingestion
    enabled: true
    interval_minutes: 240
    
  # Every 4 hours - calculate indicators (after ingestion)
  - id: incremental_technical_analysis
    enabled: true
    interval_minutes: 240
    
  # Disabled - only enable for manual backfills
  - id: historic_ingestion
    enabled: false
```

### Running as Background Service (Windows)

**Option 1: PowerShell Background Job**
```powershell
# Activate and start in background
.\.venv\Scripts\Activate.ps1
Start-Job -ScriptBlock { python scripts/run_scheduler.py }

# Check status
Get-Job

# Stop background job
Stop-Job -Id 1  # Replace with actual job ID
```

**Option 2: Windows Task Scheduler**
1. Open Task Scheduler
2. Create new task: Run `python scripts/run_scheduler.py`
3. Set trigger: At system startup
4. Configure: Run whether user is logged on or not

**Option 3: NSSM (Non-Sucking Service Manager)**
```powershell
# Download NSSM from nssm.cc
nssm install CryptoQuantScheduler "D:\data\development\crypto\.venv\Scripts\python.exe" "D:\data\development\crypto\scripts\run_scheduler.py"
nssm start CryptoQuantScheduler
```

### Health Checks

Create a monitoring script to verify jobs are running:

```powershell
# Save as scripts/check_scheduler_health.ps1
$logFile = "logs/scheduler_$(Get-Date -Format 'yyyyMMdd').log"
$recentLogs = Get-Content $logFile -Tail 100
$completedJobs = $recentLogs | Select-String "completed"

if ($completedJobs) {
    Write-Host "✓ Scheduler is running - $($completedJobs.Count) completed jobs in last 100 lines"
} else {
    Write-Host "⚠ WARNING: No completed jobs found in recent logs"
}
```

---

## Testing Workflow

### Complete End-to-End Test

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Step 1: Test incremental ingestion
Write-Host "`n=== Testing Incremental Ingestion ===" -ForegroundColor Cyan
python -c "from cryptoquant.scheduling.jobs import incremental_ingestion_job; incremental_ingestion_job()"

# Step 2: Test technical analysis
Write-Host "`n=== Testing Technical Analysis ===" -ForegroundColor Cyan
python -c "from cryptoquant.scheduling.jobs import incremental_technical_analysis_job; incremental_technical_analysis_job()"

# Step 3: Verify data
Write-Host "`n=== Verifying Results ===" -ForegroundColor Cyan
python scripts/verify_technical_analysis.py --pair BTC-USD

Write-Host "`n✓ All tests complete!" -ForegroundColor Green
```

### Quick Validation Commands

```powershell
# Check if scheduler is running
Get-Process python | Where-Object { $_.CommandLine -like "*run_scheduler*" }

# Count records in last hour
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; from datetime import datetime, timedelta; s = get_session(); count = s.query(func.count(MarketPrice.id)).filter(MarketPrice.timestamp >= datetime.utcnow() - timedelta(hours=1)).scalar(); print(f'Records in last hour: {count}'); s.close()"

# Check for errors in logs
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log | Select-String "ERROR"
```

---

## Next Steps

1. **Enable Jobs**: Ensure both `incremental_ingestion` and `incremental_technical_analysis` are enabled
2. **Start Scheduler**: Run `python scripts/run_scheduler.py`
3. **Monitor Logs**: Check `logs/scheduler_YYYYMMDD.log` for job execution
4. **Validate Data**: Run SQL validation scripts in `tests/sql/`
5. **Phase 3**: Implement scoring and signal generation logic

---

## References

- **Scheduler Implementation**: `src/cryptoquant/scheduling/scheduler.py`
- **Job Functions**: `src/cryptoquant/scheduling/jobs.py`
- **Job Configuration**: `config/jobs.yaml`
- **Ingestion Pipeline**: `src/cryptoquant/ingestion/historic.py`
- **Analytics Pipeline**: `src/cryptoquant/analytics/analytics_pipeline.py`
- **CLI Scripts**: `scripts/collect_historic_data.py`, `scripts/calculate_technical_analysis.py`
