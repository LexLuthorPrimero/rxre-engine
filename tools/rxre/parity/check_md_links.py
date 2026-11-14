#!/usr/bin/env python3
"""check_md_links — verify relative links and anchors inside Markdown documentation.

Reusable documentation-integrity verifier, born from docs reorganization work.

When a docs tree is rearranged (sections moved across files, guides split,
URLs preserved for compatibility), links rot quietly: a relative target stops
existing, or an anchor no longer names a heading. This verifier reports broken
relative links and anchors across a Markdown tree, fails closed, and never
touches the network.

Semantics
---------
- Fenced code blocks and inline code spans are excluded from scanning.
- Scheme-qualified links (https://, mailto:) and reference-style links
  (`[text][ref]`) are skipped and counted separately, not validated.
- Root-absolute targets starting with `/` are skipped (cannot be grounded
  without a publish root) and counted.
- Relative targets must resolve against the source file's directory.
  A link to a directory passes when the directory exists.
- Anchors (`#frag`) inside a relative target must name a heading or an
  explicit `<a id="frag">` in the target file. A pure `#frag` link is
  checked inside the source file.
- Anchor slugification follows GitHub's scheme (lowercase, letters/digits/
  spaces/dashes kept, spaces become dashes), which is a close match, not a
  byte-perfect contract with every Markdown processor.

Exit codes: 0 clean, 1 broken links found, 2 usage or IO error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

SCAN_SUFFIXES = {".md"}
EXCLUDE_DIRS = {".git", "node_modules", ".turbo", "dist", ".next", ".venv", "__pycache__", ".vitepress"}
SKIP_SCHEMES = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
AID_RE = re.compile(r"<[^>]*\bid=\"([^\"]+)\"[^>]*>")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


@dataclass(frozen=True)
class BrokenLink:
    path: str
    line: int
    target: str
    reason: str


@dataclass(frozen=True)
class Report:
    root: str
    files_scanned: int
    links_checked: int
    skipped: int
    broken: tuple[BrokenLink, ...]

    @property
    def ok(self) -> bool:
        return not self.broken


def slugify(heading: str) -> str:
    # GitHub's algorithm lowercases, turns spaces into dashes and drops
    # punctuation/control characters; letters, marks, numbers and format
    # characters (e.g. ZWNJ) survive.
    heading = re.sub(r"<[^>]+>", "", heading).strip().lower()
    out: list[str] = []
    for char in heading:
        kind = unicodedata.category(char)
        if char == " ":
            out.append("-")
        elif char == "`":
            continue  # Markdown backtick, not part of the slug
        elif kind.startswith(("P", "C", "Z")) and char != "-":
            if char in ("\u200c", "\u200d"):  # ZWNJ/ZWJ kept by GitHub
                out.append(char)
            continue
        else:
            out.append(char)
    return "".join(out)


def strip_code(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            lines.append("")
            continue
        if in_fence:
            lines.append("")
        else:
            lines.append(re.sub(r"`[^`\n]*`", "", raw))
    return "\n".join(lines)


def anchors_of(text: str) -> set[str]:
    slugs: set[str] = set()
    in_fence = False
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(raw)
        if match:
            slugs.add(slugify(match.group(1)))
        for aid in AID_RE.findall(raw):
            slugs.add(aid)
    return slugs


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix != ".md":
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def check_root(root: Path) -> Report:
    cache: dict[Path, set[str]] = {}

    def anchors(path: Path) -> set[str]:
        key = path.resolve()
        if key not in cache:
            try:
                cache[key] = anchors_of(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                cache[key] = set()
        return cache[key]

    broken: list[BrokenLink] = []
    checked = 0
    skipped = 0
    files = collect_files(root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = strip_code(path.read_text(encoding="utf-8", errors="replace"))
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(2).split()[0]
                if SKIP_SCHEMES.match(target):
                    skipped += 1
                    continue
                if target.startswith("/"):
                    skipped += 1
                    continue
                if not target:
                    skipped += 1
                    continue
                checked += 1
                file_part, _, frag = target.partition("#")
                file_part = unquote(file_part)
                if file_part == "":
                    target_path = path
                else:
                    target_path = (path.parent / file_part).resolve()
                try:
                    target_path.relative_to(root.resolve())
                except ValueError:
                    broken.append(BrokenLink(rel, lineno, target, "target escapes repository root"))
                    continue
                if not target_path.exists():
                    broken.append(BrokenLink(rel, lineno, target, "no such relative target"))
                    continue
                if frag and target_path.is_file():
                    if unquote(frag) not in anchors(target_path):
                        broken.append(BrokenLink(rel, lineno, target, f"no such anchor #{frag}"))
    return Report(str(root.resolve()), len(files), checked, skipped, tuple(broken))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    report = check_root(args.root.resolve())
    if args.json:
        print(
            json.dumps(
                {
                    "root": report.root,
                    "files_scanned": report.files_scanned,
                    "links_checked": report.links_checked,
                    "skipped": report.skipped,
                    "ok": report.ok,
                    "broken": [asdict(b) for b in report.broken],
                },
                indent=2,
            )
        )
    else:
        print(
            f"root={report.root} files={report.files_scanned} checked={report.links_checked} skipped={report.skipped}"
        )
        if report.ok:
            print("ok: all relative Markdown links and anchors resolve")
        else:
            for item in report.broken:
                print(f"{item.path}:{item.line}: {item.target} — {item.reason}")
            print(f"{len(report.broken)} broken link(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
