# CryptoQuant Mini PC Deployment Guide

## Complete Step-by-Step Setup for Brand New Windows PC

**Purpose**: Deploy CryptoQuant data collection system on a fresh Windows Mini PC with:
- Initial 3-year historical data ingestion (hourly candles)
- Automated daily incremental updates
- Production-ready scheduler configuration

**Prerequisites**: 
- Windows 10/11 Mini PC
- Internet connection
- Azure SQL Database credentials
- Coinbase API credentials

**Estimated Time**: 4-8 hours (most time is historical data loading)

---

## Phase 1: Software Installation (30 minutes)

### Step 1.1: Install Python 3.12+

1. **Download Python**:
   - Go to https://www.python.org/downloads/
   - Download Python 3.12 or later (64-bit Windows installer)

2. **Run Installer**:
   - ✅ Check "Add Python to PATH"
   - Click "Install Now"
   - Wait for completion

3. **Verify Installation**:
   ```powershell
   # Open PowerShell (Windows + X → Terminal/PowerShell)
   python --version
   # Should show: Python 3.12.x
   
   pip --version
   # Should show: pip 24.x.x
   ```

### Step 1.2: Install Git

1. **Download Git**:
   - Go to https://git-scm.com/download/win
   - Download 64-bit Git for Windows

2. **Run Installer**:
   - Use default settings
   - Select "Use Git from the Windows Command Prompt"
   - Click through installation

3. **Verify Installation**:
   ```powershell
   git --version
   # Should show: git version 2.x.x
   ```

### Step 1.3: Install ODBC Driver 18 for SQL Server

1. **Download Driver**:
   - Go to https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Download "ODBC Driver 18 for SQL Server (x64)"

2. **Run Installer**:
   - Accept license agreement
   - Use default installation path
   - Click "Install"

3. **Verify Installation**:
   ```powershell
   # Open ODBC Data Source Administrator
   odbcad32
   # Go to Drivers tab → should see "ODBC Driver 18 for SQL Server"
   ```

### Step 1.4: Install VS Code (Optional but Recommended)

1. **Download VS Code**:
   - Go to https://code.visualstudio.com/
   - Download Windows 64-bit installer

2. **Install**:
   - Use default settings
   - ✅ Check "Add to PATH"

---

## Phase 2: Project Setup (20 minutes)

### Step 2.1: Clone Repository

1. **Create Project Directory**:
   ```powershell
   # Create folder for the project
   mkdir D:\crypto
   cd D:\crypto
   ```

2. **Clone from Git** (if using Git):
   ```powershell
   git clone <your-repo-url> .
   ```
   
   **OR Copy Files Manually**:
   - Copy all project files to `D:\crypto\`

3. **Verify Structure**:
   ```powershell
   ls
   # Should see: src/, scripts/, config/, docs/, etc.
   ```

### Step 2.2: Create Virtual Environment

1. **Create venv**:
   ```powershell
   cd D:\crypto
   python -m venv .venv
   ```

2. **Activate venv**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   # Prompt should show (.venv)
   ```
   
   **If execution policy error occurs**:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   # Type Y to confirm, then retry activation
   ```

3. **Verify Activation**:
   ```powershell
   where python
   # Should show: D:\crypto\.venv\Scripts\python.exe
   ```

### Step 2.3: Install Dependencies

```powershell
# Ensure venv is activated (see (.venv) in prompt)
pip install --upgrade pip
pip install -e .
```

Wait for all packages to install (~5 minutes).

**Verify Installation**:
```powershell
pip list
# Should show: apscheduler, pyyaml, sqlalchemy, etc.
```

### Step 2.4: Configure Environment Variables

1. **Create .env File**:
   ```powershell
   notepad .env
   ```

2. **Add Configuration**:
   ```env
   # Database Configuration
   DATABASE_URL=mssql+pyodbc://USERNAME:PASSWORD@SERVER.database.windows.net:1433/DATABASE?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
   
   # Coinbase API Credentials
   COINBASE_API_KEY=organizations/YOUR_ORG_ID/apiKeys/YOUR_KEY_ID
   COINBASE_API_SECRET=YOUR_BASE64_ENCODED_SECRET
   COINBASE_BASE_URL=https://api.coinbase.com
   
   # Scheduler Configuration
   SCHEDULER_ENABLED=true
   SCHEDULER_JOBS_CONFIG=config/jobs.yaml
   
   # Ingestion Configuration
   INGESTION_GRANULARITY=hourly
   INGESTION_LOOKBACK_DAYS=1
   
   # Environment
   ENVIRONMENT=production
   ```

3. **Replace Placeholders**:
   - `USERNAME`, `PASSWORD`: Azure SQL credentials
   - `SERVER`: Your Azure SQL server (e.g., `myserver.database.windows.net`)
   - `DATABASE`: Database name (e.g., `fin-market-db`)
   - `COINBASE_API_KEY`: Your Coinbase API key
   - `COINBASE_API_SECRET`: Your Coinbase API secret

4. **Save and Close**: `Ctrl+S`, then close Notepad

### Step 2.5: Test Database Connection

```powershell
python -c "from cryptoquant.database.session import get_session; s = get_session(); print('✓ Database connected'); s.close()"
```

**Expected Output**: `✓ Database connected`

**If error occurs**:
- Check firewall: Azure SQL firewall allows your Mini PC IP
- Verify credentials in .env
- Test ODBC driver: `odbcad32` → Drivers tab

### Step 2.6: Verify Tracked Pairs

```powershell
python -c "from cryptoquant.database.session import get_session; from cryptoquant.database.models import TrackedPair; s = get_session(); pairs = s.query(TrackedPair).filter_by(is_tracking_active=True).all(); print(f'✓ Found {len(pairs)} tracked pairs'); [print(f'  - {p.product_id}') for p in pairs]; s.close()"
```

**Expected Output**:
```
✓ Found 4 tracked pairs
  - BTC-USD
  - ETH-USD
  - XRP-USD
  - SOL-USD
