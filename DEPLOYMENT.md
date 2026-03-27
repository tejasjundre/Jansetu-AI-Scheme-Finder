# AI Sakhi Deployment Guide

## 1. Recommended production stack

- Web app: Django behind `gunicorn`
- Database: PostgreSQL
- Cache / rate limiting: Redis
- Static files: WhiteNoise for simple hosting, or object storage/CDN later
- Reverse proxy / TLS: Nginx, Caddy, Render, Railway, Fly.io, or a similar managed platform

## 2. Environment variables

Use the values in `.env.example` as the baseline.

Important variables:

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `RATE_LIMIT_ENABLED=True`
- `ALERT_WEBHOOK_URL` (optional, for failure/success alerts)

If your hosting provider gives separate DB values instead of a single URL, you can use:

- `DB_ENGINE`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `DB_CONN_MAX_AGE`

## 3. First deploy steps

Install dependencies:

```bash
pip install -r requirements.txt
```

Run database setup:

```bash
python manage.py migrate
python manage.py seed_schemes
python manage.py sync_myscheme --limit 200
```

Create an admin:

```bash
python manage.py createsuperuser
```

Collect static files:

```bash
python manage.py collectstatic --noinput
```

Warm the launch-news cache:

```bash
python manage.py refresh_launch_news --limit 7
```

Optional detail enrichment pass (recommended in batches):

```bash
python manage.py sync_state_portals
python manage.py sync_state_verified_sources
python manage.py crawl_state_verified_sources --limit-sources 12 --max-pages 8 --max-links-per-source 40
python manage.py sync_myscheme --enrich-details --detail-limit 100
python manage.py enrich_myscheme_details --only-missing --limit 300
python manage.py backfill_district_coverage --only-empty --limit 1000
```

Single command for a full refresh cycle:

```bash
python manage.py run_daily_refresh
```

Add backup and alerts in the same run:

```bash
python manage.py run_daily_refresh --with-backup --backup-compress --alert-on-failure
```

Standalone backup command:

```bash
python manage.py backup_database --compress --keep-days 14
```

## 4. Automatic daily updates

The app supports automatic refresh by scheduling `run_daily_refresh`.

Quickstart by platform is available in:

```text
HOSTING_QUICKSTART.md
```

Linux cron example (daily at 02:30):

```bash
30 2 * * * cd /path/to/ai_sakhi && /path/to/venv/bin/python manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --crawl-state-sources --crawl-limit-sources 20 --crawl-max-pages 8 --crawl-max-links-per-source 40 --with-backup --backup-compress --alert-on-failure
```

Windows Task Scheduler action:

```text
Program/script: C:\path\to\venv\Scripts\python.exe
Arguments: manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --with-backup --backup-compress --alert-on-failure
Start in: C:\path\to\ai_sakhi
```

To include deeper state-source crawling in scheduler runs, append:

```text
--crawl-state-sources --crawl-limit-sources 20 --crawl-max-pages 8 --crawl-max-links-per-source 40
```

Prebuilt scheduler scripts:

- Windows PowerShell: `scripts/daily_refresh.ps1`
- Linux shell: `scripts/daily_refresh.sh`
- Windows installer: `scripts/install_windows_scheduler.ps1`
- Linux cron installer: `scripts/install_linux_cron.sh`

## 5. Start command

Example `gunicorn` command for Linux hosting:

```bash
gunicorn ai_sakhi.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
```

For platforms that use a Procfile, this repo includes one.

## 6. Health and operations

Health endpoint:

```text
/healthz/
```

What it checks:

- database connectivity
- cache read/write

Operations dashboard:

```text
/ops/
```

Use it after launch to review:

- unanswered requests needing human follow-up
- pending escalations
- stale scheme records
- broken-link alerts
- most requested schemes

## 7. Platform notes

### Render / Railway / Fly.io

- Set `DATABASE_URL` from the managed Postgres add-on
- Set `REDIS_URL` if Redis is available
- Use the `gunicorn` start command
- Add a health check pointed to `/healthz/`

### VPS with Nginx or Caddy

- run `gunicorn` on an internal port
- terminate TLS at the proxy
- forward `X-Forwarded-Proto` so Django sees HTTPS correctly

## 8. Security checklist

- keep `DEBUG=False`
- use a strong `SECRET_KEY`
- restrict `ALLOWED_HOSTS`
- configure `CSRF_TRUSTED_ORIGINS` with your exact HTTPS domain
- keep admin access limited to trusted staff
- review audit logs and unresolved escalations regularly

## 9. Important note

The bundled scheme dataset is still a product seed, not a final government-verified master dataset. Before public launch, continue syncing official scheme sources, verifying links, and reviewing expiry / freshness status in ops.
