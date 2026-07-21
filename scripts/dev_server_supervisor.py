#!/usr/bin/env python3
"""Durable Django runserver supervisor with autoreload.

Why this exists
---------------
``manage.py runserver --noreload`` stays up under ``nohup``, but freezes
URLconf across branch switches (templates reload from disk → NoReverseMatch).

Plain ``runserver`` (with autoreload) forks a watcher that often dies when the
launching shell exits. This supervisor:

1. Detaches into its own session (survives terminal / agent shell exit)
2. Runs ``runserver`` *with* autoreload so Python/URLconf pick up checkouts
3. Restarts the worker if it exits unexpectedly
4. Records ``logs/devserver.boot_sha`` and forwards SIGTERM/SIGINT cleanly
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
PID_FILE = LOG_DIR / 'devserver.pid'
BOOT_FILE = LOG_DIR / 'devserver.boot_sha'
LOG_FILE = LOG_DIR / 'devserver.log'

HOST = os.environ.get('DEV_HOST', '0.0.0.0')
PORT = os.environ.get('DEV_PORT', '8060')
PYTHON = ROOT / '.venv' / 'bin' / 'python'

_child: subprocess.Popen | None = None
_stopping = False


def _log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f'[supervisor] {message}\n'
    with LOG_FILE.open('a', encoding='utf-8') as handle:
        handle.write(line)
        handle.flush()
    # Also mirror to stderr when attached to a terminal.
    if sys.stderr.isatty():
        sys.stderr.write(line)


def _write_boot_sha() -> None:
    try:
        sha = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        sha = 'unknown'
    BOOT_FILE.write_text(sha + '\n', encoding='utf-8')


def _stop_child(signum: int = signal.SIGTERM) -> None:
    global _child
    proc = _child
    if proc is None:
        return
    if proc.poll() is not None:
        _child = None
        return
    try:
        # Autoreload parent + worker share this process group when started
        # without start_new_session on the child.
        os.killpg(proc.pid, signum)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(signum)
        except (ProcessLookupError, OSError):
            pass
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.wait(timeout=3)
    _child = None


def _handle_signal(signum, _frame) -> None:
    global _stopping
    _stopping = True
    _log(f'received signal {signum}; stopping runserver')
    _stop_child(signum)
    raise SystemExit(0)


def _start_runserver() -> subprocess.Popen:
    env = os.environ.copy()
    env['DATABASE_URL'] = ''
    env['DJANGO_SETTINGS_MODULE'] = 'config.settings_development'
    env['DJANGO_DEBUG'] = env.get('DJANGO_DEBUG') or 'true'
    # Avoid nested reloader confusion if something already set RUN_MAIN.
    env.pop('RUN_MAIN', None)

    if not PYTHON.exists():
        raise FileNotFoundError(f'Missing venv python at {PYTHON}')

    cmd = [
        str(PYTHON),
        '-u',
        str(ROOT / 'manage.py'),
        'runserver',
        f'{HOST}:{PORT}',
    ]
    _write_boot_sha()
    _log(f'starting {" ".join(cmd)} (boot {BOOT_FILE.read_text(encoding="utf-8").strip()[:8]})')

    log_handle = LOG_FILE.open('a', encoding='utf-8')
    try:
        # Own session for the runserver tree so we can signal reloader+worker
        # together. Supervisor is already session-detached from the launcher.
        return subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=(),
        )
    finally:
        # Child owns the FD after Popen; close our copy.
        log_handle.close()


def main() -> int:
    global _child

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Detach from controlling terminal when launched under nohup/agent shells.
    try:
        os.setsid()
    except OSError:
        pass

    PID_FILE.write_text(str(os.getpid()) + '\n', encoding='utf-8')
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    backoff = 1.0
    while not _stopping:
        started = time.monotonic()
        try:
            _child = _start_runserver()
        except Exception as exc:  # noqa: BLE001
            _log(f'failed to spawn runserver: {exc}')
            time.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
            continue

        code = _child.wait()
        _child = None
        if _stopping:
            break
        uptime = time.monotonic() - started
        if uptime > 30:
            backoff = 1.0
        _log(f'runserver exited with code {code} after {uptime:.0f}s; restarting in {backoff:.1f}s')
        time.sleep(backoff)
        backoff = min(backoff * 1.5, 15.0)

    _log('supervisor exiting')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