```

---

## Phase 3: Historical Data Load (2-6 hours)

### Step 3.1: Disable Scheduler

Edit `config/jobs.yaml`:
```yaml
jobs:
  - id: historic_ingestion
    enabled: false  # ← Disable during manual historical load
    ...
```

### Step 3.2: Clean Database (Optional - Fresh Start)

**WARNING**: This deletes ALL existing candle data.

```powershell
# Execute SQL cleanup script
# Option 1: Using sqlcmd
sqlcmd -S SERVER.database.windows.net -d DATABASE -U USERNAME -P PASSWORD -i tests\sql\cleanup_candles.sql

# Option 2: Manual SQL (Azure Data Studio/SSMS)
# Execute: DELETE FROM crypto.market_prices;
```

### Step 3.3: Run Historical Ingestion

**Important**: This will take 2-6 hours depending on API rate limits.

```powershell
# Activate venv if not already active
.\.venv\Scripts\Activate.ps1

# Run 3-year historical ingestion (1095 days)
python -c "from cryptoquant.ingestion.historic import run_ingestion; print('Starting 3-year historical ingestion...'); result = run_ingestion(granularity='hourly', days=1095); print(f'\n✓ Complete: {result}')"
```

**What to Expect**:
- Process runs for 2-6 hours
- Fetches ~26,280 candles per pair (3 years * 365 days * 24 hours)
- Total: ~105,000 candles (4 pairs)
- Console shows progress for each pair
- Duplicate handling: any existing candles are skipped

**Monitor Progress**:
```powershell
# Open new PowerShell window
cd D:\crypto
Get-Content logs\historic_YYYYMMDD.log -Wait
# Replace YYYYMMDD with today's date
```

**If Process Stops**:
- Check last successful timestamp in logs
- Calculate remaining days
- Re-run with adjusted days parameter
- Duplicate handling ensures no double-counting

### Step 3.4: Verify Historical Data

After completion, verify data loaded:

```sql
-- Run in Azure Data Studio or SSMS
SELECT 
    tp.symbol AS trading_pair,
    COUNT(*) AS total_candles,
    MIN(mp.timestamp) AS earliest_candle,
    MAX(mp.timestamp) AS latest_candle,
    DATEDIFF(day, MIN(mp.timestamp), MAX(mp.timestamp)) AS days_covered
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
GROUP BY tp.symbol
ORDER BY tp.symbol;
```

**Expected Results**:
| trading_pair | total_candles | earliest_candle | latest_candle | days_covered |
|--------------|---------------|-----------------|---------------|--------------|
| BTC-USD | ~26,280 | ~2023-08-20 | 2026-08-20 | ~1095 |
| ETH-USD | ~26,280 | ~2023-08-20 | 2026-08-20 | ~1095 |
| SOL-USD | ~26,280 | ~2023-08-20 | 2026-08-20 | ~1095 |
| XRP-USD | ~26,280 | ~2023-08-20 | 2026-08-20 | ~1095 |

**Success Criteria**:
- ✅ Each pair has ~26,000-27,000 candles
- ✅ Date range covers ~3 years
- ✅ No significant gaps in data

---

## Phase 4: Scheduler Configuration (15 minutes)

### Step 4.1: Enable Incremental Mode

Edit `config/jobs.yaml`:
```yaml
jobs:
  - id: historic_ingestion
    name: "Historic OHLCV Data Ingestion"
    enabled: true  # ← Re-enable for daily runs
    run_on_startup: false
    type: cron
    cron: "0 2 * * *"  # Daily at 2 AM UTC
    function: historic_ingestion_job
