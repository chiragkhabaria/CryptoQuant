# Dagu Setup (Windows Mini PC)

This guide installs and starts Dagu for the CryptoQuant candle and technical-analysis backfill workflow. The checked-in DAG is [crypto_backfill.yaml](../../deploy/dagu/crypto_backfill.yaml); its commands assume the project lives at `D:\crypto`.

## Prerequisites

- The CryptoQuant repository is deployed at `D:\crypto`.
- Project dependencies are installed in `D:\crypto\.venv` and `D:\crypto\.env` contains the required database and Coinbase settings.
- The old `CryptoQuant Data Scheduler` task is left enabled until Dagu has passed the verification below.

If the project directory is different, update `working_dir` in the DAG and verify the Python executable path before proceeding.

## Install Dagu

Install the Windows binary using the current instructions at [Dagu Installation](https://docs.dagu.sh/getting-started/installation/), then open a new PowerShell window and verify:

```powershell
dagu version
```

## Enable missed-run catch-up

Dagu reads its user config from `%USERPROFILE%\.config\dagu\config.yaml` by default. Install the repository's sample config:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\dagu" | Out-Null
Copy-Item D:\crypto\deploy\dagu\dagu_config.yaml `
  "$env:USERPROFILE\.config\dagu\config.yaml" -Force
```

The `queues.enabled: true` setting is required for this DAG's `catchup_window` to replay missed scheduled runs.

## Install and validate the CryptoQuant DAG

Place the DAG in Dagu's configured DAGs directory. The default installation uses `%USERPROFILE%\.config\dagu\dags`; create it and copy the file:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\dagu\dags" | Out-Null
Copy-Item D:\crypto\deploy\dagu\crypto_backfill.yaml `
  "$env:USERPROFILE\.config\dagu\dags\crypto_backfill.yaml" -Force

dagu validate "$env:USERPROFILE\.config\dagu\dags\crypto_backfill.yaml"
```

A successful validation reports that the DAG specification is valid. Then run it once manually:

```powershell
dagu start crypto_backfill
dagu status crypto_backfill
```

Confirm both the `backfill_candles` and `backfill_analysis` steps succeeded. Check the application logs under `D:\crypto\logs\backfill_*.log` as well.

## Keep Dagu running after reboot

Dagu's scheduler must remain running for scheduled jobs to fire. For this single-PC deployment, configure Windows Task Scheduler to launch Dagu at startup:

1. Open Task Scheduler and create a task named `CryptoQuant Dagu`.
2. Set the trigger to **At startup**. Enable **Run whether user is logged on or not** and use the Windows account that can access the project and `.env` file.
3. Set the action to **Start a program**:
   - Program: the full path to `dagu.exe` (find it with `Get-Command dagu`).
   - Arguments: `start-all --dags D:\crypto\deploy\dagu`.
   - Start in: `D:\crypto`.
4. In **Conditions**, disable power-only restrictions. In **Settings**, enable restart on failure, prevent starting a second instance, and disable any maximum run-time limit so the scheduler is not stopped while waiting for future runs.
5. Run the task once, then verify the Dagu server is available at `http://localhost:8080` and the scheduled DAG is listed.

The Dagu process should stay running; do not configure the task to stop it when the user logs off. If the DAG is copied to the default Dagu DAGs directory above, use that directory as the `--dags` value instead.

## Cut over from the old scheduler

After Dagu has completed a successful full run and you have confirmed its startup task works:

```powershell
Disable-ScheduledTask -TaskName "CryptoQuant Data Scheduler"
```

Do not run both schedulers in steady state. Both would invoke overlapping ingestion and analysis work.

## Power-cut recovery

The DAG replays missed scheduled runs from the last three days after Dagu restarts. For downtime longer than three days, the next successful `run_backfill.py` execution still catches up from the latest timestamp stored in the database, so candles and analysis are not limited to that three-day replay window.

See [Dagu Scheduler Reference](../scheduler/DAGU_SCHEDULER.md) for job behavior and operational commands.
