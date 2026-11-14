"""Tests for the packaged-feature release verifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools/rxre/parity/check_release_features.py"

package_name = "pkg"

def make_pkg(tmp_path: Path, files: dict[str, bytes | str]) -> Path:
    root = tmp_path / package_name
    root.mkdir(parents=True)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content_b = content.encode("utf-8")
        else:
            content_b = content
        target.write_bytes(content_b)
    return root


def run(pkg: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(pkg), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_all_markers_present_exits_zero(tmp_path: Path) -> None:
    pkg = make_pkg(tmp_path, {"dist/server/createServer.js": "parseMcpToolFamilies(environment.REA_MCP_TOOL_FAMILIES)"})
    proc = run(pkg, "--marker", "REA_MCP_TOOL_FAMILIES", "--marker", "parseMcpToolFamilies")
    assert proc.returncode == 0, proc.stdout
    proc = run(pkg, "--marker", "REA_MCP_TOOL_FAMILIES")
    assert proc.returncode == 0


def test_missing_marker_exits_one(tmp_path: Path) -> None:
    pkg = make_pkg(tmp_path, {"dist/a.js": "hello"})
    proc = run(pkg, "--marker", "FEATURE_THAT_DOES_NOT_EXIST")
    assert proc.returncode == 1
    assert "MISSING" in proc.stdout


def test_invalid_regex_exits_two(tmp_path: Path) -> None:
    pkg = make_pkg(tmp_path, {"a.js": "hello"})
    proc = run(pkg, "--marker", "(")
    assert proc.returncode == 2


def test_missing_directory_exits_two(tmp_path: Path) -> None:
    proc = run(tmp_path / "nope", "--marker", "x")
    assert proc.returncode == 2


def test_oversize_file_is_skipped(tmp_path: Path) -> None:
    bulk = b"A" * (8 * 1024 * 1024 + 1)
    big = b"needle" * 1000
    pkg = make_pkg(tmp_path, {"big.bin": bulk, "small.marker": "needle"})
    proc = run(pkg, "--marker", "^needle$", "--json")
    report = json.loads(proc.stdout)
    assert report["skipped_large"] == ["big.bin"]


def test_vcs_directories_are_skipped(tmp_path: Path) -> None:
    pkg = make_pkg(tmp_path, {".git/HEAD": "ref: refs/heads/main", "dist/a.js": "no token here"})
    proc = run(pkg, "--marker", "^ref: refs/heads/main$")
    assert proc.returncode == 1


def test_json_report_schema(tmp_path: Path) -> None:
    pkg = make_pkg(tmp_path, {"a.js": "needle", "b.js": "needle"})
    proc = run(pkg, "--marker", "needle", "--json")
    report = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert report["ok"] is True
    assert report["markers"][0]["matched_files"] == 2
    assert len(report["markers"][0]["witnesses"]) <= 3


def test_witnesses_are_capped_at_three(tmp_path: Path) -> None:
    files = {f"dist/pkg-{i}.js": "needle" for i in range(5)}
    pkg = make_pkg(tmp_path, files)
    proc = run(pkg, "--marker", "needle", "--json")
    report = json.loads(proc.stdout)
    marker = report["markers"][0]
    assert marker["matched_files"] == 5
    assert len(marker["witnesses"]) == 3


def test_symlink_is_not_followed(tmp_path: Path) -> None:
    import os

    pkg = make_pkg(tmp_path, {"real.js": "needle"})
    os.symlink(pkg / "real.js", pkg / "link.js")
    # Remove the real file so only the symlink carries the marker.
    (pkg / "real.js").unlink()
    proc = run(pkg, "--marker", "needle")
    assert proc.returncode == 1
