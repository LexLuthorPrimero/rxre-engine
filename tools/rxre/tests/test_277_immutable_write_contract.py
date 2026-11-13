#!/usr/bin/env python3
"""RXRE-MISSION-277 — PRUEBAS AISLADAS DEL CONTRATO DE ESCRITURA INMIBLE (A–J)."""
import sys, os, json, sqlite3, hashlib, shutil, subprocess
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store
from rxre.contracts import row_hash_contract as rhc
from rxre.contracts import migration_scope_gate as gate
from rxre.contracts import immutable_write_contract as iwc
from rxre.core import e2e_manifest_producer as prod

DB_ISO = "/tmp/rxre_277_iso.sqlite3"
ART = "/home/lucas/Escritario/rxre/audit/strace/glxinfo_trace_20261019_005110.txt" if False else "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
ORIG = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
OUT = "/tmp/rxre_277_out/e2e_277.json"

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def setup():
    for suf in ("", "-wal", "-shm"):
        p = DB_ISO + suf
        if os.path.exists(p):
            os.remove(p)
    c = store.conectar(DB_ISO)
    for q in ["ALTER TABLE results ADD COLUMN verified_scope TEXT DEFAULT ''",
              "ALTER TABLE results ADD COLUMN scope_decision TEXT DEFAULT 'UNVERIFIED'",
              "ALTER TABLE operations ADD COLUMN declared_scope TEXT DEFAULT ''",
              "ALTER TABLE operations ADD COLUMN authorized_scope TEXT DEFAULT ''",
              "ALTER TABLE operations ADD COLUMN auth_decision TEXT DEFAULT 'UNAUTH'",
              "ALTER TABLE operations ADD COLUMN auth_actor TEXT DEFAULT ''",
              "ALTER TABLE operations ADD COLUMN auth_timestamp TEXT DEFAULT ''"]:
        try: c.execute(q); c.commit()
        except Exception: pass
    return c

def auth_ok():
    return {"decision": "AUTHORIZED", "actor": "lucas", "timestamp": "2026-10-21T12:00:00Z"}

def make_result(rid, op, scope, hashval="", timestamp="2026-10-21T12:00:00Z"):
    return {
        "result_id": rid, "operation_id": op, "type": "t", "value": "v", "source": "s",
        "file": ART, "line": 0, "scope": scope, "tool": "t", "tool_version": "1",
        "status": "ok", "raw_json": {"hash": hashval}, "timestamp": timestamp}

# A
def test_A():
    c = setup()
    v = gate.evaluar_insercion_scope("scope_277_ok", "scope_277_ok", auth_ok())
    assert v["decision"] == "ACCEPT", v
    req = {"op": "claim", "target": ART, "scope": "scope_277_ok", "scope_authorization": auth_ok(),
           "evidence_ids": ["res_277_a"]}
    env = {"status": "ok", "op": "claim", "results": [
        {"result_id": "res_277_a", "type": "strace", "value": "v", "source": "s",
         "location": {"file": ART, "line": 0}, "scope": "scope_277_ok", "tool": "t",
         "tool_version": "1", "status": "ok", "raw_json": {"hash": sha(ART)},
         "timestamp": "2026-10-21T12:00:00Z"}]}
    op_id = store.registrar(c, req, env, 0.0)
    row = c.execute("SELECT scope, row_hash FROM results WHERE result_id='res_277_a'").fetchone()
    op = c.execute("SELECT scope, request_json FROM operations WHERE operation_id=?", (op_id,)).fetchone()
    c.close()
    assert row[0] == "scope_277_ok" and row[1] and len(row[1]) == 64
    assert json.loads(op[1])["scope_authorization"]["actor"] == "lucas"
    print("[PASS-A] Inserción válida: scope+autorización persistidos, row_hash calculado en INSERT.")

