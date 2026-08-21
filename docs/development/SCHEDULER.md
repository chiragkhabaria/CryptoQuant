# Scheduler

CryptoQuant includes a lightweight, Python-based scheduling layer built on
[APScheduler 3.x](https://apscheduler.readthedocs.io/en/3.x/).  Jobs are
defined in a **YAML configuration file** (`config/jobs.yaml`) and loaded
dynamically at startup — no code changes needed to add or modify schedules.

---

## Quick Start

### 1. Configure Jobs

Edit `config/jobs.yaml` to define when jobs should run:

```yaml
jobs:
  - id: historic_ingestion
    name: "Historic OHLCV Data Ingestion"
    enabled: true
    run_on_startup: false  # true = run immediately when scheduler starts
    type: cron             # 'cron' or 'interval'
    cron: "0 2 * * *"      # Daily at 2:00 AM UTC
    function: historic_ingestion_job
```

### 2. Start the Scheduler

```bash
# Activate virtual environment first
.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate      # Linux / macOS

python scripts/run_scheduler.py
```

The process blocks until `Ctrl+C` or `SIGTERM`.  
Logs: `logs/scheduler_YYYYMMDD.log` + stdout.

---

## Job Configuration (jobs.yaml)

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique job identifier | `historic_ingestion` |
| `name` | Human-readable name | `"Historic OHLCV Data Ingestion"` |
| `enabled` | Enable/disable without deleting | `true` / `false` |
| `type` | Schedule type | `cron` or `interval` |
| `function` | Python function name in `cryptoquant.scheduling.jobs` | `historic_ingestion_job` |

### Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `run_on_startup` | Run immediately when scheduler starts | `false` |
| `cron` | Cron expression (required if `type: cron`) | — |
| `interval_minutes` | Interval in minutes (required if `type: interval`) | — |

### Schedule Types

#### Cron (specific times)

Run at specific times of day/week/month using standard cron syntax:

```yaml
type: cron
cron: "minute hour day month day_of_week"
```

**Common examples:**

| Schedule | Cron Expression |
|----------|----------------|
| Daily at 2:00 AM UTC | `"0 2 * * *"` |
| Every 4 hours | `"0 */4 * * *"` |
| Weekdays at 1:30 AM | `"30 1 * * 1-5"` |
| Every Sunday at midnight | `"0 0 * * 0"` |
| Twice daily (6 AM & 6 PM) | `"0 6,18 * * *"` |

#### Interval (fixed period)

Run every N minutes:

```yaml
type: interval
interval_minutes: 60
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_ENABLED` | `true` | Master on/off switch |
| `SCHEDULER_JOBS_CONFIG` | `config/jobs.yaml` | Path to jobs config file |
| `INGESTION_GRANULARITY` | `hourly` | Candle granularity for ingestion job |
| `INGESTION_LOOKBACK_DAYS` | `1` | How many days back to fetch |

---

## Example Configurations

### Development (Test Every 5 Minutes)

```yaml
jobs:
  - id: historic_ingestion
    enabled: true
    run_on_startup: true   # Run immediately for testing
    type: interval
    interval_minutes: 5
    function: historic_ingestion_job
```

### Production (Daily at 2 AM)

```yaml
jobs:
  - id: historic_ingestion
    enabled: true
    run_on_startup: false
    type: cron
    cron: "0 2 * * *"      # 2:00 AM UTC daily
    function: historic_ingestion_job
```

### Production (Every 4 Hours)

```yaml
jobs:
  - id: historic_ingestion
    enabled: true
    run_on_startup: false
    type: cron
    cron: "0 */4 * * *"    # Every 4 hours
    function: historic_ingestion_job
```

---

## Testing Locally

### Quick Test Workflow

Follow these steps to test the scheduler locally before deploying to Mini PC:

#### Step 1: Enable Immediate Execution

Edit [config/jobs.yaml](../../config/jobs.yaml):

```yaml
jobs:
  - id: historic_ingestion
    enabled: true
    run_on_startup: true  # ← Change to true for testing
    type: cron
    cron: "0 2 * * *"
    function: historic_ingestion_job
```

#### Step 2: Activate Virtual Environment

```powershell
# Windows
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate
```

#### Step 3: Start the Scheduler

```powershell
python scripts/run_scheduler.py
```

**What to expect:**
- Job runs immediately (because `run_on_startup: true`)
- Logs appear in console and `logs/scheduler_YYYYMMDD.log`
- After completion, scheduler waits for next scheduled time (2 AM UTC)

#### Step 4: Monitor the Logs

Watch for these log messages:

```
✓ Success:
  "historic_ingestion_job: completed — inserted=X, skipped=Y, errors=0"

⚠ Retry (expected with Azure SQL serverless):
  "historic_ingestion_job: attempt 1/3 failed — ... — retrying in 60 seconds..."

✗ Failure after 3 attempts:
  "historic_ingestion_job: all 3 attempts failed — giving up until next scheduled run"
```

#### Step 5: Kill the Scheduler

Press `Ctrl+C` in the terminal running the scheduler.

**Expected output:**
```
Received signal 2 — shutting down scheduler gracefully...
Scheduler stopped.
```

The scheduler shuts down cleanly without data loss.

#### Step 6: Restore Production Config

Edit [config/jobs.yaml](../../config/jobs.yaml):

```yaml
run_on_startup: false  # ← Change back to false
```

---

### Test Scenarios

#### Test 1: Run Immediately on Startup

```yaml
run_on_startup: true
```

Start the scheduler — the job runs instantly, then waits for the next scheduled time.

**Use case:** Verify job executes correctly without waiting for cron schedule.

#### Test 2: Short Interval for Repeated Testing

```yaml
type: interval
interval_minutes: 2
run_on_startup: true
```

Runs immediately, then every 2 minutes. Watch the logs to verify correct behavior.

**Use case:** Test retry logic, error handling, or repeated execution patterns.

#### Test 3: Dry Run (Check Schedule Without Running)

Temporarily disable jobs:

```yaml
enabled: false
```

Start the scheduler. It loads the config but doesn't execute the job.

**Use case:** Verify YAML config parses correctly without triggering actual job execution.

---

## Retry Logic

Jobs implement automatic retry logic to handle transient failures (e.g., Azure SQL serverless connection timeouts):

- **Max Retries:** 3 attempts
- **Retry Delay:** 60 seconds between attempts
- **Behavior:**
  - Attempt 1 fails → wait 60s → Attempt 2
  - Attempt 2 fails → wait 60s → Attempt 3
  - Attempt 3 fails → log error, wait for next scheduled run

**Logged as:**
```
[WARNING] historic_ingestion_job: attempt 1/3 failed — (pyodbc.OperationalError) ... — retrying in 60 seconds...
[ERROR] historic_ingestion_job: all 3 attempts failed — giving up until next scheduled run
```

---

## Adding a New Job

### Step 1: Create the Job Function

Add to `src/cryptoquant/scheduling/jobs.py`:

```python
def my_new_job() -> None:
    """Job description."""
    logger.info("my_new_job: started")
    try:
        # Call your existing application logic here
        from cryptoquant.mymodule import do_something
        do_something()
        logger.info("my_new_job: completed successfully")
    except Exception:
        logger.exception("my_new_job: failed")
```

**Rules:**
- Must be a zero-argument function
- Must catch and log all exceptions (don't let them propagate)
- Should log start/completion/failure

### Step 2: Add to jobs.yaml

```yaml
jobs:
  - id: my_new_job
    name: "My New Scheduled Task"
    enabled: true
    run_on_startup: false
    type: cron
    cron: "0 3 * * *"
    function: my_new_job
```

### Step 3: Restart the Scheduler

```bash
# Stop (Ctrl+C), then restart
python scripts/run_scheduler.py
```

The new job is loaded automatically — no code deployment needed.

---

## Project Structure

```
config/
└── jobs.yaml              ← Job definitions (edit this to change schedules)

src/cryptoquant/
├── ingestion/
│   └── historic.py        ← run_ingestion() entry point
└── scheduling/
    ├── jobs.py            ← Job wrapper functions (add new jobs here)
    └── scheduler.py      ← YAML loader + APScheduler setup

scripts/
└── run_scheduler.py      ← Launcher (run this to start the process)
```

---

## Error Handling

- **Job exception** → logged, scheduler continues running
- **Missed firing** (process was down) → coalesced into single catch-up run
- **Overlapping runs** → blocked (`max_instances=1`)
- **Invalid YAML** → scheduler fails to start (fix the YAML and restart)
- **Missing job function** → that job is skipped, other jobs continue

---

## Deployment to Mini PC

### Recommended Setup

1. **Use cron schedule** (not interval) for predictable timing:
   ```yaml
   type: cron
   cron: "0 2 * * *"  # 2 AM daily
   ```

2. **Disable `run_on_startup`** in production:
   ```yaml
   run_on_startup: false
   ```

3. **Run as a service** (Windows Task Scheduler / systemd):
   - Configure to auto-start on boot
   - Restart on failure
   - Log rotation

### Windows Task Scheduler Example

1. **Task Trigger:** At system startup
2. **Action:** Start a program
   - Program: `D:\crypto\.venv\Scripts\python.exe`
   - Arguments: `scripts\run_scheduler.py`
   - Start in: `D:\crypto\`
3. **Conditions:** Uncheck "Start only if on AC power"
4. **Settings:** Check "Restart on failure"

---

## Troubleshooting

### Job doesn't run immediately

✅ **Solution:** Set `run_on_startup: true` in jobs.yaml  
OR use a short test interval: `interval_minutes: 1`

### "Job function 'xyz' not found"

✅ Ensure the function exists in `src/cryptoquant/scheduling/jobs.py`  
✅ Check spelling in `function:` field (case-sensitive)

### "Invalid cron expression"

✅ Use 5 fields: `"minute hour day month day_of_week"`  
✅ Example: `"0 2 * * *"` (daily at 2 AM)

### Job runs but nothing happens

✅ Check `logs/scheduler_YYYYMMDD.log` for job-level errors  
✅ Verify environment variables (`INGESTION_GRANULARITY`, etc.)  
✅ Ensure tracked pairs exist in database

---

## Configuration Summary

| Use Case | `type` | `cron` / `interval_minutes` | `run_on_startup` |
|----------|--------|----------------------------|------------------|
| **Production: Daily at 2 AM** | `cron` | `"0 2 * * *"` | `false` |
| **Production: Every 4 hours** | `cron` | `"0 */4 * * *"` | `false` |
| **Development: Every 10 min** | `interval` | `10` | `true` |
| **Testing: Run once immediately** | Any | Any | `true` (then stop scheduler) |
