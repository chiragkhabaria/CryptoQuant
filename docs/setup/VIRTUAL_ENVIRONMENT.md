# Virtual Environment Setup

This project uses a local Python virtual environment at `.venv/`.

## Create the Virtual Environment

From the project root:

```powershell
cd D:\data\development\crypto

# Use an installed Python, or the bundled Codex Python if needed.
python -m venv .venv
```

If `python` opens the Microsoft Store or cannot be found, use the full Python path that created the current environment:

```powershell
& "C:\Users\chira\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
```

## Activate the Virtual Environment

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
.\.venv\Scripts\activate.bat
```

Git Bash:

```bash
source .venv/Scripts/activate
```

When activation works, your prompt should start with `(.venv)`.

## Install Dependencies

After activation:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m pip install pytest pytest-cov pytest-asyncio black ruff mypy pre-commit ipython jupyter types-requests
```

## Run Project Commands

Use the activated environment:

```powershell
python scripts\collect_historic_data.py --help
python scripts\collect_historic_data.py --granularity daily --days 7 --product-id BTC-USD
```

Or call the venv Python directly without activation:

```powershell
.\.venv\Scripts\python.exe scripts\collect_historic_data.py --help
```

## Deactivate the Virtual Environment

From any shell where the venv is active:

```powershell
deactivate
```

## Troubleshooting

If you see an error like:

```text
ModuleNotFoundError: No module named 'click'
```

you are probably running the script outside the virtual environment, or dependencies were not installed. Activate `.venv` and rerun:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python scripts\collect_historic_data.py --help
```

If PowerShell blocks activation scripts, run this once for the current terminal:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```