# B
def test_B():
    for a in [None, {"decision": "PENDING", "actor": "lucas"},
              {"decision": "AUTHORIZED", "actor": "lucas"},
              {"decision": "AUTHORIZED", "actor": "otro", "timestamp": "t"}]:
        v = gate.evaluar_insercion_scope("scope_b", "scope_b", a)
        assert v["decision"] == "REJECT", str(a)
    print("[PASS-B] Rechazo sin autorización / decisión inválida / sin timestamp / actor distinto.")

# C
def test_C():
    v = gate.evaluar_insercion_scope("declared", "auth", auth_ok())
    assert v["decision"] == "CONFLICT", v
    print("[PASS-C] Divergencia declared != authorized -> CONFLICT.")

# D
def test_D():
    c = setup()
    req = {"op": "claim", "scope": "scope_277_d", "scope_authorization": auth_ok()}
    env = {"status": "ok", "op": "claim", "results": [make_result("res_277_d", "op_277_d", "scope_277_d", sha(ART))]}
    op = store.registrar(c, req, env, 0.0)
    st, val, msg = rhc.verificar_row_hash(c, "results", "result_id", "res_277_d")
    c.close()
    assert st == "MATCH", "%s %s" % (st, msg)
    # determinismo del canónico: misma representación -> mismo hash
    rep1 = iwc.representar_canonica_resultado({"result_id": "x", "value": "v"})
    rep2 = iwc.representar_canonica_resultado({"result_id": "x", "value": "v"})
    assert rep1 == rep2
    print("[PASS-D] Hash reproducible: recálculo == row_hash persistido (MATCH); canónico determinístico.")

# E
def test_E():
    scratch = "/tmp/rxre_277_scratch.sqlite3"
    if os.path.exists(scratch): os.remove(scratch)
    c = sqlite3.connect(scratch)
    c.execute("CREATE TABLE results (result_id TEXT PRIMARY KEY, operation_id TEXT, type TEXT,"
              " value TEXT, source TEXT, file TEXT, line INTEGER, scope TEXT, tool TEXT, tool_version TEXT,"
              " status TEXT, raw_json TEXT NOT NULL, timestamp TEXT NOT NULL, row_hash TEXT)")
    r = make_result("res_277_e", "op_277_e", "scope_277_e", sha(ART))
    campos = dict(r); campos["value"] = str(r["value"])[:4000]
    campos["raw_json"] = json.dumps(r, sort_keys=True, default=str)
    h = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (r["result_id"], r["operation_id"], r["type"], r["value"], r["source"], r["file"],
               r["line"], r["scope"], r["tool"], r["tool_version"], r["status"],
               json.dumps(r, sort_keys=True, default=str), r["timestamp"], h))
    c.commit()
    st_ok, _, _ = rhc.verificar_row_hash(c, "results", "result_id", "res_277_e")
    c.execute("UPDATE results SET status='alterado' WHERE result_id='res_277_e'")
    c.commit()
    st_bad, _, _ = rhc.verificar_row_hash(c, "results", "result_id", "res_277_e")
    c.close()
    assert st_ok == "MATCH" and st_bad == "MISMATCH"
    print("[PASS-E] Alteración cubierta invalida el hash (MATCH -> MISMATCH), BD sin triggers.")

# F
def test_F():
    stage = "/tmp/rxre_277_stage.sqlite3"
    shutil.copy(ORIG, stage)
    c = sqlite3.connect(stage)
    try:
        c.execute("UPDATE results SET status='x' WHERE result_id='res_real_001'")
        raise AssertionError("UPDATE no bloqueado")
    except sqlite3.IntegrityError as e:
        assert "APPEND_ONLY" in str(e)
    try:
        c.execute("DELETE FROM results WHERE result_id='res_real_001'")
        raise AssertionError("DELETE no bloqueado")
    except sqlite3.IntegrityError as e:
        assert "APPEND_ONLY" in str(e)
    trigs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
    assert "trg_results_no_update" in trigs and "trg_results_no_delete" in trigs
    c.close()
    print("[PASS-F] UPDATE/DELETE abortados por triggers; triggers intactos; no desactivados.")

