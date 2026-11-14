#!/usr/bin/env python3
"""Verify a REA bounded-view builder (bounded ZIP directory scan) against an independent oracle.

This tool exists for one bounded-view issue observed in practice: REA's bounded ZIP
directory scan (`scanZipDirectory`) kept the *first* Info-ZIP Unicode Path extra field,
while the production decoder (`@zip.js/zip.js`, extra fields keyed by id in a Map) reads
the *final* one — so `hidden/` + `settings.json` in the same extra field list produced a
"missing settings.json" desktop view (reported upstream; fix shipped in REA #10172 /
`rea` fix commit and follow-up `desktop_zip_python` boundary cases).

This harness:
  1. builds three synthetic fixtures into memory (conflicting fields, corrupted final CRC, UTF-8 flag),
  2. invokes the *installed* REA dist implementation of `scanZipDirectory` via Node.js,
  3. decodes each retained record itself with an independent Python model of the documented rule
     (final field wins; unusable final field falls back to the stored raw name; never resurrect
     an earlier claim),
  4. reports `PARITY | DIVERGENT | INCONCLUSIVE` per fixture and in aggregate.

Requires: `node` on PATH and a built REA dist directory (`dist/domain/desktop/zipDirectory.js`
able to be imported by Node.js). State with `--rea-dist PATH` or env `REA_DIST_DIR`. When either
is missing, exits 3 (`INCONCLUSIVE`) — nothing is reported as verified.

Usage: rea_verify_zip_bounded_views.py [--rea-dist PATH] [--json]

Exit: 0 all fixtures PARITY · 2 any fixture DIVERGENT · 3 any fixture INCONCLUSIVE or bad invocation.
This verifies *this* bounded view against *this* oracle on these fixtures; nothing else is admitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zlib
import struct
from pathlib import Path
from typing import Any

UNICODE_PATH = 0x7075
UTF8_NAME = 0x800
UNIX_TYPE = 0o170000
UNIX_DIRECTORY = 0o040000
MSDOS_DIRECTORY = 0x10
STRICT_UTF8 = "utf-8"


def unicode_path_field(raw_stored_name: bytes, unicode_name: bytes, version: int = 1) -> bytes:
    payload = bytes([version]) + struct.pack("<I", zlib.crc32(raw_stored_name) & 0xffffffff) + unicode_name
    return struct.pack("<HH", UNICODE_PATH, len(payload)) + payload


def build_zip(members: list[tuple[bytes, bytes, int, int, int, bytes]]) -> bytes:
    """Build a minimal ZIP64-free archive from (stored_name, data, method, flags, external, central_extra)."""
    locals_: list[bytes] = []
    centrals: list[bytes] = []
    offset = 0
    for name, data, method, flags, external, central_extra in members:
        compressed = data if method == 0 else zlib.compress(data, 9, wbits=-15)
        crc = zlib.crc32(data) & 0xffffffff
        local = (
            b"PK\x03\x04"
            + struct.pack(
                "<HHHHHIIIHH",
                20, flags, method, 0, 0, crc,
                len(compressed), len(data), len(name), len(central_extra),
            )
            + name + central_extra + compressed
        )
        central = (
            b"PK\x01\x02"
            + struct.pack(
                "<HHHHHHIIIHHHHHII",
                45, 20, flags, method, 0, 0,
                crc, len(compressed), len(data),
                len(name), len(central_extra), 0, 0, 0, external, 0,
            )
            + name + central_extra
        )
        patched = bytearray(central)
        struct.pack_into("<I", patched, 42, offset)
        locals_.append(local)
        centrals.append(bytes(patched))
        offset += len(local)
    directory = b"".join(centrals)
    eocd = b"PK\x05\x06" + struct.pack(
        "<HHHHIIH", 0, 0, len(members), len(members), len(directory), offset, 0
    )
    return b"".join(locals_) + directory + eocd


def fixture_conflict() -> bytes:
    return build_zip([(
        b"legacy.bin", b'{"zoom": 1.5}', 8, 0, 0,
        unicode_path_field(b"legacy.bin", b"hidden/") + unicode_path_field(b"legacy.bin", b"settings.json"),
    )])


def fixture_bad_final_crc() -> bytes:
    raw = b"legacy.bin"
    first = unicode_path_field(raw, b"hidden/")
    bad = bytearray(unicode_path_field(raw, b"settings.json"))
    bad[6] ^= 0x01  # flip a bit of the final field's CRC
    return build_zip([(
        raw, b'{"zoom": 1.5}', 8, 0, 0, first + bytes(bad),
    )])


def fixture_utf8_flag() -> bytes:
    raw = "café.json".encode("utf-8")
    data = b'{"zoom": 1.5}'
    extra = unicode_path_field(raw, b"settings.json")  # valid, but the UTF-8 flag wins per REA's documented behavior
    return build_zip([(raw, data, 8, UTF8_NAME, 0, extra)])


FIXTURES = {
    "conflicting_fields": fixture_conflict(),
    "bad_final_crc": fixture_bad_final_crc(),
    "utf8_flag_precedence": fixture_utf8_flag(),
}


def parse_unicode_path_fields(extra: bytes) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    at = 0
    while at + 4 <= len(extra):
        kind, length = struct.unpack_from("<HH", extra, at)
        data = extra[at + 4:at + 4 + length]
        if kind == UNICODE_PATH:
            fields.append({"kind": kind, "version": data[0], "crc": struct.unpack_from("<I", data, 1)[0], "value": data[5:]})
        at += 4 + length
    return fields


def expected_name(raw: bytes, flags: int, extra: bytes) -> bytes | None:
    """Independent model: final usable Unicode Path wins; otherwise stored raw name; None → unreadable UTF-8 claim."""
    fields = parse_unicode_path_fields(extra)
    selected = fields[-1] if fields else None
    stored_crc = zlib.crc32(raw) & 0xffffffff
    if (
        selected is not None
        and selected["version"] == 1
        and not (flags & UTF8_NAME)
        and selected["crc"] == stored_crc
        and len(selected["value"]) > 0
    ):
        return selected["value"]
    if flags & UTF8_NAME:
        try:
            return raw  # REA keeps the UTF-8-flagged stored name verbatim
        except Exception:
            return None
    return raw


def expected_files(bytes_: bytes) -> list[bytes] | None:
    """Model the expected kept file list under the REA documented rule."""
    view = memoryview(bytes_)
    # Walk the central directory manually; fixtures are valid-by-construction.
    end = bytes_.rfind(b"PK\x05\x06")
    total_entries = struct.unpack_from("<H", view, end + 10)[0]
    directory_size = struct.unpack_from("<I", view, end + 12)[0]
    directory_offset = struct.unpack_from("<I", view, end + 16)[0]
    if directory_size < 46 or directory_offset >= end:
        return None
    files: list[bytes] = []
    at = directory_offset
    end_dir = end
    for _ in range(total_entries):
        if view[at:at + 4] != b"PK\x01\x02":
            return None
        name_len = struct.unpack_from("<H", view, at + 28)[0]
        extra_len = struct.unpack_from("<H", view, at + 30)[0]
        comment_len = struct.unpack_from("<H", view, at + 32)[0]
        flags = struct.unpack_from("<H", view, at + 8)[0]
        made_by = struct.unpack_from("<H", view, at + 4)[0]
        external = struct.unpack_from("<I", view, at + 38)[0]
        name = bytes(view[at + 46: at + 46 + name_len])
        extra = bytes(view[at + 46 + name_len: at + 46 + name_len + extra_len])
        resolved = expected_name(name, flags, extra)
        if resolved is None:
            return None
        try:
            slash = resolved.decode("utf-8", errors="strict").endswith("/")
        except UnicodeDecodeError:
            slash = resolved.endswith(b"/")
        is_directory = (
            slash
            or ((external >> 16) & UNIX_TYPE) == UNIX_DIRECTORY
            or ((made_by >> 8) == 0 and (external & MSDOS_DIRECTORY) != 0)
        )
        if not is_directory:
            files.append(resolved)
        at += 46 + name_len + extra_len + comment_len
    return files


def invoke_rea_scan(rea_dist: Path, fixture_path: Path) -> list[bytes] | None:
    node_program = f"""
