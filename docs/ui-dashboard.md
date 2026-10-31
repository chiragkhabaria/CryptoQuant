# UI Dashboard (Phase 5)

Streamlit + Plotly app in `src/cryptoquantui/`. Pages: **Coins** (BTC default), **Data quality**, **Backtests & score**.
Every table has a 📋 button per row (and **Copy all as JSON**) for pasting into an LLM.

## Quick start (Windows, from the repo root)

One-time setup:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e . streamlit pyodbc      # or: poetry install --extras ui
Copy-Item .env.example .env                            # then fill in DATABASE_URL and the Coinbase keys
$env:PYTHONPATH = "src"
.\.venv\Scripts\alembic upgrade head                   # creates crypto.job_runs (migration 008)
```

Azure SQL may be paused; if the migration times out with a login error, simply re-run it.
Needs the *ODBC Driver 18 for SQL Server* installed.

Start the dashboard:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\streamlit run src\cryptoquantui\app.py --server.address 0.0.0.0 --server.port 8501
```

| Where | URL |
|---|---|
| Same machine | http://localhost:8501 |
| Phone / laptop on the home Wi-Fi | `http://<mini-pc-ip>:8501` (find it with `ipconfig`) |
| Anywhere | `http://<tailscale-name>:8501` (see below) |

The first page load can take 10-20 seconds while the database wakes up and queries run; results are then cached for 60 seconds.
Stop the server with `Ctrl+C`. After editing code under `src/cryptoquantui/components/`, restart the server
(Streamlit only auto-reloads the page scripts reliably).

Windows Firewall may prompt on first start: allow private networks so phones can connect.
No password is used (home network only).

### Phone access from anywhere
Install [Tailscale](https://tailscale.com) on the mini PC and phone, then browse to `http://<tailscale-name>:8501`.
Do not port-forward the dashboard to the public internet.

### Start on boot (Windows)
Create a Task Scheduler task (trigger: at startup, run whether user is logged on or not) that runs
`.\.venv\Scripts\streamlit.exe run src\cryptoquantui\app.py --server.address 0.0.0.0 --server.port 8501`
with the repo as the working directory and `PYTHONPATH=src` set.

## Actions and the job log
Buttons insert `queued` rows in `crypto.job_runs`; a worker runs them one at a time (one active job per type).
Scheduler jobs also write to the same table, so the history shows both. Set `JOB_LOG_ENABLED=0` to disable logging.

- In-process worker (default): a daemon thread inside the Streamlit process.
- Separate worker: set `UI_EMBEDDED_WORKER=0` on the web process and run `python -m cryptoquantui.worker`.

## Azure App Service
Container-ready via the root `Dockerfile` (port 8000, ODBC 18 driver included).
1. Push the image to ACR and create a Linux container Web App; set `WEBSITES_PORT=8000` and enable **Web sockets**.
2. Configure `DATABASE_URL` and the Coinbase keys as app settings.
3. Run the worker as a second container/WebJob (`python -m cryptoquantui.worker`) with `UI_EMBEDDED_WORKER=0` on the web app.
4. The app has no built-in auth: enable App Service Authentication (Entra ID) before exposing it.
