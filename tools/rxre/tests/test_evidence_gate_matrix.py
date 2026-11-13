#!/usr/bin/env python3
"""EVIDENCE GATE MATRIX — hermetic: tmp artifacts + tmp evidence JSONs.
Cada mutación de la auditoría con resultado obligatorio. Sin DB ni repo."""
import sys, os, json, hashlib
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from rxre.core.evidence_integrity import accept_evidence, validate_evidence_path

def _artifact(tmp, content=b"binary-target-bytes-matrix"):
    p = Path(tmp) / "art.bin"
    if not p.exists():
        p.write_bytes(content)
    return p, hashlib.sha256(content).hexdigest()

def _evidence(tmp, sha, size, **overrides):
    d = {
        "e2e_id": "e2e_900",
        "artefacto_path": str(Path(tmp) / "art.bin"),
        "artefacto_size_bytes": size,
        "artefacto_hash_sha256": sha,
        "epistemic": "VALID",
        "procedencia": "tests-matrix",
    }
    d.update(overrides)
    p = Path(tmp) / "ev.json"
    p.write_text(json.dumps(d))
    return p

def test_valid_evidence_accepted(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size)
    v = validate_evidence_path(str(ev), str(art))
    assert v["ok"], v["errors"]
    a = accept_evidence(str(ev), str(art))
    assert a["status"] == "accepted"

def test_missing_hash_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, artefacto_hash_sha256="")
    assert validate_evidence_path(str(ev))["ok"] is False

def test_hash_format_invalid_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, artefacto_hash_sha256="deadbeef")
    assert validate_evidence_path(str(ev))["ok"] is False

def test_hash_mismatch_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, "f" * 64, art.stat().st_size)
    v = validate_evidence_path(str(ev))
    assert v["ok"] is False and any("hash_mismatch" in e for e in v["errors"])

def test_size_missing_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    d = json.loads(_evidence(tmp_path, sha, art.stat().st_size).read_text())
    d.pop("artefacto_size_bytes")
    p = Path(tmp_path) / "ev_nosize.json"; p.write_text(json.dumps(d))
    assert validate_evidence_path(str(p))["ok"] is False

def test_size_not_positive_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, artefacto_size_bytes=0)
    assert validate_evidence_path(str(ev))["ok"] is False

def test_size_mismatch_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size + 1)
    assert validate_evidence_path(str(ev))["ok"] is False

def test_empty_artifact_path_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, artefacto_path="")
    assert validate_evidence_path(str(ev))["ok"] is False

def test_procedencia_missing_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, procedencia="")
    assert validate_evidence_path(str(ev))["ok"] is False

def test_artifact_binding_mismatch_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    other = Path(tmp_path) / "other.bin"; other.write_bytes(b"otro-artefacto")
    ev = _evidence(tmp_path, sha, art.stat().st_size)  # ev describes art
    v = validate_evidence_path(str(ev), str(other))    # pero se pide otro target
    assert v["ok"] is False and any("evidence_target_mismatch" in e for e in v["errors"])

def test_artifact_missing_rejected(tmp_path):
    art, sha = _artifact(tmp_path)
    ev = _evidence(tmp_path, sha, art.stat().st_size, artefacto_path="/no/existe/este.bin")
    assert validate_evidence_path(str(ev))["ok"] is False
