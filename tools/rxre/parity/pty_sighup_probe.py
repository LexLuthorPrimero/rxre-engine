#!/usr/bin/env python3
"""pty_sighup_probe — verify the POSIX session-semantics claim behind PTY hangups.

Reusable black-box verifier, born from upstream issue REA #8780.

Assertion under test: *when a command runs with a PTY and the PTY's session
leader exits, the still-running children in the PTY's foreground process group
receive SIGHUP from the terminal, even though no framework signaled them.*
This is the terminal's doing (cf. `script -c <probe>`, `ssh -t host <probe>`),
not REA's. CAPTURE harnesses, CI runners and wrappers that keep the target as
session leader inherit it; workers that must outlive the target must leave the
group (`setsid`/`setpgid(0, 0)`) or handle SIGHUP.

The probe spawns an embedded fixture — a session-leader-to-be that forks a
grandchild which logs a tick loop and catchable signals — in two modes:

  direct mode : fixture runs with no PTY (subprocess). The grandchild, still
                in the leader's group, survives the leader's exit.
  pty    mode : fixture runs under a PTY as session leader (python's pty.fork).
                When the fixture leader exits, the terminal delivers SIGHUP to
                the foreground group, hanging up the grandchild.

Verdicts (CLI exit codes): 0 CONFIRMED (both modes matched POSIX), 1 MISMATCH
(claim failed somewhere), 2 usage/IO error, 3 INCONCLUSIVE (fixture broken or
timed out; no semantics verdict possible).

Not a fuzzer, not a kernel conformance suite: one bounded POSIX scenario,
reported honestly. The fixture lives entirely in a caller-selected workspace.
No network, no subprocess other than the fixture, no elevation.
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

FIXTURE = r"""import os, signal, time
import sys

mask = set(range(1, 32)) - {signal.SIGKILL, signal.SIGSTOP}
signal.pthread_sigmask(signal.SIG_BLOCK, mask)
log_path, ticks = sys.argv[1], int(sys.argv[2])

pid = os.fork()
if pid != 0:
    sys.stdout.write("parent-exit\n")
    sys.stdout.flush()
    os._exit(0)

with open(log_path, "w", buffering=1) as log:
    log.write(f"child pid={os.getpid()} pgid={os.getpgid(0)}\n")

    def handler(signum, frame):
        log.write(f"signal {signum}\n")
        log.flush()
        os._exit(0)

    for s in mask:
        try:
            signal.signal(s, handler)
        except (OSError, ValueError):
            pass
    signal.pthread_sigmask(signal.SIG_SETMASK, [])

    for i in range(ticks):
        time.sleep(0.25)
        log.write(f"tick {i}\n")
    log.write("finished\n")
"""

DIRECT_TIMEOUT_SECONDS = 15
PTY_DEADLINE_SECONDS = 20


@dataclass(frozen=True)
class ScenarioResult:
    mode: str
    ok: bool
    log: tuple[str, ...]
    error: str | None


def run_direct(fixture: Path, log: Path, ticks: int) -> ScenarioResult:
    log.write_text("", encoding="utf-8")
    try:
        subprocess.run(
            [sys.executable, str(fixture), str(log), str(ticks)],
            capture_output=True,
            timeout=DIRECT_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ScenarioResult("direct", False, tuple(log.read_text().splitlines()), str(exc))
    return ScenarioResult("direct", True, tuple(log.read_text().splitlines()), None)


def run_pty(fixture: Path, log: Path, ticks: int) -> ScenarioResult:
    log.write_text("", encoding="utf-8")
    try:
        pid, master = pty.fork()
    except OSError as exc:
        return ScenarioResult("pty", False, tuple(log.read_text().splitlines()), str(exc))
    if pid == 0:
        os.execv(sys.executable, [sys.executable, str(fixture), str(log), str(ticks)])
    deadline = time.monotonic() + PTY_DEADLINE_SECONDS
    try:
        while time.monotonic() < deadline:
            done, _ = os.waitpid(pid, os.WNOHANG)
            try:
                ready, _, _ = select.select([master], [], [], 0.1)
            except OSError:
                ready = []
            if ready:
                try:
                    if not os.read(master, 65536):
                        break
                except OSError:
                    break
            if done == pid:
                break
        else:
            return ScenarioResult("pty", False, tuple(log.read_text().splitlines()), "deadline exceeded")
        os.waitpid(pid, 0)
    except OSError as exc:
        return ScenarioResult("pty", False, tuple(log.read_text().splitlines()), str(exc))
    finally:
        os.close(master)
    time.sleep(0.5)
    return ScenarioResult("pty", True, tuple(log.read_text().splitlines()), None)


def verdict(direct: ScenarioResult, pty_run: ScenarioResult) -> tuple[str, str]:
    if not direct.ok or not pty_run.ok:
        return "INCONCLUSIVE", f"fixture failure: direct_error={direct.error} pty_error={pty_run.error}"
    direct_survived = "finished" in direct.log
    pty_hungup = any(line.startswith("signal 1") for line in pty_run.log)
    if direct_survived and pty_hungup:
        return "PTY_SIGHUP_CONFIRMED", "direct child survived; PTY-leader child received SIGHUP(1), as POSIX requires"
    detail = f"direct_survived={direct_survived} pty_sighup={pty_hungup}"
    return "MISMATCH", detail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, required=True, help="scratch directory for fixtures and logs")
    parser.add_argument("--ticks", type=int, default=8, help="ticks per grandchild lifetime (default 8, ~2s)")
    parser.add_argument("--json", action="store_true", help="emit JSON report instead of text")
    args = parser.parse_args(argv)
    if args.ticks < 2:
        print("error: --ticks must be >= 2", file=sys.stderr)
        return 2
    workspace = args.workspace
    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create workspace: {exc}", file=sys.stderr)
        return 2
    fixture = workspace / "probe_fixture.py"
    fixture.write_text(FIXTURE, encoding="utf-8")
    direct = run_direct(fixture, workspace / "direct.log", args.ticks)
    pty_run = run_pty(fixture, workspace / "pty.log", args.ticks)
    code, message = verdict(direct, pty_run)
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": code,
                    "message": message,
                    "direct": {"ok": direct.ok, "log": list(direct.log)},
                    "pty": {"ok": pty_run.ok, "log": list(pty_run.log)},
                },
                indent=2,
            )
        )
    else:
        print(f"direct log: {' | '.join(direct.log)}")
        print(f"pty log:    {' | '.join(pty_run.log)}")
        print(f"verdict: {code} — {message}")
    return {"PTY_SIGHUP_CONFIRMED": 0, "MISMATCH": 1, "INCONCLUSIVE": 3}[code]


if __name__ == "__main__":
    sys.exit(main())