```

**Note**: The code changes ensure incremental mode is used (fetches from last timestamp).

### Step 4.2: Test Scheduler Locally

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Test with immediate run
# Temporarily set run_on_startup: true in jobs.yaml
python scripts\run_scheduler.py
```

**Expected Behavior**:
- Job runs immediately (run_on_startup: true)
- Fetches candles from last timestamp to now
- Should insert 0-24 new candles per pair (depending on gap)
- Logs show: `historic_ingestion_job: completed — inserted=X, skipped=0, errors=0`

**Stop Scheduler**: Press `Ctrl+C`

**Restore Config**: Set `run_on_startup: false` in jobs.yaml

### Step 4.3: Create Windows Task Scheduler Job

1. **Open Task Scheduler**:
   ```powershell
   taskschd.msc
   ```

2. **Create Task**:
   - Click "Create Task" (right panel)
   - **General Tab**:
     - Name: `CryptoQuant Data Scheduler`
     - Description: `Automated cryptocurrency data collection`
     - ✅ Run whether user is logged on or not
     - ✅ Run with highest privileges
   
   - **Triggers Tab**:
     - Click "New..."
     - Begin the task: `At startup`
     - ✅ Enabled
     - Click "OK"
   
   - **Actions Tab**:
     - Click "New..."
     - Action: `Start a program`
     - Program/script: `D:\crypto\.venv\Scripts\python.exe`
     - Add arguments: `scripts\run_scheduler.py`
     - Start in: `D:\crypto`
     - Click "OK"
   
   - **Conditions Tab**:
     - ❌ Uncheck "Start only if on AC power"
     - ❌ Uncheck "Stop if on battery power"
   
   - **Settings Tab**:
     - ✅ Allow task to be run on demand
     - ✅ Run task as soon as possible after scheduled start is missed
     - ✅ If the task fails, restart every: `5 minutes`, Attempt to restart up to: `3` times
     - Do not start a new instance: `Do not start a new instance`

3. **Save Task**:
   - Click "OK"
   - Enter Windows admin password when prompted

### Step 4.4: Test Auto-Start

1. **Run Task Manually**:
   - Right-click task → "Run"
   - Check Task Scheduler "Status" column: Should show "Running"

2. **Verify Logs**:
   ```powershell
   Get-Content D:\crypto\logs\scheduler_*.log -Tail 50
   ```

3. **Stop Task**:
   - Right-click task → "End"

4. **Test Reboot**:
   - Restart Mini PC
   - After reboot, check Task Scheduler: Task should be "Running"
   - Verify logs show scheduler started

---

## Phase 5: Verification & Monitoring (30 minutes)

### Step 5.1: Daily Verification

After 24 hours, check new data was ingested:

```sql
-- Check recent ingestion
SELECT 
    tp.symbol,
    MAX(mp.timestamp) AS latest_candle,
    COUNT(CASE WHEN mp.timestamp >= DATEADD(hour, -24, GETDATE()) THEN 1 END) AS candles_last_24h
FROM crypto.market_prices mp
JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
GROUP BY tp.symbol
ORDER BY tp.symbol;
```

**Expected**: `latest_candle` should be today's date, `candles_last_24h` should be ~24 per pair.

### Step 5.2: Log Monitoring

Check scheduler logs daily:

```powershell
# View today's log
Get-Content D:\crypto\logs\scheduler_*.log -Tail 100

# Search for errors
Select-String -Path D:\crypto\logs\*.log -Pattern "ERROR"
```

**Healthy Logs Show**:
```
[INFO] historic_ingestion_job: started
[INFO] Ingestion started: granularity=hourly, days=1, product_id=all
[INFO] Processing 4 pair(s) in incremental mode
[INFO] BTC-USD: Incremental from 2026-08-20 02:00:00+00:00
[INFO] Completed BTC-USD: 1 inserted, 0 skipped, 0 errors
[INFO] historic_ingestion_job: completed — inserted=4, skipped=0, errors=0
```

### Step 5.3: Alert Configuration (Optional)

Set up email alerts for errors:
1. Create PowerShell script to check logs for "ERROR"
2. Use Windows Task Scheduler to run script every 6 hours
3. Send email if errors found (using Send-MailMessage or external service)

---

## Troubleshooting

### Issue: Python Not Found
**Symptom**: `python: command not found`

**Solution**:
```powershell
# Find Python installation
where python
# Add to PATH if needed: Settings → System → Environment Variables
```