# G
def test_G():
    c = setup()
    req = {"op": "claim", "scope": "scope_277_g", "scope_authorization": auth_ok()}
    env = {"status": "ok", "op": "claim", "results": [make_result("res_277_g", "op_277_g", "scope_277_g", sha(ART), "v1")]}
    store.registrar(c, req, env, 0.0)
    env2 = dict(env); env2["results"][0]["value"] = "v2"
    store.registrar(c, req, env2, 0.0)
    assert c.execute("SELECT COUNT(*) FROM results WHERE result_id='res_277_g'").fetchone()[0] == 1
    assert c.execute("SELECT value FROM results WHERE result_id='res_277_g'").fetchone()[0] == "v1"
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='collision'").fetchone()[0] >= 1
    # fallback
    c = setup()
    try:
        c.execute("BEGIN")
        c.execute("INSERT INTO operations(operation_id,request_json,response_json,timestamp) VALUES (?,?,?,?)",
                  ("op_277_fallida", "{}", "{}", "2026-10-21T12:00:00Z"))
        raise RuntimeError("fallo simulado")
    except RuntimeError:
        c.rollback()
    n = c.execute("SELECT COUNT(*) FROM operations WHERE operation_id='op_277_fallida'").fetchone()[0]
    c.close()
    assert n == 0
    print("[PASS-G] Append-only en el escritor (sin sobresripción); rollback deja 0 operaciones.")

# H
def test_H():
    c = setup()
    req = {"op": "claim", "target": ART, "scope": "scope_277_h", "scope_authorization": auth_ok()}
    env = {"status": "ok", "op": "claim", "results": [make_result("res_277_h", "op_277_h", "scope_277_h", sha(ART))]}
    op_id = store.registrar(c, req, env, 0.0)
    c.close()
    res = prod.generar_manifest_e2e(DB_ISO, op_id, "res_277_h", OUT, "e2e_277_h")
    mf = json.load(open(OUT))
    assert res["status"] == "WRITTEN" and mf["operation_id"] == op_id
    assert mf["result_id"] == "res_277_h" and mf["scope_decision"] == "AUTHORIZED"
    assert mf["verified_scope"] is None and mf["scope_autorizacion"]["autenticidad"] == "DOCUMENTED_AUTHORITY"
    print("[PASS-H] Vínculo explícito op<->result<->manifiesto; manifest WRITTEN con ids correlacionados.")

