#!/usr/bin/env python3
"""check_release_features — verify doc/commit-claimed features exist in a packaged tree.

Reusable release-integrity verifier, born from shipped release notes (REA #7680).

The class of failure: documentation, commit messages or release notes claim a
feature is present; the shipped artifact lacks it (REA #7680: 6.8.0 notes
advertised MMIO attribution after the modules were removed pre-release). This
check fails closed when a known marker of the feature is absent from the
packaged tree. It does not read the network; the package tree is the caller's
responsibility.

Semantics
---------
- `--marker PATTERN` (repeatable): Python regular expression applied to the
  bytes of every regular file in the package tree.
- Files larger than 8 MiB are skipped and reported as `files_skipped_large`.
- Directories are scanned recursively; symbolic links are not followed;
  VCS/dependency-cache directories (.git, .hg, .svn, node_modules, .turbo) are skipped.
- Every listed marker must appear in at least one file.
- With `--json`, a structured report is emitted: per marker, matched file
  count and a few witness paths (max 3).

Exit codes: 0 all markers present, 1 at least one missing, 2 usage or IO error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_WITNESSES = 3
EXCLUDE_DIR_NAMES = {".git", ".hg", ".svn", "node_modules", ".turbo"}


@dataclass(frozen=True)
class MarkerReport:
    pattern: str
    matched_files: int
    witnesses: tuple[str, ...]

    @property
    def present(self) -> bool:
        return self.matched_files > 0


@dataclass(frozen=True)
class Report:
    package_dir: str
    file_count: int
    skipped_large: tuple[str, ...]
    markers: tuple[MarkerReport, ...]

    @property
    def ok(self) -> bool:
        return all(marker.present for marker in self.markers)


def collect_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in EXCLUDE_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_BYTES:
            skipped.append(path.relative_to(root).as_posix())
            continue
        files.append(path)
    return files, skipped


def scan(root: Path, markers: list[tuple[str, re.Pattern[bytes]]]) -> Report:
    marker_counts = [0] * len(markers)
    witnesses: list[list[str]] = [[] for _ in markers]
    files, skipped = collect_files(root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for index, (_, pattern) in enumerate(markers):
            if pattern.search(blob):
                marker_counts[index] += 1
                if len(witnesses[index]) < MAX_WITNESSES:
                    witnesses[index].append(rel)
    result = tuple(
        MarkerReport(marker_str, marker_counts[i], tuple(witnesses[i]))
        for i, (marker_str, _) in enumerate(markers)
    )
    return Report(str(root.resolve()), len(files), tuple(skipped), result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--marker", action="append", required=True, help="regex expected in the package")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.package_dir.resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        markers = [(p, re.compile(p.encode("utf-8"))) for p in args.marker]
    except re.error as exc:
        print(f"error: invalid --marker regex: {exc}", file=sys.stderr)
        return 2
    report = scan(root, markers)
    if args.json:
        print(
            json.dumps(
                {
                    "package_dir": report.package_dir,
                    "file_count": report.file_count,
                    "skipped_large": list(report.skipped_large),
                    "ok": report.ok,
                    "markers": [asdict(m) for m in report.markers],
                },
                indent=2,
            )
        )
    else:
        print(f"package={report.package_dir} files={report.file_count} skipped_large={len(report.skipped_large)}")
        for marker in report.markers:
            state = "present" if marker.present else "MISSING"
            witness = ", ".join(marker.witnesses) or "-"
            print(f"{state}: /{marker.pattern}/ in {marker.matched_files} file(s) [{witness}]")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
