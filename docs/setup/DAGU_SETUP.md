# Dagu Setup (Windows Mini PC)

This guide installs and starts Dagu for the CryptoQuant candle and technical-analysis backfill workflow. The DAG is [crypto_backfill.yaml](../../deploy/dagu/dags/crypto_backfill.yaml); Dagu reads it directly from the repository, so there is no copy step and `git pull` is the only deploy action. The DAG contains no drive letters: its `working_dir` is relative to the DAG file, so it works wherever the repo is cloned (the mini PC uses `C:\data\code\git\CryptoQuant`).

## Prerequisites

- The repository is cloned on the mini PC and up to date (`git pull origin dev`).
- `.venv` exists in the repo root with dependencies installed ([virtual environment guide](VIRTUAL_ENVIRONMENT.md)).
- `.env` in the repo root contains the database and Coinbase settings.
- Dagu is installed (next section).
- The old `CryptoQuant Data Scheduler` task stays enabled until Dagu is verified.

## Install Dagu

Install the Windows binary using the current instructions at [Dagu Installation](https://docs.dagu.sh/getting-started/installation/), then open a new PowerShell window and verify:

```powershell
dagu version
```

## Configure and verify with the setup script

From the repository root in PowerShell:

```powershell
cd C:\data\code\git\CryptoQuant
git pull origin dev
.\deploy\ps\dagu-setup.ps1 -RunNow
```

If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope Process RemoteSigned` first.

The script is safe to re-run. It:

1. Checks that `dagu`, `.venv`, `.env`, and the DAG file exist.
2. Writes `%USERPROFILE%\.config\dagu\config.yaml` from [dagu_config.yaml](../../deploy/dagu/dagu_config.yaml) (enables `queues` for missed-run catch-up, disables the login prompt) and sets `paths.dags_dir` to the repo's `deploy\dagu\dags` folder. An existing different config is backed up first.
3. Deletes any old copy at `%USERPROFILE%\.config\dagu\dags\crypto_backfill.yaml` (a stale copy is what produced the `entrypoint document must not define name` and `D:\crypto` errors).
4. Runs `dagu validate` and confirms Dagu is reading the repo's DAG folder.
5. With `-RunNow`, runs the DAG once against the live database (both steps should report `succeeded`; a step may retry once on a transient Azure SQL timeout).

Logs for each run are in `logs\backfill_*.log`, and `dagu status crypto_backfill` shows the last run.

## Keep Dagu running after reboot

The scheduler must be running for scheduled jobs to fire. From an **elevated** PowerShell (Run as administrator):

```powershell
cd C:\data\code\git\CryptoQuant
.\deploy\ps\dagu-setup.ps1 -RegisterStartupTask
```

This creates the `CryptoQuant Dagu` scheduled task: it runs `dagu start-all` at startup as the current user, restarts on failure, ignores a second instance, has no run-time limit, and is not stopped on battery. Start it (`Start-ScheduledTask 'CryptoQuant Dagu'`) or reboot, then open `http://localhost:8080` to see the DAG and its next run.

The task runs without a stored password, so it has no network-share credentials; internet access (Azure SQL, Coinbase) is unaffected.

## Cut over from the old scheduler

After Dagu has completed a successful run and the startup task works:

```powershell
.\deploy\ps\dagu-setup.ps1 -DisableOldScheduler
```

Do not run both schedulers in steady state; they would run overlapping ingestion and analysis.

## Updating later

```powershell
cd C:\data\code\git\CryptoQuant
git pull origin dev
```

No other step is needed for DAG changes. Dagu reads the repo's DAG folder directly. Re-run `dagu-setup.ps1` only if `deploy\dagu\dagu_config.yaml` changes.

## Power-cut recovery

After the mini PC restarts, the startup task starts Dagu and `catchup_window: "72h"` replays scheduled runs missed in the last three days. For longer outages, the next run of `run_backfill.py` still catches up from the latest timestamp stored in the database, so candles and analysis are not limited to that replay window.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `entrypoint document must not define name` | Dagu is reading an old copy of the DAG. Re-run `dagu-setup.ps1`, which removes the stale copy and points Dagu at the repo. |
| `mkdir D:\crypto ... cannot find the path` | Same stale copy (older DAG had a hard-coded path). Re-run `dagu-setup.ps1`. |
| `Dagu is using '...' instead of ...` (from the script) | A `DAGU_HOME` or `DAGU_DAGS_DIR` environment variable overrides the config. Remove it (`[Environment]::SetEnvironmentVariable('DAGU_HOME', $null, 'User')`) and open a new PowerShell. |
| `No auth.mode configured` warning | Config not applied yet. Run `dagu-setup.ps1`. |

See [Dagu Scheduler Reference](../scheduler/DAGU_SCHEDULER.md) for job behavior and operational commands.
