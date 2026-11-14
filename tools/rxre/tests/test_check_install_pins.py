"""Tests for the install-pin documentation verifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools/rxre/parity/check_install_pins.py"


def make_repo(tmp: Path, version: str, files: dict[str, str]) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    files.setdefault("package.json", json.dumps({"name": "rea-agents", "version": version}))
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return repo


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_repo_passes(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {
            "README.md": "```\nnpx -y rea-agents@6.9.0 setup\n```\n",
            "docs/install.sh": "curl -fsSL https://raw.githubusercontent.com/morluto/rea/rea-agents-6.9.0/install.sh | bash\n",
        },
    )
    proc = run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bare_invocation_is_reported(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"README.md": "```\nnpx rea-agents setup\n```\n"},
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "unpinned-invocation" in proc.stdout
    assert "README.md:2" in proc.stdout


def test_latest_alias_is_reported(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"README.md": "npx -y rea-agents@latest analyze --json\n"},
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "unpinned-invocation" in proc.stdout


def test_stale_pin_is_reported_against_package_json(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"README.md": "npx -y rea-agents@6.8.0 analyze --json\n"},
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "stale-pin" in proc.stdout


def test_moving_installer_ref_is_reported(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {
            "docs/get-started.md": "curl -fsSL https://raw.githubusercontent.com/morluto/rea/main/install.sh | bash\n"
        },
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "unstable-installer-ref" in proc.stdout


def test_changelog_and_historical_records_are_not_flagged(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"CHANGELOG.md": "Release notes: npx -y rea-agents@latest setup\n"},
    )
    proc = run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bunx_and_npx_cmd_are_checked(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {
            "windows.md": "npx.cmd rea-agents@6.9.0 setup\n",
            "bun.md": "bunx rea-agents@6.9.0 setup\n",
            "bare.md": "bunx rea-agents setup\n",
        },
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "bare.md:1" in proc.stdout
    report = json.loads(run(repo, "--json").stdout)
    assert [f["path"] for f in report["findings"]] == ["bare.md"]


def test_json_report_schema_and_exit(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"README.md": "npx rea-agents setup\n"},
    )
    proc = run(repo, "--json")
    report = json.loads(proc.stdout)
    assert proc.returncode == 1
    assert report["package"] == "rea-agents"
    assert report["version"] == "6.9.0"
    assert report["ok"] is False
    assert {f["rule"] for f in report["findings"]} == {"unpinned-invocation"}


@pytest.mark.parametrize("bad", ["beta", "canary", "next"])
def test_moving_dist_tags_are_rejected(tmp_path: Path, bad: str) -> None:
    repo = make_repo(
        tmp_path,
        "6.9.0",
        {"README.md": f"npx -y rea-agents@{bad} setup\n"},
    )
    proc = run(repo)
    assert proc.returncode == 1
    assert "unpinned-invocation" in proc.stdout