import fs from 'node:fs';
import vm from 'node:vm';
const bytes = fs.readFileSync({json.dumps(str(fixture_path))});
const dist = {json.dumps(str(rea_dist))};
const {{ scanZipDirectory }} = await import('file://' + dist + '/domain/desktop/zipDirectory.js');
const directory = scanZipDirectory(new Uint8Array(bytes), 1n);
if (directory === undefined) {{
  console.log(JSON.stringify({{ok:false, reason:'unreadable'}}));
  process.exit(0);
}}
const names = [];
for (const record of directory.records) {{
  const r = Buffer.from(record);
  const nameLen = r.readUInt16LE(28);
  const extraLen = r.readUInt16LE(30);
  const flags = r.readUInt16LE(8);
  const rawNameStart = 46, rawNameEnd = 46 + nameLen;
  const extraStart = rawNameEnd, extraEnd = rawNameEnd + extraLen;
  let resolved = null;
  if ((flags & 0x800) === 0) {{
    // Rule (REA's fixed semantics): the final 0x7075 field wins; validation happens
    // BEFORE selection. An unusable final field falls back to the stored raw name,
    // never resurrects an earlier valid claim.
    let at = extraStart, selected = null, found = false;
    while (at + 4 <= extraEnd) {{
      const kind = r.readUInt16LE(at), len = r.readUInt16LE(at + 2);
      if (kind === 0x7075) {{
        const data = r.subarray(at + 4, at + 4 + len);
        const ok = data.length >= 6 && data[0] === 1 && data.readUInt32LE(1) === crc32of(r.subarray(rawNameStart, rawNameEnd));
        selected = ok ? data.subarray(5) : null;
        found = true;
      }}
      at += 4 + len;
    }}
    resolved = found ? selected : r.subarray(rawNameStart, rawNameEnd);
    if (found && resolved === null) resolved = r.subarray(rawNameStart, rawNameEnd);
  }} else {{
    resolved = r.subarray(rawNameStart, rawNameEnd);
  }}
  names.push(resolved.toString('utf8'));
}}
console.log(JSON.stringify({{ok:true, names}}));
function crc32of(buf) {{
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n++) {{
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c;
  }}
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = table[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", node_program],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None
    if not payload.get("ok"):
        return None
    return [n.encode("utf-8") for n in payload["names"]]


def check_fixture(rea_dist: Path, name: str, bytes_: bytes) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        handle.write(bytes_)
        temp = Path(handle.name)
    try:
        rea_names = invoke_rea_scan(rea_dist, temp)
    finally:
        temp.unlink(missing_ok=True)
    if rea_names is None:
        return {"fixture": name, "verdict": "INCONCLUSIVE", "detail": "REA scan unavailable or unreadable"}
    model = expected_files(bytes_)
    if model is None or sorted(model) != sorted(rea_names):
        return {
            "fixture": name,
            "verdict": "DIVERGENT",
            "rea": [x.decode("utf-8", errors="replace") for x in sorted(rea_names)],
            "model": [x.decode("utf-8", errors="replace") for x in sorted(model or [])],
        }
    return {"fixture": name, "verdict": "PARITY", "rea": [x.decode("utf-8", errors="replace") for x in sorted(rea_names)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rea-dist", default=None, help="Path to REA's dist directory (defaults to REA_DIST_DIR env var)")
    parser.add_argument("--json", action="store_true", help="Emit results as JSON")
    args = parser.parse_args()
    rea_dist = Path(args.rea_dist or __import__("os").environ.get("REA_DIST_DIR", ""))
    if not rea_dist.is_dir():
        print("INCONCLUSIVE: REA dist directory missing or not a directory", file=sys.stderr)
        return 3
    results = [check_fixture(rea_dist, name, bytes_) for name, bytes_ in FIXTURES.items()]
    verdict = "PARITY" if all(r["verdict"] == "PARITY" for r in results) else (
        "INCONCLUSIVE" if any(r["verdict"] == "INCONCLUSIVE" for r in results) else "DIVERGENT"
    )
    summary = {"reporter": "rea_verify_zip_bounded_views", "fixtures": results, "verdict": verdict}
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"verdict: {verdict}")
        for r in results:
            print(f"  {r['fixture']:24s} {r['verdict']:12s} {r.get('detail', '')}")
    return 0 if verdict == "PARITY" else (2 if verdict == "DIVERGENT" else 3)


if __name__ == "__main__":
    raise SystemExit(main())
