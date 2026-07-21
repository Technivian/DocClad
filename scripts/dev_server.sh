#!/usr/bin/env bash
# Run the Django dev server in the foreground *with autoreload*.
# For a durable background server, use scripts/dev_up.sh (supervised).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEV_PORT="${DEV_PORT:-8060}"
DEV_HOST="${DEV_HOST:-0.0.0.0}"

mkdir -p logs
echo "$$" > logs/devserver.pid
git -C "$ROOT_DIR" rev-parse HEAD > logs/devserver.boot_sha 2>/dev/null || echo "unknown" > logs/devserver.boot_sha

echo "Starting foreground runserver with autoreload on http://${DEV_HOST}:${DEV_PORT}/"
echo "Keep this terminal open. For background: bash scripts/dev_up.sh"

exec env DATABASE_URL= \
  DJANGO_SETTINGS_MODULE=config.settings_development \
  DJANGO_DEBUG=true \
  "$ROOT_DIR/.venv/bin/python" -u manage.py runserver "${DEV_HOST}:${DEV_PORT}"
