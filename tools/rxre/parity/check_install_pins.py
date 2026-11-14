#!/usr/bin/env python3
"""check_install_pins — verify documentation install examples pin the shipped version.

Reusable documentation-vs-reality verifier, born from upstream issue REA #3423.

`npx rea-agents` / `npx -y rea-agents@latest` examples in README, docs and the
website executed whatever the registry resolved at copy time, while the CLI
itself pins a version once installed (REA's `updateMaintenance`). This tool
fails closed when invocation examples lack a version pin, when a pinned
version has drifted from the shipped `package.json`, or when the copy-paste
installer URL tracks a moving ref (`main`, `HEAD`) instead of the release tag.

Scope and honesty boundaries
----------------------------
- Scans text docs/scripts only: `.md`, `.html`, `.sh` (excluding node_modules,
  dist, .turbo and historical records such as CHANGELOG and the generated
  error corpus, which describe the past on purpose).
- Checks invocation strings and installer URLs only. It does NOT audit prose,
  does NOT verify that the pinned version exists on the registry, and does NOT
  claim the pin is *good* — only that it is present, current and stable.
- No network access; all facts come from the repository.

Exit codes: 0 clean, 1 findings, 2 usage or IO error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCAN_SUFFIXES = {".md", ".html", ".sh"}
EXCLUDE_DIRS = {".git", "node_modules", ".turbo", "dist", ".next", ".venv", "__pycache__"}
EXCLUDE_FILES = {"CHANGELOG.md", "CHANGELOG.rst", "user-visible-errors.csv"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    detail: str


@dataclass(frozen=True)
class Report:
    repo: str
    package: str
    version: str
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def escaped(value: str) -> str:
    return re.escape(value)


def collect_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        if path.name in EXCLUDE_FILES:
            continue
        files.append(path)
    return files


def pin_of(invocation: re.Match[str]) -> str | None:
    pin = invocation.group("pin")
    return pin if pin else None


def scan_text(
    text: str, rel: str, package: str, owner_repo: str, installer: str, version: str
) -> list[Finding]:
    findings: list[Finding] = []
    pkg = escaped(package)
    # (npx|npx.cmd|bunx) plus optional runner flags, then the package.
    invocation_re = re.compile(
        rf"(?:npx(?:\.cmd)?|bunx)(?:\s+(?:-y|--yes|--no-install|[^\s@]+))*\s+{pkg}(?:@(?P<pin>[A-Za-z0-9][A-Za-z0-9._-]*))?"
    )
    installer_re = re.compile(
        rf"raw\.githubusercontent\.com/{escaped(owner_repo)}/(?P<ref>[^/\s\"'<>]+)/{escaped(installer)}"
    )
    type_def = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    allow_next = False
    for lineno, line in enumerate(text.splitlines(), 1):
        line_allowed = allow_next or "install-pin: allow" in line
        allow_next = "install-pin: allow" in line
        if line_allowed:
            continue
        templated = "@<" in line or "@${" in line or "@[" in line
        for match in invocation_re.finditer(line):
            if templated:
                continue
            pin = pin_of(match)
            if pin is None or pin == "latest":
                findings.append(
                    Finding(
                        "unpinned-invocation",
                        rel,
                        lineno,
                        f"`{match.group(0)}` does not name a version; it executes whatever the registry currently resolves",
                    )
                )
            elif not type_def.match(pin):
                # Named dist-tags are moving pointers; so is anything this
                # check cannot recognize as an immutable release version.
                findings.append(
                    Finding(
                        "unpinned-invocation",
                        rel,
                        lineno,
                        f"`{match.group(0)}` pins `{pin}`, which is not an immutable release version",
                    )
                )
            elif pin != version:
                findings.append(
                    Finding(
                        "stale-pin",
                        rel,
                        lineno,
                        f"`{match.group(0)}` pins {pin}, but package.json ships {version}",
                    )
                )
        for match in installer_re.finditer(line):
            ref = match.group("ref")
            if "$" in ref:
                # Shell variable reference; not a literal ref to falsify.
                continue
            expected = f"{package}-{version}"
            if ref != expected:
                findings.append(
                    Finding(
                        "unstable-installer-ref",
                        rel,
                        lineno,
                        f"installer URL tracks `{ref}`, not the release tag `{expected}`",
                    )
                )
    return findings


def check(repo: Path, package: str, owner_repo: str, installer: str) -> Report:
    pkg_json = repo / "package.json"
    if not pkg_json.is_file():
        raise SystemExit(f"error: {pkg_json} does not exist")
    version = json.loads(pkg_json.read_text(encoding="utf-8")).get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit("error: package.json has no version string")
    findings: list[Finding] = []
    for path in collect_files(repo):
        rel = path.relative_to(repo).as_posix()
        findings.extend(
            scan_text(path.read_text(encoding="utf-8", errors="replace"), rel, package, owner_repo, installer, version)
        )
    return Report(str(repo.resolve()), package, version, tuple(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path, help="repository root containing package.json")
    parser.add_argument("--package", default="rea-agents")
    parser.add_argument("--owner-repo", default="morluto/rea", help="GitHub owner/repo for raw installer URLs")
    parser.add_argument("--installer-name", default="install.sh", help="installer file name referenced in docs")
    parser.add_argument("--json", action="store_true", help="emit JSON report instead of text")
    args = parser.parse_args(argv)
    if not args.repo.is_dir():
        print(f"error: {args.repo} is not a directory", file=sys.stderr)
        return 2
    try:
        report = check(args.repo.resolve(), args.package, args.owner_repo, args.installer_name)
    except SystemExit as exc:
        print(exc.code, file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {
                    "repo": report.repo,
                    "package": report.package,
                    "version": report.version,
                    "ok": report.ok,
                    "findings": [asdict(f) for f in report.findings],
                },
                indent=2,
            )
        )
    else:
        print(f"repo={report.repo} package={report.package} version={report.version}")
        if report.ok:
            print("ok: all scanned install examples pin the shipped version")
        else:
            for finding in report.findings:
                print(f"{finding.rule}: {finding.path}:{finding.line}: {finding.detail}")
            print(f"{len(report.findings)} finding(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
