$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

& ".\venv\Scripts\python.exe" manage.py run_daily_refresh `
  --sync-limit 500 `
  --detail-limit 300 `
  --enrich-missing-limit 800 `
  --district-backfill-limit 1500 `
  --with-backup `
  --backup-compress `
  --alert-on-failure
