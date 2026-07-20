#!/usr/bin/env python3
"""Double-fork and exec a command so it survives the parent shell exiting.

macOS has no setsid(1). Cursor/agent shells also reap nohup children when the
invoking process group ends. Reparenting via setsid + double-fork fixes both.

Usage:
  python scripts/_daemonize_exec.py --pid-file PATH --log-file PATH --workdir PATH -- \\
    env KEY=VAL ... command args...
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--pid-file", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to exec after --",
    )
    args = parser.parse_args(argv)
    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.error("missing command after --")
    args.command = cmd
    return args


def _wait_for_pid_file(pid_file: str, timeout_s: float = 5.0) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with open(pid_file, encoding="utf-8") as handle:
                pid = int(handle.read().strip())
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            time.sleep(0.05)
    raise SystemExit(f"daemon did not write a live pid to {pid_file}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    pid_file = os.path.abspath(args.pid_file)
    log_file = os.path.abspath(args.log_file)
    workdir = os.path.abspath(args.workdir)
    command = args.command

    os.makedirs(os.path.dirname(pid_file) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    # First fork: parent waits for grandchild pid file, then exits.
    if os.fork() > 0:
        pid = _wait_for_pid_file(pid_file)
        print(pid)
        return 0

    os.setsid()
    if os.fork() > 0:
        os._exit(0)

    os.chdir(workdir)

    # Keep stdio attached to the log for the exec'd process; do not close the
    # duplicated descriptors via a context manager.
    devnull_fd = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull_fd, 0)
    os.close(devnull_fd)

    log_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    if log_fd > 2:
        os.close(log_fd)

    with open(pid_file, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
        handle.flush()

    os.execvp(command[0], command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
