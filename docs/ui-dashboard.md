# UI Dashboard (Phase 5)

Streamlit + Plotly app in `src/cryptoquantui/`. Pages: **Coins** (BTC default), **Data quality**, **Backtests & score**.

## Run locally / on the mini PC

```powershell
pip install streamlit          # or: poetry install --extras ui
alembic upgrade head           # creates crypto.job_runs (migration 008)
$env:PYTHONPATH="src"
streamlit run src/cryptoquantui/app.py --server.address 0.0.0.0 --server.port 8501
```

Needs the same `.env` as the scheduler (`DATABASE_URL`, Coinbase keys).
Open `http://<mini-pc-ip>:8501` on the home network. No password (home network only).

### Phone access from anywhere
Install [Tailscale](https://tailscale.com) on the mini PC and phone, then browse to `http://<tailscale-name>:8501`.
Do not port-forward the dashboard to the public internet.

### Start on boot (Windows)
Create a Task Scheduler task (trigger: at startup) running the `streamlit run ...` command above with the repo as working directory.

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
