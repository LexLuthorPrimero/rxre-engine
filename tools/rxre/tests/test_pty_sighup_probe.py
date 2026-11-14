"""Tests for the PTY SIGHUP POSIX-semantics probe."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools/rxre/parity/pty_sighup_probe.py"

spec = importlib.util.spec_from_file_location("pty_sighup_probe", TOOL)
assert spec is not None
module = importlib.util.module_from_spec(spec)
sys.modules["pty_sighup_probe"] = module
spec.loader.exec_module(module)  # type: ignore[union-attr]

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="PTYs are POSIX-only")


def _run_cli(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--workspace", str(workspace), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_cli_confirms_posix_semantics(tmp_path: Path) -> None:
    proc = _run_cli(tmp_path / "ws", "--ticks", "4", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"verdict": "PTY_SIGHUP_CONFIRMED"' in proc.stdout


def test_cli_rejects_invalid_ticks(tmp_path: Path) -> None:
    proc = _run_cli(tmp_path / "ws", "--ticks", "1")
    assert proc.returncode == 2


def test_direct_mode_child_finishes(tmp_path: Path) -> None:
    fixture = tmp_path / "probe_fixture.py"
    fixture.write_text(module.FIXTURE, encoding="utf-8")
    log = tmp_path / "direct.log"
    result = module.run_direct(fixture, log, 4)
    assert result.ok, result.error
    assert "finished" in result.log


def test_pty_mode_child_gets_sighup(tmp_path: Path) -> None:
    fixture = tmp_path / "probe_fixture.py"
    fixture.write_text(module.FIXTURE, encoding="utf-8")
    log = tmp_path / "pty.log"
    result = module.run_pty(fixture, log, 4)
    assert result.ok, result.error
    assert any(line.startswith("signal 1") for line in result.log)


def test_verdict_mismatch_and_inconclusive() -> None:
    direct = module.ScenarioResult("direct", True, ("finished",), None)
    pty_run = module.ScenarioResult("pty", True, ("finished",), None)
    code, _ = module.verdict(direct, pty_run)
    assert code == "MISMATCH"
    broken = module.ScenarioResult("direct", False, (), "boom")
    code, _ = module.verdict(broken, pty_run)
    assert code == "INCONCLUSIVE"
