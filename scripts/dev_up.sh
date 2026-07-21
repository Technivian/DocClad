#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INTERVAL_MINUTES="${1:-60}"
DEV_PORT="${DEV_PORT:-8060}"
DEV_HOST="${DEV_HOST:-0.0.0.0}"
mkdir -p logs

wait_for_port() {
  local tries=0
  while [[ $tries -lt 60 ]]; do
    if lsof -i "tcp:${DEV_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
    tries=$((tries + 1))
  done
  return 1
}

health_check() {
  curl -sf --connect-timeout 3 "http://127.0.0.1:${DEV_PORT}/login/" >/dev/null
}

start_proc() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  shift 3

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file"))."
    return 0
  fi

  : > "$log_file"
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$@" >> "$log_file" 2>&1 &
  else
    nohup "$@" >> "$log_file" 2>&1 &
  fi
  local pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" > "$pid_file"

  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "Failed to start $name. See $log_file for details."
    tail -20 "$log_file" || true
    return 1
  fi

  echo "Started $name (pid $pid)."
}

stop_port_listeners() {
  local pids
  pids="$(lsof -ti "tcp:${DEV_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping existing listeners on port ${DEV_PORT}..."
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
    done
    sleep 1
    pids="$(lsof -ti "tcp:${DEV_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      for pid in $pids; do
        kill -9 "$pid" 2>/dev/null || true
      done
    fi
  fi
}

current_git_sha() {
  git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown"
}

boot_sha_matches_workspace() {
  local boot_file="logs/devserver.boot_sha"
  [[ -f "$boot_file" ]] || return 1
  [[ "$(cat "$boot_file")" == "$(current_git_sha)" ]]
}

stop_supervisor() {
  local pid_file="logs/devserver.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      # Supervisor + runserver process group(s).
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
  # Also stop any orphaned runserver/reloader still bound to the port.
  stop_port_listeners
  pkill -f "manage.py runserver ${DEV_HOST}:${DEV_PORT}" 2>/dev/null || true
  pkill -f "manage.py runserver 0.0.0.0:${DEV_PORT}" 2>/dev/null || true
  pkill -f "manage.py runserver 127.0.0.1:${DEV_PORT}" 2>/dev/null || true
}

start_dev_server() {
  local pid_file="logs/devserver.pid"
  local log_file="logs/devserver.log"
  local supervisor="$ROOT_DIR/scripts/dev_server_supervisor.py"

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    if wait_for_port && health_check; then
      echo "dev server already running (pid $(cat "$pid_file"))."
      return 0
    fi
    echo "Stale dev server pid file; restarting."
    stop_supervisor
  fi

  local port_pid
  port_pid="$(lsof -ti "tcp:${DEV_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "$port_pid" ]]; then
    if health_check && [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "Adopted existing supervised dev server on port ${DEV_PORT} (pid $(cat "$pid_file"))."
      return 0
    fi
    echo "Replacing unsupervised listener on port ${DEV_PORT}."
    stop_supervisor
  fi

  : > "$log_file"
  # Launch the supervisor detached. It runs runserver *with* autoreload and
  # restarts the worker if the reloader exits after shell/agent teardown.
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid env DEV_HOST="$DEV_HOST" DEV_PORT="$DEV_PORT" \
      "$ROOT_DIR/.venv/bin/python" -u "$supervisor" >> "$log_file" 2>&1 &
  else
    nohup env DEV_HOST="$DEV_HOST" DEV_PORT="$DEV_PORT" \
      "$ROOT_DIR/.venv/bin/python" -u "$supervisor" >> "$log_file" 2>&1 &
  fi
  # Supervisor rewrites the pid file to its own pid; keep the launcher pid as
  # a fallback until that happens.
  local launcher_pid=$!
  disown "$launcher_pid" 2>/dev/null || true
  echo "$launcher_pid" > "$pid_file"

  # Wait for supervisor to claim the pid file / port.
  local tries=0
  while [[ $tries -lt 40 ]]; do
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      break
    fi
    sleep 0.1
    tries=$((tries + 1))
  done

  if ! wait_for_port; then
    echo "dev server did not bind to port ${DEV_PORT}. See $log_file"
    tail -40 "$log_file" || true
    return 1
  fi

  if ! health_check; then
    echo "dev server is listening but /login/ is not healthy. See $log_file"
    tail -40 "$log_file" || true
    return 1
  fi

  echo "dev server ready at http://localhost:${DEV_PORT}/ (autoreload supervised, pid $(cat "$pid_file"))"
}

start_dev_server

start_proc "reminder scheduler" "logs/reminder_scheduler.pid" "logs/reminder_scheduler.log" \
  env DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_development \
  "$ROOT_DIR/.venv/bin/python" -u manage.py run_reminder_scheduler --interval-minutes "$INTERVAL_MINUTES"

echo "Services started."
echo "- App URL: http://localhost:${DEV_PORT}/"
echo "- Mode: supervised runserver with autoreload (survives shell exit; picks up branch switches)"
echo "- Server log: logs/devserver.log"
echo "- Scheduler log: logs/reminder_scheduler.log"
