# Dagu Scheduler Reference

## CryptoQuant Backfill DAG

The production Dagu workflow is [crypto_backfill.yaml](../../deploy/dagu/crypto_backfill.yaml). It replaces the APScheduler process previously launched by `scripts/run_scheduler.py`.

| Setting | Value |
|---|---|
| DAG name | `crypto_backfill` |
| Schedule | Every 4 hours, at minute 0 (`0 */4 * * *`) |
| Catch-up window | 3 days (`3d`); requires `queues.enabled: true` in Dagu's global config |
| Working directory | `D:\crypto` |
| Overlap policy | `skip`; an already-running execution is not overlapped |
| Timeout | 2 hours |
| Retries | Up to 2 retries per step, 60 seconds apart |

### Steps and dependency

1. `backfill_candles` runs `scripts/run_backfill.py --type candles`.
2. `backfill_analysis` runs `scripts/run_backfill.py --type analysis` after the candle step succeeds.

The step dependency prevents analysis from running on an unsuccessful candle step. Both commands return a non-zero exit code on failure, allowing Dagu to record failures and apply its retry policy.

### Recovery after downtime

Dagu's `catchup_window: "3d"` replays missed schedule times from the last three days after the scheduler comes back online. Catch-up requires `queues.enabled: true` in `%USERPROFILE%\.config\dagu\config.yaml`; the repo sample is [dagu_config.yaml](../../deploy/dagu/dagu_config.yaml).

Dagu catch-up is not the only recovery mechanism. Each DAG cycle first runs the candle step, which checks the database for missing candle data and performs incremental catch-up to the present; the dependent analysis step then recalculates analysis. Therefore, if the PC was down longer than three days, a later successful cycle can still fill the database gap even though Dagu does not replay every old schedule tick.

### Common commands (PowerShell)

Run from the project directory:

```powershell
cd D:\crypto

# Validate structure and step dependencies
dagu validate deploy\dagu\crypto_backfill.yaml

# Run both steps immediately
dagu start deploy\dagu\crypto_backfill.yaml

# Inspect current/latest run
dagu status crypto_backfill

# Show recent runs
dagu history crypto_backfill

# Start the Dagu UI and scheduler using this repository's DAG directory
dagu start-all --dags D:\crypto\deploy\dagu
```

The UI is available at `http://localhost:8080` by default. Use `dagu ls -n -l` to see scheduled DAGs and their projected next run.

### Troubleshooting checklist

- **DAG does not appear in Dagu:** confirm its YAML is in the directory passed to `--dags` (or Dagu's configured DAG directory), then run `dagu ls`.
- **Catch-up does not happen:** verify `%USERPROFILE%\.config\dagu\config.yaml` contains `queues.enabled: true`, and check Dagu logs for configuration warnings.
- **Python or `.env` errors:** confirm `working_dir` points to the project root, `.venv\Scripts\python.exe` exists, and `.env` is present there.
- **Step failed:** inspect Dagu's run details and `D:\crypto\logs\backfill_*.log`; fix the underlying issue before retrying.
- **Runs overlap or duplicate:** verify the old `CryptoQuant Data Scheduler` task is disabled after cutover and the DAG retains `overlap_policy: skip`.

For installation, Windows startup configuration, and initial cutover steps, see [Dagu Setup](../setup/DAGU_SETUP.md).
