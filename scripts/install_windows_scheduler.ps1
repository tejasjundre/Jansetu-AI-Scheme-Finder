param(
  [string]$TaskName = "JanSetu Daily Refresh",
  [string]$RunTime = "02:30",
  [string]$ProjectRoot = "",
  [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not $PythonPath) {
  $PythonPath = (Resolve-Path (Join-Path $ProjectRoot "venv\\Scripts\\python.exe")).Path
}

if (-not (Test-Path $PythonPath)) {
  throw "Python path not found: $PythonPath"
}

$refreshArguments = "manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --with-backup --backup-compress --alert-on-failure"
$taskCommand = "cmd /c cd /d `"$ProjectRoot`" && `"$PythonPath`" $refreshArguments"

schtasks /Create /TN "$TaskName" /TR "$taskCommand" /SC DAILY /ST "$RunTime" /F | Out-Null

Write-Host "Scheduled task created successfully."
Write-Host "Task Name : $TaskName"
Write-Host "Run Time  : $RunTime"
Write-Host "Command   : $taskCommand"
