<#
.SYNOPSIS
    Configures Dagu to run the CryptoQuant backfill DAG straight from this repository.

.DESCRIPTION
    - Derives the project root from this script's location (no hard-coded drive/path).
    - Writes %USERPROFILE%\.config\dagu\config.yaml from deploy\dagu\dagu_config.yaml plus
      paths.dags_dir pointing at deploy\dagu\dags, so `git pull` is the only deploy step.
    - Validates the DAG and confirms Dagu is reading the repo's DAG folder.

.PARAMETER RunNow
    Run the DAG once after validation (hits the live database).

.PARAMETER RegisterStartupTask
    Create/replace the "CryptoQuant Dagu" scheduled task (At startup). Requires an elevated shell.

.PARAMETER DisableOldScheduler
    Disable the legacy "CryptoQuant Data Scheduler" task. Only use once Dagu is verified.

.PARAMETER ReplaceDaguService
    Stop and disable the "Dagu" Windows service created by the Dagu installer. It runs `dagu start-all`
    as LocalSystem with DAGU_HOME=C:\ProgramData\Dagu (not this repo's config/DAGs) and holds ports
    8080/50055, so `dagu start-all` and the "CryptoQuant Dagu" task fail with "bind: Only one usage of
    each socket address". Requires an elevated shell.

.PARAMETER DaguHome
    Override the Dagu home (default: %USERPROFILE%\.config\dagu). Intended for testing.

.EXAMPLE
    .\deploy\ps\dagu-setup.ps1 -RunNow
#>
[CmdletBinding()]
param(
    [switch]$RunNow,
    [switch]$RegisterStartupTask,
    [switch]$DisableOldScheduler,
    [switch]$ReplaceDaguService,
    [string]$DaguHome = (Join-Path $env:USERPROFILE '.config\dagu')
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$DagsDir     = Join-Path $ProjectRoot 'deploy\dagu\dags'
$DagFile     = Join-Path $DagsDir 'crypto_backfill.yaml'
$Template    = Join-Path $ProjectRoot 'deploy\dagu\dagu_config.yaml'
$ConfigPath  = Join-Path $DaguHome 'config.yaml'
$VenvPython  = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$TaskName    = 'CryptoQuant Dagu'
$OldTaskName = 'CryptoQuant Data Scheduler'

if ($PSBoundParameters.ContainsKey('DaguHome')) { $env:DAGU_HOME = $DaguHome }

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { Write-Host "ERROR: $Message" -ForegroundColor Red; exit 1 }

# Dagu logs warnings to stderr, which would abort the script under $ErrorActionPreference = 'Stop'.
function Invoke-Dagu {
    param([Parameter(ValueFromRemainingArguments)][string[]]$DaguArgs)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & dagu @DaguArgs 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    [pscustomobject]@{ ExitCode = $code; Output = $output }
}

Write-Step "Checking prerequisites (project root: $ProjectRoot)"
if (-not (Get-Command dagu -ErrorAction SilentlyContinue)) {
    Fail 'dagu not found on PATH. Install it from https://docs.dagu.sh/getting-started/installation/ and open a new PowerShell window.'
}
if (-not (Test-Path $VenvPython)) { Fail "Virtual environment missing: $VenvPython (see docs/setup/VIRTUAL_ENVIRONMENT.md)" }
if (-not (Test-Path (Join-Path $ProjectRoot '.env'))) { Fail "Missing $ProjectRoot\.env (database and Coinbase settings)" }
if (-not (Test-Path $DagFile)) { Fail "DAG file missing: $DagFile (run git pull)" }
if (-not (Test-Path $Template)) { Fail "Config template missing: $Template (run git pull)" }
Write-Host "dagu $((Invoke-Dagu version).Output -join ' ')"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$daguService = Get-Service -Name 'Dagu' -ErrorAction SilentlyContinue
if ($ReplaceDaguService -and $daguService) {
    Write-Step "Stopping and disabling the 'Dagu' Windows service"
    if (-not $isAdmin) { Fail 'Replacing the Dagu service needs an elevated (Run as administrator) PowerShell.' }
    if ($daguService.Status -ne 'Stopped') { Stop-Service -Name 'Dagu' -Force }
    Set-Service -Name 'Dagu' -StartupType Disabled
    Write-Host "OK: service 'Dagu' stopped and disabled (re-enable with: Set-Service Dagu -StartupType Automatic; Start-Service Dagu)"
} elseif ($daguService -and $daguService.Status -eq 'Running') {
    Write-Host "WARNING: the 'Dagu' Windows service is running and holds ports 8080/50055 with its own config (C:\ProgramData\Dagu)." -ForegroundColor Yellow
    Write-Host "         'dagu start-all' will fail with 'bind: Only one usage of each socket address'. Re-run from an elevated shell with -ReplaceDaguService." -ForegroundColor Yellow
}

Write-Step "Writing $ConfigPath"
New-Item -ItemType Directory -Force $DaguHome | Out-Null
$yamlPath = $DagsDir.Replace("'", "''")
$config = (Get-Content $Template -Raw).TrimEnd() + "`r`n`r`npaths:`r`n  dags_dir: '$yamlPath'`r`n"
if ((Test-Path $ConfigPath) -and ((Get-Content $ConfigPath -Raw) -ne $config)) {
    $backup = "$ConfigPath.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
    Copy-Item $ConfigPath $backup
    Write-Host "Existing config backed up to $backup"
}
[System.IO.File]::WriteAllText($ConfigPath, $config, (New-Object System.Text.UTF8Encoding($false)))

# A copy in the old default DAG folder is what caused stale-DAG errors; Dagu no longer reads it.
$staleCopy = Join-Path $DaguHome 'dags\crypto_backfill.yaml'
if (Test-Path $staleCopy) {
    Remove-Item $staleCopy -Force
    Write-Host "Removed stale DAG copy: $staleCopy"
}

Write-Step 'Validating DAG'
$result = Invoke-Dagu validate $DagFile
$result.Output | ForEach-Object { Write-Host $_ }
if ($result.ExitCode -ne 0) { Fail 'DAG validation failed (details above).' }
Write-Host 'OK: DAG is valid'

Write-Step 'Confirming Dagu reads the repository DAG folder'
$paths = Invoke-Dagu config
$dagsLine = $paths.Output | Where-Object { $_ -match '^DAGs directory:\s*(.+)$' } | Select-Object -First 1
$actual = if ($dagsLine -match '^DAGs directory:\s*(.+)$') { $Matches[1].Trim() } else { '' }
if ($actual -ne $DagsDir) {
    Fail "Dagu is using '$actual' instead of '$DagsDir'. Check for a DAGU_HOME / DAGU_DAGS_DIR environment variable overriding $ConfigPath."
}
Write-Host "OK: $actual"

if ($RunNow) {
    Write-Step 'Running crypto_backfill once (live database)'
    $run = Invoke-Dagu start crypto_backfill
    $run.Output | ForEach-Object { Write-Host $_ }
    if ($run.ExitCode -ne 0) { Fail 'crypto_backfill run failed (details above).' }
}

if ($RegisterStartupTask) {
    Write-Step "Registering scheduled task '$TaskName'"
    if (-not $isAdmin) { Fail 'Registering the startup task needs an elevated (Run as administrator) PowerShell.' }
    $daguExe  = (Get-Command dagu).Source
    $action   = New-ScheduledTaskAction -Execute $daguExe -Argument 'start-all' -WorkingDirectory $ProjectRoot
    $trigger  = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Registered '$TaskName' (runs '$daguExe start-all' at startup as $env:USERNAME)."
}

if ($DisableOldScheduler) {
    Write-Step "Disabling legacy task '$OldTaskName'"
    if (Get-ScheduledTask -TaskName $OldTaskName -ErrorAction SilentlyContinue) {
        Disable-ScheduledTask -TaskName $OldTaskName | Out-Null
        Write-Host "Disabled '$OldTaskName'."
    } else {
        Write-Host "'$OldTaskName' not found; nothing to disable."
    }
}

Write-Step 'Done'
Write-Host "DAG:   $DagFile"
Write-Host "Next:  dagu start crypto_backfill   (manual run)"
Write-Host "       dagu start-all               (scheduler + UI at http://localhost:8080)"
