#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from rxre.parity import bounded_parity

CAT = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"]
EMPTY = [sys.executable, "-c", "import sys; sys.stdin.buffer.read()"]
CRASH = [sys.executable, "-c", "import sys; sys.exit(3)"]
HEAD4 = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()[:4])"]


def contract(tmp_path, bounded, verdict="stdout-equal", reference=CAT):
    probes = tmp_path / "probes"
    probes.mkdir(exist_ok=True)
    (probes / "a.bin").write_bytes(b"hello\n")
    (probes / "b.bin").write_bytes(b"hi\n")
    (probes / "empty.bin").write_bytes(b"")
    cfg = tmp_path / "contract.json"
    cfg.write_text(json.dumps({
        "bounded": bounded,
        "reference": reference,
        "probes_dir": str(probes),
        "verdict": verdict,
        "timeout_seconds": 15,
    }), encoding="utf-8")
    return cfg


def run_cli(cfg):
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "parity" / "bounded_parity.py"), str(cfg)],
        capture_output=True,
    )
    return completed


def test_all_parity(tmp_path):
    cfg = contract(tmp_path, CAT)
    report = bounded_parity.evaluate(cfg)
    assert report["counts"] == {"PARITY": 3, "DIVERGENT": 0, "INCONCLUSIVE": 0}


def test_divergence_is_reported_with_the_probe(tmp_path):
    cfg = contract(tmp_path, HEAD4)
    report = bounded_parity.evaluate(cfg)
    assert report["counts"]["DIVERGENT"] == 1
    assert report["counts"]["PARITY"] == 2
    assert [r for r in report["results"] if r["probe"] == "a.bin"][0]["verdict"] == "DIVERGENT"


def test_bounded_crash_is_inconclusive_never_a_pass(tmp_path):
    cfg = contract(tmp_path, CRASH)
    report = bounded_parity.evaluate(cfg)
    assert report["counts"]["INCONCLUSIVE"] == 3
    assert report["counts"]["DIVERGENT"] == 0


def test_bounded_nondeterminism_is_inconclusive(tmp_path):
    counter = tmp_path / "counter"
    noisy = [sys.executable, "-c", (
        "import sys, os\n"
        f"path = {str(counter)!r}\n"
        "n = int(open(path).read() or 0) if os.path.exists(path) else 0\n"
        "open(path, 'w').write(str(n + 1))\n"
        "print(n)\n"
    )]
    probes = tmp_path / "probes"
    probes.mkdir(exist_ok=True)
    (probes / "a.bin").write_bytes(b"x\n")
    cfg = tmp_path / "contract.json"
    cfg.write_text(json.dumps({
        "bounded": noisy,
        "reference": CAT,
        "probes_dir": str(probes),
        "verdict": "stdout-equal",
        "timeout_seconds": 15,
    }), encoding="utf-8")
    report = bounded_parity.evaluate(cfg)
    assert report["counts"]["INCONCLUSIVE"] == 1


def test_empty_corpus_fails_closed(tmp_path):
    (tmp_path / "probes").mkdir()
    cfg = tmp_path / "contract.json"
    cfg.write_text(json.dumps({
        "bounded": CAT,
        "reference": CAT,
        "probes_dir": str(tmp_path / "probes"),
        "verdict": "stdout-equal",
        "timeout_seconds": 5,
    }), encoding="utf-8")
    try:
        bounded_parity.evaluate(cfg)
    except bounded_parity.ContractError:
        return
    raise AssertionError("empty corpus must not evaluate")


def test_cli_exit_codes(tmp_path):
    assert run_cli(contract(tmp_path, CAT)).returncode == 0
    assert run_cli(contract(tmp_path, HEAD4)).returncode == 2
    assert run_cli(contract(tmp_path, CRASH)).returncode == 3