# I — hueco documentado del productor
def test_I():
    # I-a: hash incorrecto en forma plana -> REJECTED
    c = setup()
    req = {"op": "claim", "target": ART, "scope": "scope_277_i", "scope_authorization": auth_ok()}
    env = {"status": "ok", "op": "claim", "results": [
        {"result_id": "res_277_i", "type": "t", "value": "v", "source": "s",
         "location": {"file": ART, "line": 0}, "scope": "scope_277_i", "tool": "t",
         "tool_version": "1", "status": "ok", "hash": "deadbeef" * 8,   # plano, faluda
         "timestamp": "2026-10-21T12:00:00Z"}]}
    op_id = store.registrar(c, req, env, 0.0)
    c.close()
    r1 = prod.generar_manifest_e2e(DB_ISO, op_id, "res_277_i", "/tmp/rxre_277_out/e2e_277_badhash.json", "e2e_277_badhash")
    assert r1["status"] == "REJECTED", r1
    # I-b: hash anidado (formato que REALMENE escribe core/store.py) -> hueco: prod WRITTEN; contrato MISMATCH
    db_iso = setup()
    nested_payload = {"result_id": "res_277_anidado", "operation_id": "op_277_i", "type": "t", "value": "v",
                     "source": "s", "location": {"file": ART, "line": 0},
                     "scope": "scope_277_i", "tool": "t", "tool_version": "1", "status": "ok",
                     "raw_json": {"hash": "deadbeef" * 8}, "timestamp": "2026-10-21T12:00:00Z"}
    db_iso.execute("INSERT INTO results(result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("res_277_anidado", "op_277_i", "t", "v", "s", ART, 0, "scope_277_i", "t", "1", "ok",
                    json.dumps(nested_payload, sort_keys=True),
                    hashlib.sha256(json.dumps({"x":"v","result_id":"y"}, sort_keys=True).encode()).hexdigest()))
    db_iso.commit(); db_iso.close()
    r2 = prod.generar_manifest_e2e(DB_ISO, "op_277_i", "res_277_anidado", "/tmp/rxre_277_out/e2e_277_nested.json")
    ct = iwc.verificar_integridad_artefacto(nested_payload["raw_json"], ART)
    assert ct["status"] == "MISMATCH"           # contrato detecta; prod NO detecta -> hueco documento
    assert r2["status"] == "WRITTEN"            # por el hueco
    # I-c: id inexistente -> REJECTED
    assert prod.generar_manifest_e2e(DB_ISO, "op_no_existe", "res_277_i", "/tmp/rxre_277_out/e2e_277_noid.json")["status"] == "REJECTED"
    # I-d: vínculo roto (result de otra operación) -> REJECTED
    c = setup()
    env2 = {"status": "ok", "op": "claim", "results": [make_result("res_277_i2", "op_277_i", "scope_277_i", sha(ART))]}
    store.registrar(c, req, env2, 0.0); c.close()
    assert prod.generar_manifest_e2e(DB_ISO, op_id, "res_277_i2", "/tmp/rxre_277_out/e2e_277_broken.json")["status"] == "REJECTED"
    print("[PASS-I] Hash plano->REJECTED; hueco anidado->contrato MISMATCH/prod WRITTEN; id->REJECTED; vínculo->REJECTED.")

# J
def test_J():
    base = "/home/lucas/Escritorio/rxre"
    env = dict(os.environ); env["PYTHONPATH"] = base + "/tools"
    before = sha(ORIG)
    scripts = [("265", "tools/rxre/tests/test_265_caller_trust.py"),
               ("270", "tools/rxre/tests/test_270_scope_propagation.py"),
               ("272", "tools/rxre/tests/test_272_real_integration.py"),
               ("275", "tools/rxre/tests/test_275_migration_dryrun.py"),
               ("273", "/tmp/test_273_e2e_producer.py"),
               ("276", "/tmp/test_276_preoperational.py")]
    for nm, path in scripts:
        r = subprocess.run([sys.executable, path], cwd=base, capture_output=True, text=True, env=env)
        print("  %s: rc=%d" % (nm, r.returncode))
    after = sha(ORIG)
    assert before == after, "DB_OP alterada por las regresiones"
    import glob
    assert sum(1 for p in glob.glob(base + "/audit/evidence/e2e_*.json") if json.load(open(p)).get("scope")) == 0
    c = sqlite3.connect("file:%s?mode=ro" % ORIG, uri=True)
    assert c.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 3
    assert all(x[0] is None for x in c.execute("SELECT scope FROM results").fetchall())
    assert all(x[0] is None for x in c.execute("SELECT row_hash FROM results").fetchall())
    c.close()
    print("[PASS-J] Regresiones ejecutadas; DB_OP sin alterar; históricos preservados.")

if __name__ == "__main__":
    pruebas = [("A", test_A), ("B", test_B), ("C", test_C), ("D", test_D), ("E", test_E),
               ("F", test_F), ("G", test_G), ("H", test_H), ("I", test_I), ("J", test_J)]
    fallos = 0
    for e, fn in pruebas:
        try:
            fn()
        except Exception as exc:
            fallos += 1
            print("[FAIL-%s] %s: %s" % (e, fn.__name__, exc))
    print("\n=== 277 CONTRATO ESCRITURA INMIBLE: %d/%d PASS ===" % (len(pruebas) - fallos, len(pruebas)))
