"""Tests for the Markdown link and anchor verifier."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools/rxre/parity/check_md_links.py"

spec = importlib.util.spec_from_file_location("check_md_links", TOOL)
assert spec is not None
module = importlib.util.module_from_spec(spec)
sys.modules["check_md_links"] = module
spec.loader.exec_module(module)  # type: ignore[union-attr]


def fixture(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_clean_tree_passes(tmp_path: Path) -> None:
    root = fixture(
        tmp_path,
        {"a.md": "[ok](b.md#target-anchor)\n", "b.md": "## Target anchor\n\ntext\n"},
    )
    assert run(root).returncode == 0, run(root).stdout


def test_missing_relative_file_is_broken(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "[x](missing.md)\n"})
    proc = run(root)
    assert proc.returncode == 1
    assert "no such relative target" in proc.stdout


def test_missing_anchor_is_broken(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "[x](b.md#nope)\n", "b.md": "## Other\n\ntext\n"})
    proc = run(root)
    assert proc.returncode == 1
    assert "no such anchor #nope" in proc.stdout


def test_anchor_in_same_file_resolves(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "see [x](#section-one)\n\n## Section one\n\ntext\n"})
    assert run(root).returncode == 0, run(root).stdout


def test_links_inside_code_are_ignored(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "```\n[x](missing.md)\n```\n\ntext\n"})
    assert run(root).returncode == 0, run(root).stdout


def test_scheme_links_are_skipped(tmp_path: Path) -> None:
    root = fixture(
        tmp_path,
        {"a.md": "[x](https://example.com/a.md#any) [y](mailto:a@b.c)\n"},
    )
    proc = run(root, "--json")
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["skipped"] == 2
    assert report["links_checked"] == 0


def test_root_absolute_links_are_skipped(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "[x](/absolute/path.md)\n"})
    assert run(root, "--json").stdout and json.loads(run(root, "--json").stdout)["skipped"] == 1


def test_html_id_anchors_resolve(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": '[x](b.md#explicit-id)\n', "b.md": '<div id="explicit-id"></div>\n'})
    assert run(root).returncode == 0, run(root).stdout


def test_target_escaping_repo_root_is_broken(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "[x](../../outside.md)\n"})
    proc = run(root)
    assert proc.returncode == 1
    assert "escapes repository root" in proc.stdout


def test_json_report_schema_and_exit_codes(tmp_path: Path) -> None:
    root = fixture(tmp_path, {"a.md": "[x](missing.md)\n"})
    proc = run(root, "--json")
    report = json.loads(proc.stdout)
    assert proc.returncode == 1
    assert report["ok"] is False
    assert report["broken"][0]["path"] == "a.md"
    assert "reason" in report["broken"][0]
