#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INTERVAL_MINUTES="${1:-60}"

# Durable local default is HTTP runserver under nohup with DATABASE_URL cleared.
# HTTPS (uvicorn) is available via scripts/dev_https.sh when explicitly needed.
# Prefer HTTP because the app is opened as http://127.0.0.1:8060/ and because
# --noreload freezes URLconf: after a branch switch you must restart (see
# contracts/middleware.py DevServerCodeDriftMiddleware).
"$ROOT_DIR/scripts/dev_down.sh"
pkill -f "uvicorn config.asgi:application" 2>/dev/null || true
sleep 1

"$ROOT_DIR/scripts/dev_up.sh" "$INTERVAL_MINUTES"