### Issue: Cannot Activate venv
**Symptom**: `Activate.ps1 cannot be loaded because running scripts is disabled`

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Database Connection Timeout
**Symptom**: `Login timeout expired`, `TCP Provider: Timeout error`

**Solution**:
1. Check Azure SQL firewall rules: Add Mini PC IP address
2. Verify credentials in .env
3. Test connectivity:
   ```powershell
   Test-NetConnection -ComputerName SERVER.database.windows.net -Port 1433
   ```

### Issue: Historical Load Incomplete
**Symptom**: Process stops before completing 3 years

**Solution**:
1. Check logs for last successful timestamp
2. Calculate remaining days: `remaining = 1095 - days_loaded`
3. Re-run with adjusted days:
   ```powershell
   python -c "from cryptoquant.ingestion.historic import run_ingestion; run_ingestion(days=REMAINING_DAYS)"
   ```

### Issue: Scheduler Not Running After Reboot
**Symptom**: Task shows "Ready" instead of "Running" in Task Scheduler

**Solution**:
1. Check Task Scheduler → Task History (enable if disabled)
2. Review error messages
3. Verify:
   - Python path is correct
   - "Start in" directory is correct (D:\crypto)
   - User has permissions to run task

### Issue: Incremental Mode Not Working
**Symptom**: Scheduler inserts 0 candles daily

**Solution**:
1. Verify last ingestion timestamp:
   ```sql
   SELECT symbol, MAX(timestamp) 
   FROM crypto.market_prices mp
   JOIN crypto.trading_pairs tp ON mp.trading_pair_id = tp.id
   GROUP BY symbol;
   ```
2. Check if timestamp is current (within last 24 hours)
3. If gap exists, scheduler will fill it automatically

---

## Maintenance

### Weekly Tasks
- [ ] Check logs for errors: `Select-String -Path D:\crypto\logs\*.log -Pattern "ERROR"`
- [ ] Verify data freshness (latest timestamp should be < 24 hours old)
- [ ] Check disk space: `Get-PSDrive D`

### Monthly Tasks
- [ ] Review candle count growth (should increase by ~2,880 per pair per month)
- [ ] Archive old logs (keep last 90 days)
- [ ] Backup database
- [ ] Check for Python/package updates: `pip list --outdated`

### Quarterly Tasks
- [ ] Review tracked pairs: Add/remove tickers as needed
- [ ] Update Windows and software
- [ ] Test disaster recovery (restore from backup)

---

## Rollback & Recovery

### If Historical Load Fails
1. Check last successful timestamp in logs
2. Re-run with remaining days
3. Duplicate handling ensures no double-counting

### If Database Corrupted
1. Stop scheduler: Right-click task → End
2. Restore from backup
3. Re-run historical load if needed

### If Scheduler Fails Repeatedly
1. Check logs: `D:\crypto\logs\scheduler_*.log`
2. Verify database connectivity
3. Check Coinbase API status: https://status.cloud.coinbase.com/
4. Review retry logic (3 attempts, 60s delay)
5. If persistent, disable scheduler and investigate

---

## Success Checklist

### After Installation
- [ ] Python 3.12+ installed and in PATH
- [ ] Git installed (if needed)
- [ ] ODBC Driver 18 installed
- [ ] Project cloned to D:\crypto
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] .env file configured
- [ ] Database connection tested

### After Historical Load
- [ ] All 4 tracked pairs have ~26,280 candles
- [ ] Date range covers ~3 years
- [ ] No errors in final ingestion summary
- [ ] SQL verification query shows correct data

### After Scheduler Setup
- [ ] jobs.yaml configured for production (enabled=true, run_on_startup=false)
- [ ] Windows Task Scheduler job created
- [ ] Task runs at system startup
- [ ] Logs show successful daily runs
- [ ] New candles inserted daily (4-96 per run)

### Production Ready
- [ ] Scheduler survives reboot
- [ ] Incremental mode working (fetches from last timestamp)
- [ ] Retry logic handling transient errors
- [ ] Logs being generated and monitored
- [ ] Data freshness verified daily

---

## Support & Resources

- **Project Documentation**: `D:\crypto\docs\`
- **Scheduler Guide**: `docs/development/SCHEDULER.md`
- **Database Guide**: `docs/database/DATABASE_SETUP_GUIDE.md`
- **Logs Location**: `D:\crypto\logs\`
- **Configuration**: `D:\crypto\config\jobs.yaml`

---

**Deployment Complete!** 🎉

Your Mini PC is now running automated cryptocurrency data collection with:
- ✅ 3 years of historical data loaded
- ✅ Daily incremental updates from last timestamp
- ✅ Automatic retry logic for transient failures
- ✅ Auto-start on system reboot
- ✅ Production-ready monitoring
