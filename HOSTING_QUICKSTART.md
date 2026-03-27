# JanSetu Hosting Quickstart

This guide gives copy-paste setup for automatic daily refresh on common hosting targets.

## Common app command

Use this command for scheduled refresh jobs:

```bash
python manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --crawl-state-sources --crawl-limit-sources 20 --crawl-max-pages 8 --crawl-max-links-per-source 40 --with-backup --backup-compress --alert-on-failure
```

This pipeline now includes:
- official state portal sync (`sync_state_portals`)
- curated verified state source sync (`sync_state_verified_sources`)
- optional state source crawling (`crawl_state_verified_sources`)
- myScheme catalog sync
- detail enrichment
- district backfill
- launch-news warmup
- optional backup + alerts

Also set:

- `DEBUG=False`
- `DATABASE_URL`
- `ALERT_WEBHOOK_URL` (optional, for success/failure notifications)

## Render

1. Create a Web Service for the app (start command from `Procfile`).
2. Add a Cron Job with this command:

```bash
python manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --with-backup --backup-compress --alert-on-failure
```

3. Set cron schedule to daily (for example, `30 2 * * *`).
4. Point health check to `/healthz/`.

## Railway

1. Deploy the app service.
2. Add a scheduled task/job with the same refresh command.
3. Configure daily interval (for example 24h).
4. Keep `DATABASE_URL` and optional `ALERT_WEBHOOK_URL` in project variables.

## Linux VPS (Ubuntu/CentOS)

Use one command installer:

```bash
chmod +x scripts/install_linux_cron.sh
./scripts/install_linux_cron.sh
```

Optional custom schedule:

```bash
CRON_SCHEDULE="0 3 * * *" ./scripts/install_linux_cron.sh
```

Log file:

```text
logs/daily_refresh.log
```

## Windows Server / Windows host

Run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_scheduler.ps1
```

Custom run time:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_scheduler.ps1 -RunTime "03:00"
```

This registers a Task Scheduler job named `JanSetu Daily Refresh`.

## Verify after scheduler setup

1. Trigger one manual run from host command shell:

```bash
python manage.py run_daily_refresh --sync-limit 10 --detail-limit 5 --enrich-missing-limit 20 --district-backfill-limit 50 --with-backup --backup-compress
```

2. Confirm:
- backup file appears in `backups/`
- ops dashboard opens at `/ops/`
- health endpoint returns `ok` at `/healthz/`
