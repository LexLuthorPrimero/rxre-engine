#!/usr/bin/env python3
"""REPLAY ADVERSARIAL MATRIX — hermetic: tmp sqlite DB + tmp artifacts.
No toca la DB privada del autor ni fixtures del repo. Fail-closed en cada ruta."""
import sys, os, json, hashlib
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import rxre.core.replay as replay_mod

def _make_db(tmp, rows):
    db = Path(tmp) / "rxre.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.execute("DROP TABLE IF EXISTS operations")
    conn.execute("CREATE TABLE operations (operation_id TEXT PRIMARY KEY, operacion TEXT, capability TEXT, request_json TEXT, response_json TEXT)")
    for op_id, capability, req, resp in rows:
        conn.execute("INSERT INTO operations VALUES (?,?,?,?,?)",
                     (op_id, "binary", capability, json.dumps(req), json.dumps(resp)))
    conn.commit(); conn.close()
    return db

def _artifact(tmp, content=b"binary-target-bytes"):
    p = Path(tmp) / "target.bin"
    if not p.exists():
        p.write_bytes(content)
    return p, hashlib.sha256(content).hexdigest()

class FakeBackend:
    """Sustituye ejecutar(): jamás depende de herramientas del sistema."""
    CALLS = []
    NEXT_RESULT = {"functions": 42, "sections": 7}
    @staticmethod
    def fake_execute(capability, params):
        FakeBackend.CALLS.append((capability, dict(params)))
        return {"status": "ok", "result": dict(FakeBackend.NEXT_RESULT)}

def _setup(monkeypatch, tmp_path, rows):
    db = _make_db(tmp_path, rows)
    art, sha = _artifact(tmp_path)
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    monkeypatch.setattr(replay_mod, "ejecutar", FakeBackend.fake_execute)
    FakeBackend.CALLS.clear()
    FakeBackend.NEXT_RESULT = {"functions": 42, "sections": 7}
    return art, sha

def test_unsupported_capability(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [("op_x", "fs.verify", {"target": "x"}, {})])
    res = replay_mod.replay_operacion("op_x")
    assert res["status"] == "unsupported_capability"
    assert res["reproducible"] is None
    assert FakeBackend.CALLS == []

def test_target_missing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [("op_y", "binary.inspect", {"target": ""}, {})])
    res = replay_mod.replay_operacion("op_y")
    assert res["status"] == "no_target"
    assert FakeBackend.CALLS == []

def test_artifact_not_found(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [("op_z", "binary.inspect", {"target": "/no/existe/este-artefacto-jamas.bin"}, {})])
    res = replay_mod.replay_operacion("op_z")
    assert res["status"] == "no_artefact"
    assert FakeBackend.CALLS == []

def test_identity_mismatch_fail_closed(monkeypatch, tmp_path):
    art, sha = _setup(monkeypatch, tmp_path, [
        ("op_m", "binary.inspect", {"target": None}, {"backend": {"tool_version": "fake"}, "artefacto_hash_sha256": "0" * 64})])
    # target real, hash registrado que NO coincide -> fail-closed, backend no corre
    req = {"target": str(art)}
    db = _make_db(tmp_path, [("op_m2", "binary.inspect", req, {"artefacto_hash_sha256": "0" * 64})])
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    res = replay_mod.replay_operacion("op_m2")
    assert res["status"] == "artefact_mismatch"
    assert FakeBackend.CALLS == [], "backend no debe ejecutarse con identidad distinta"

def test_no_recorded_identity_blocked(monkeypatch, tmp_path):
    art, sha = _setup(monkeypatch, tmp_path, [("op_n", "binary.inspect",
                                               {"target": None}, {"backend": {"tool_version": "fake"}})])
    db = _make_db(tmp_path, [("op_nr", "binary.inspect", {"target": str(art)}, {"backend": {"tool_version": "fake"}})])
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    # eliminar evidencia vinculada: ninguna existe aquí porque el artefacto es temporal
    res = replay_mod.replay_operacion("op_nr")
    assert res["status"] == "blocked_insufficient_identity"
    assert FakeBackend.CALLS == [], "sin identidad registrada no se ejecuta el backend"

