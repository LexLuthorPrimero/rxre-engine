#!/usr/bin/env python3
"""Bounded parity: does a bounded implementation answer exactly what the production one
does, on a caller-declared probe corpus?

For each probe (one file in `probes_dir`), this runs `bounded` and `reference` as
subprocesses with the probe bytes as stdin. Each pair gets one verdict:

- PARITY       — both answered and agree under `verdict`.
- DIVERGENT    — both answered and disagree; reported with the probe's path.
- INCONCLUSIVE — bounded did not give a deterministic answer (error, timeout, or
                 inconsistent repeat runs) or the reference did not answer.

Anything that cannot be compared is INCONCLUSIVE, never a silent pass or a
silently skipped probe. An empty corpus is rejected fail-closed.

Scope stated by the verdict line itself: this tool admits a match on the given
probes and the given comparison only. It is not evidence about inputs outside
the corpus, and it is not independence, authenticity or security of anything.

Contract (JSON):
  {
    "bounded": ["argv", ...],       # runs with the probe on stdin
    "reference": ["argv", ...],     # same protocol
    "probes_dir": ".",              # one file == one probe (sorted)
    "verdict": "stdout-equal"       # or "json-field:NAME" | "exit-equal"
    "timeout_seconds": 10
  }

Usage: python3 bounded_parity.py contract.json
Exit: 0 all PARITY · 2 any DIVERGENT · 3 any INCONCLUSIVE or an invalid contract.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERDICT_KINDS = ("stdout-equal", "exit-equal")


class ContractError(Exception):
    pass


@dataclass(frozen=True)
class Contract:
    bounded: list[str]
    reference: list[str]
    probes_dir: Path
    verdict: str
    json_field: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class PairResult:
    probe: str
    verdict: str  # PARITY | DIVERGENT | INCONCLUSIVE
    detail: str


def load_contract(path: Path) -> Contract:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"contract unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError("contract must be a JSON object")
    for key in ("bounded", "reference", "probes_dir"):
        if key not in raw:
            raise ContractError(f"contract missing {key!r}")
    for key in ("bounded", "reference"):
        if (
            not isinstance(raw[key], list)
            or not raw[key]
            or not all(isinstance(arg, str) and arg for arg in raw[key])
        ):
            raise ContractError(f"{key} must be a nonempty argv list")
    probes_dir = Path(raw["probes_dir"])
    if not probes_dir.is_dir():
        raise ContractError(f"probes_dir is not a directory: {probes_dir}")
    verdict = raw.get("verdict", "stdout-equal")
    json_field = None
    if isinstance(verdict, str) and verdict.startswith("json-field:"):
        json_field = verdict[len("json-field:") :]
        if not json_field:
            raise ContractError("json-field verdict needs a field name")
        verdict = "json-field"
    if verdict not in (*VERDICT_KINDS, "json-field"):
        raise ContractError(f"unsupported verdict: {raw.get('verdict')!r}")
    timeout_seconds = raw.get("timeout_seconds", 10)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ContractError("timeout_seconds must be a positive integer")
    return Contract(
        bounded=list(raw["bounded"]),
        reference=list(raw["reference"]),
        probes_dir=probes_dir,
        verdict=verdict,
        json_field=json_field,
        timeout_seconds=timeout_seconds,
    )


def run(command: list[str], payload: bytes, timeout_seconds: int):
    return subprocess.run(
        command,
        input=payload,
        capture_output=True,
        timeout=timeout_seconds,
    )


def probe_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file())


def extract_field(payload: bytes, field: str):
    value = json.loads(payload.decode("utf-8", errors="strict"))
    if not isinstance(value, dict) or field not in value:
        raise ValueError(f"missing JSON field {field!r}")
    return value[field]


def compare(contract: Contract, bounded_out, reference_out) -> str:
    if contract.verdict == "exit-equal":
        return "equal" if bounded_out.returncode == reference_out.returncode else "different"
    if contract.verdict == "stdout-equal":
        return "equal" if bounded_out.stdout == reference_out.stdout else "different"
    assert contract.json_field is not None
    try:
        expected = extract_field(reference_out.stdout, contract.json_field)
        actual = extract_field(bounded_out.stdout, contract.json_field)
    except (ValueError, json.JSONDecodeError):
        return "uncomparable"
    return "equal" if expected == actual else "different"


def check_pair(contract: Contract, probe: Path) -> PairResult:
    payload = probe.read_bytes()
    try:
        first = run(contract.bounded, payload, contract.timeout_seconds)
        second = run(contract.bounded, payload, contract.timeout_seconds)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return PairResult(probe.name, "INCONCLUSIVE", f"bounded did not run: {exc}")
    if (first.stdout, first.stderr, first.returncode) != (
        second.stdout,
        second.stderr,
        second.returncode,
    ):
        return PairResult(probe.name, "INCONCLUSIVE", "bounded is not deterministic")
    if first.returncode != 0:
        return PairResult(probe.name, "INCONCLUSIVE", f"bounded exited {first.returncode}")
    try:
        reference = run(contract.reference, payload, contract.timeout_seconds)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return PairResult(probe.name, "INCONCLUSIVE", f"reference did not run: {exc}")
    if reference.returncode != 0:
        return PairResult(probe.name, "INCONCLUSIVE", f"reference exited {reference.returncode}")
    outcome = compare(contract, first, reference)
    if outcome == "uncomparable":
        return PairResult(probe.name, "INCONCLUSIVE", "bounded or reference output is not comparable")
    if outcome == "different":
        return PairResult(probe.name, "DIVERGENT", f"bounded differs from reference on {probe.name}")
    return PairResult(probe.name, "PARITY", "agreed")


def evaluate(contract_path: Path) -> dict:
    contract = load_contract(contract_path)
    probes = probe_files(contract.probes_dir)
    if not probes:
        raise ContractError(f"no probe files in {contract.probes_dir}")
    contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    results = [check_pair(contract, probe) for probe in probes]
    counts = {
        kind: sum(1 for r in results if r.verdict == kind)
        for kind in ("PARITY", "DIVERGENT", "INCONCLUSIVE")
    }
    return {
        "contract_sha256": contract_sha,
        "verdict_kind": (
            contract.verdict
            if contract.json_field is None
            else f"json-field:{contract.json_field}"
        ),
        "probes": len(probes),
        "counts": counts,
        "results": [
            {"probe": r.probe, "verdict": r.verdict, "detail": r.detail} for r in results
        ],
        "claim": "bounded parity on this corpus and comparison only; nothing else is admitted",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: bounded_parity.py contract.json", file=sys.stderr)
        return 3
    contract_path = Path(argv[1])
    try:
        report = evaluate(contract_path)
    except ContractError as exc:
        print(f"invalid contract: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["counts"]["DIVERGENT"]:
        print("DIVERGENT", file=sys.stderr)
        return 2
    if report["counts"]["INCONCLUSIVE"]:
        print("INCONCLUSIVE", file=sys.stderr)
        return 3
    print(f"PARITY on {report['probes']} probes (this corpus only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
