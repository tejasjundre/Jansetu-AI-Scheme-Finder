#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

./venv/bin/python manage.py run_daily_refresh \
  --sync-limit 500 \
  --detail-limit 300 \
  --enrich-missing-limit 800 \
  --district-backfill-limit 1500 \
  --with-backup \
  --backup-compress \
  --alert-on-failure