def test_full_replay_equivalent(monkeypatch, tmp_path):
    art, sha = _setup(monkeypatch, tmp_path, [])
    canned = {"functions": 42, "sections": 7}
    db = _make_db(tmp_path, [("op_ok", "binary.inspect",
                              {"target": str(art)},
                              {"artefacto_hash_sha256": sha, "backend": {"tool_version": "fake-backend 1.0"}, "result": canned})])
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    res = replay_mod.replay_operacion("op_ok")
    assert res["status"] == "replayed"
    assert res["reproducible"] is True
    assert res["replay_result"]["equivalence"]["outcome"] == "EQUIVALENT"
    assert "reproducible_structural" not in res["replay_result"]["differences"]

def test_result_divergent_reports(monkeypatch, tmp_path):
    art, sha = _setup(monkeypatch, tmp_path, [])
    canned_orig = {"functions": 42, "sections": 7}
    FakeBackend.NEXT_RESULT = {"functions": 99, "sections": 7}
    db = _make_db(tmp_path, [("op_dv", "binary.inspect",
                              {"target": str(art)},
                              {"artefacto_hash_sha256": sha, "backend": {"tool_version": "fake"}, "result": canned_orig})])
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    res = replay_mod.replay_operacion("op_dv")
    assert res["replay_result"]["equivalence"]["outcome"] == "DIVERGENT"
    assert res["reproducible"] is False
    assert "result_fields_diverged" in res["replay_result"]["differences"]

def test_operation_not_found(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [])
    res = replay_mod.replay_operacion("op_inexistente")
    assert res["status"] == "not_found"

def test_db_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(replay_mod, "DB_PATH", Path(tmp_path) / "no-hay-db.sqlite3")
    res = replay_mod.replay_operacion("op_x")
    assert res["status"] == "no_db"


def test_verify_reinvestigation_requires_explicit_condition(monkeypatch, tmp_path):
    """ADVERSARIAL: clasificación declarada por el resultado NO basta para RESOLVED."""
    import rxre.core.replay as replay_mod2
    art, sha = _artifact(tmp_path)
    ev = Path(tmp_path) / "ev.json"
    ev.write_text(json.dumps({"e2e_id": "e2e_901", "artefacto_path": str(art),
                              "artefacto_size_bytes": art.stat().st_size,
                              "artefacto_hash_sha256": sha,
                              "epistemic": "VALID", "procedencia": "matrix"}))
    plan = {"op_id": "op_m1", "evidence_path": str(ev),
            "plan": [{"action": "conservar", "condition": "hash estable"}]}
    # Resultado con classification VALID pero SIN condition_satisfied -> UNRESOLVED
    res = replay_mod2.verify_reinvestigation(plan, {"op_id": "op_m1", "classification": "VALID", "evidence_path": str(ev)})
    assert res["verification_status"] == "UNRESOLVED"
    # Con condition_satisfied pero SIN dependencias verificadas -> UNRESOLVED
    res = replay_mod2.verify_reinvestigation(plan, {"op_id": "op_m1", "classification": "VALID",
                                                    "condition_satisfied": True,
                                                    "evidence_path": str(ev)})
    assert res["verification_status"] == "UNRESOLVED"
    # Condición + dependencias verificadas + evidencia íntegra vinculada -> RESOLVED
    res = replay_mod2.verify_reinvestigation(plan, {"op_id": "op_m1", "classification": "VALID",
                                                    "condition_satisfied": True,
                                                    "dependencias_verificadas": True,
                                                    "artefacto_reconstruido": str(art),
                                                    "evidence_path": str(ev)})
    assert res["verification_status"] == "RESOLVED"

def test_partial_never_reproducible(monkeypatch, tmp_path):
    """ADVERSARIAL: PARTIAL en el objeto equivalence NUNCA produce reproducible=True."""
    art, sha = _setup(monkeypatch, tmp_path, [])
    db = _make_db(tmp_path, [("op_p", "binary.inspect",
                              {"target": str(art)},
                              {"artefacto_hash_sha256": sha, "backend": {"tool_version": "fake"},
                               "result": {"functions": 42, "sections": 7, "extra_orig": "only-original"}})])
    monkeypatch.setattr(replay_mod, "DB_PATH", db)
    # El fake devuelve exactamente {42,7} sin extra_orig -> PARTAL: campos faltantes
    res = replay_mod.replay_operacion("op_p")
    assert res["replay_result"]["equivalence"]["outcome"] == "PARTIAL"
    assert res["reproducible"] is False
