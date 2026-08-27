# Quick Test Commands for Mini PC

## Setup
```powershell
cd D:\data\development\crypto
.\.venv\Scripts\Activate.ps1
```

---

## Manual Job Testing

### Incremental Ingestion Job
```powershell
python -c "from cryptoquant.scheduling.jobs import incremental_ingestion_job; incremental_ingestion_job()"
```

### Incremental Technical Analysis Job
```powershell
python -c "from cryptoquant.scheduling.jobs import incremental_technical_analysis_job; incremental_technical_analysis_job()"
```

### Historic Ingestion Job (7 days lookback)
```powershell
python -c "from cryptoquant.scheduling.jobs import historic_ingestion_job; historic_ingestion_job()"
```

---

## Historical Backfill (Manual)

### Candles - 30 days
```powershell
python scripts/collect_historic_data.py --granularity hourly --days 30
```

### Candles - 2 years
```powershell
python scripts/collect_historic_data.py --granularity hourly --days 730
```

### Technical Analysis - 30 days
```powershell
python scripts/calculate_technical_analysis.py --mode historical --days 30
```

### Technical Analysis - 2 years
```powershell
python scripts/calculate_technical_analysis.py --mode historical --days 730
```

### Run Both Together (Candles + Analysis)
```powershell
# Step 1: Ingest candles
python scripts/collect_historic_data.py --granularity hourly --days 730

# Step 2: Calculate analysis (after candles complete)
python scripts/calculate_technical_analysis.py --mode historical --days 730
```

---

## Start Scheduler
```powershell
python scripts/run_scheduler.py
```

---

## Quick Validation
```powershell
# Latest market prices
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(MarketPrice.timestamp)).scalar()}'); s.close()"

# Latest technical analysis
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import TechnicalAnalysis; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(TechnicalAnalysis.timestamp)).scalar()}'); s.close()"
```
- Reports: `X pairs analyzed, Y analyses saved, 0 errors`
- Each analysis includes: EMA 200, RSI 14, MACD, ATR 14

---

## Test 3: Verify Technical Analysis Results

**Check BTC-USD indicators:**
```powershell
python scripts/verify_technical_analysis.py --pair BTC-USD
```

**Expected output:**
- Shows recent timestamps with calculated indicators
- EMA 200: ~68,000-70,000 range
- RSI 14: 0-100 range
- MACD: positive or negative values
- ATR 14: volatility measure

---

## Test 4: Run Complete End-to-End Test

```powershell
# Step 1: Ingest new data
Write-Host "`n=== Step 1: Incremental Ingestion ===" -ForegroundColor Cyan
python -c "from cryptoquant.scheduling.jobs import incremental_ingestion_job; incremental_ingestion_job()"

# Step 2: Calculate indicators
Write-Host "`n=== Step 2: Technical Analysis ===" -ForegroundColor Cyan
python -c "from cryptoquant.scheduling.jobs import incremental_technical_analysis_job; incremental_technical_analysis_job()"

# Step 3: Verify results
Write-Host "`n=== Step 3: Verify Results ===" -ForegroundColor Cyan
python scripts/verify_technical_analysis.py --pair BTC-USD

Write-Host "`n✓ All tests complete!" -ForegroundColor Green
```

---

## Test 5: Start the Scheduler

**Run the scheduler (runs indefinitely):**
```powershell
python scripts/run_scheduler.py
```

**What it does:**
- Runs both jobs every 4 hours (240 minutes)
- Logs to: `logs/scheduler_YYYYMMDD.log`
- Press `Ctrl+C` to stop

**Monitor logs in real-time:**
```powershell
# In a separate PowerShell window
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log -Wait
```

---

## Quick Validation Commands

**Check latest market prices timestamp:**
```powershell
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(MarketPrice.timestamp)).scalar()}'); s.close()"
```

**Check latest technical analysis timestamp:**
```powershell
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import TechnicalAnalysis; from sqlalchemy import func; s = get_session(); print(f'Latest: {s.query(func.max(TechnicalAnalysis.timestamp)).scalar()}'); s.close()"
```

**Count records in last 24 hours:**
```powershell
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; from datetime import datetime, timedelta, timezone; s = get_session(); count = s.query(func.count(MarketPrice.id)).filter(MarketPrice.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24)).scalar(); print(f'Records in last 24h: {count}'); s.close()"
```

**Check for errors in today's logs:**
```powershell
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log | Select-String "ERROR"
```

---

## Troubleshooting

### If timezone error occurs:
```powershell
# Ensure you have the latest code with timezone fix
git pull origin dev
git log --oneline -1  # Should show commit with timezone fix
```

### If jobs show errors:
```powershell
# Check the full log file
Get-Content logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log -Tail 100

# Or check ingestion log
Get-Content logs\historic_ingestion_*.log -Tail 50 | Sort-Object
```

### If "insufficient data" warning:
```powershell
# EMA 200 requires 200 hourly candles (8.33 days)
# Check if you have enough data
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import MarketPrice; from sqlalchemy import func; s = get_session(); count = s.query(func.count(MarketPrice.id)).filter(MarketPrice.trading_pair_id == 1).scalar(); print(f'BTC-USD candles: {count} (need at least 200 for EMA)'); s.close()"
```

---

## Configuration Files

**Job configuration:** `config/jobs.yaml`
```yaml
jobs:
  - id: incremental_ingestion
    enabled: true           # Set to false to disable
    interval_minutes: 240   # Change interval here

  - id: incremental_technical_analysis
    enabled: true           # Set to false to disable
    interval_minutes: 240   # Change interval here
```

**After editing config:**
1. Stop the scheduler (`Ctrl+C`)
2. Restart: `python scripts/run_scheduler.py`

---

## What's Running on Mini PC

Based on your logs, these jobs should be running:

1. **Incremental Ingestion** - Every 4 hours
   - Fetches new hourly candles for all 4 pairs
   - Fixed: Timezone issue resolved (commit `56b022f`)

2. **Incremental Technical Analysis** - Every 4 hours
   - Calculates EMA, RSI, MACD, ATR for new candles
   - New: Just added to config

**Next run:** Check logs for next execution time

---

## Success Indicators

✅ **Jobs are working if you see:**
- No ERROR messages in logs
- `completed — inserted=X, skipped=Y, errors=0`
- Latest timestamps within last 4 hours
- Database records increasing every 4 hours

⚠️ **Investigate if you see:**
- ERROR messages in logs
- `errors=X` where X > 0
- Jobs not completing
- Timestamps not updating

---

## Reference

Full documentation: `docs/scheduler/SCHEDULER_JOBS.md`
