#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_PATH="${PYTHON_PATH:-${PROJECT_ROOT}/venv/bin/python}"
CRON_SCHEDULE="${CRON_SCHEDULE:-30 2 * * *}"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/daily_refresh.log"

if [[ ! -x "${PYTHON_PATH}" ]]; then
  echo "Python path not executable: ${PYTHON_PATH}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"

REFRESH_CMD="cd ${PROJECT_ROOT} && ${PYTHON_PATH} manage.py run_daily_refresh --sync-limit 500 --detail-limit 300 --enrich-missing-limit 800 --district-backfill-limit 1500 --with-backup --backup-compress --alert-on-failure >> ${LOG_FILE} 2>&1"
CRON_ENTRY="${CRON_SCHEDULE} ${REFRESH_CMD}"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
FILTERED_CRON="$(printf "%s\n" "${CURRENT_CRON}" | grep -Fv "manage.py run_daily_refresh" || true)"
NEW_CRON="$(printf "%s\n%s\n" "${FILTERED_CRON}" "${CRON_ENTRY}" | sed '/^[[:space:]]*$/d')"

printf "%s\n" "${NEW_CRON}" | crontab -

echo "Cron scheduler installed."
echo "Schedule: ${CRON_SCHEDULE}"
echo "Entry   : ${CRON_ENTRY}"
