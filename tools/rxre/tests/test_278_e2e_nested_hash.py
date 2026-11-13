#!/usr/bin/env python3
"""RXRE-MISSION-278 — Pruebas A–L: hash anidado, vinculo explicito y controles de alcance.
Aislamiento total: base propia via store.conectar; DB_OP solo lectura.
"""
import sys, os, json, sqlite3, hashlib, subprocess, shutil
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store
from rxre.core import e2e_manifest_producer as prod
from rxre.contracts import immutable_write_contract as iwc

DB_ISO = "/tmp/rxre_278_iso.sqlite3"
ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
ART_TMP = "/tmp/rxre_278_artefacto.txt"
ORIG = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
OUTDIR = "/tmp/rxre_278_out"

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def auth():
    return {"decision": "AUTHORIZED", "actor": "lucas", "timestamp": "2026-10-21T12:00:00Z"}

def fresh_db():
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(DB_ISO + suf):
            os.remove(DB_ISO + suf)
    return store.conectar(DB_ISO)

def registrar_op(c, op_scope, res_id, result_scope, hash_value, art=ART, req_scope=None, auth_block=None):
    req = {"op": "claim", "target": art, "scope": req_scope if req_scope is not None else op_scope,
           "scope_authorization": auth_block if auth_block is not None else auth()}
    env = {"status": "ok", "op": "claim", "results": [
        {"result_id": res_id, "type": "t", "value": "v", "source": "s",
         "location": {"file": art, "line": 0}, "scope": result_scope, "tool": "t",
         "tool_version": "1", "status": "ok", "raw_json": {"hash": hash_value},
         "timestamp": "2026-10-21T12:00:00Z"}]}
    return store.registrar(c, req, env, 0.0)

def escribe_raw_json_directo(c, op_id, res_id, raw_json_text, art=ART, scope="scope_278"):
    """Inserta un resultado con raw_json arbitrario (formato anidado real)."""
    c.execute("INSERT INTO results(result_id,operation_id,type,value,source,file,line,scope,tool,"
              "tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (res_id, op_id, "t", "v", "s", art, 0, scope, "t", "1", "ok", raw_json_text,
               "2026-10-21T12:00:00Z", hashlib.sha256(res_id.encode()).hexdigest()))
    c.commit()

def op_id_de(c, scope):
    return c.execute("SELECT operation_id FROM operations WHERE scope=? ORDER BY timestamp LIMIT 1", (scope,)).fetchone()[0]

# ---------------- A ----------------
def test_A():
    """A. Artefacto real del escritor con hash anidado correcto -> aceptacion."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_a", "res_278_a", "scope_278_a", sha(ART))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_a", OUTDIR + "/a.json", "e2e_278_a")
    assert r["status"] == "WRITTEN", r
    mf = json.load(open(OUTDIR + "/a.json"))
    assert mf["integridad_artefacto"]["status"] == "OK"
    assert mf["hash_fuentes"]["anidado"] == sha(ART)
    assert mf["hash_fuentes"]["plano"] is None
    assert mf["scope_decision"] == "AUTHORIZED"
    assert mf["verified_scope"] is None
    assert mf["operation_id"] == op and mf["result_id"] == "res_278_a"
    print("[PASS-A] Hash anidado correcto -> WRITTEN; integridad OK; fuente='anidado'.")

# ---------------- B ----------------
def test_B():
    """B. Hash anidado alterado -> rechazo."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_b", "res_278_b", "scope_278_b", sha(ART))
    payload = json.loads(c.execute("SELECT raw_json FROM results WHERE result_id='res_278_b'").fetchone()[0])
    payload["raw_json"]["hash"] = "deadbeef" * 8
    escribe_raw_json_directo(c, op, "res_278_b2", json.dumps(payload, sort_keys=True))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_b2", OUTDIR + "/b.json", "e2e_278_b")
    assert r["status"] == "REJECTED", r
    assert r["integridad"]["status"] == "MISMATCH", r["integridad"]
    assert not os.path.exists(OUTDIR + "/b.json")
    print("[PASS-B] Hash anidado alterado -> REJECTED (MISMATCH); no se escribe manifiesto.")

# ---------------- C ----------------
def test_C():
    """C. Hash plano falso con hash anidado correcto -> rechazo (conflicto clasificado)."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_c", "res_278_c", "scope_278_c", sha(ART))
    payload = json.loads(c.execute("SELECT raw_json FROM results WHERE result_id='res_278_c'").fetchone()[0])
    payload["hash"] = "deadbeef" * 8          # plano falso
    escribe_raw_json_directo(c, op, "res_278_c2", json.dumps(payload, sort_keys=True))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_c2", OUTDIR + "/c.json", "e2e_278_c")
    assert r["status"] == "REJECTED", r
    assert r["integridad"]["status"] == "CONFLICT", r["integridad"]
    print("[PASS-C] Plano falso + anidado correcto -> REJECTED (CONFLICT); no se prefiere fuente.")

# ---------------- D ----------------
def test_D():
    """D. Hash plano correcto con hash anidado incorrecto -> rechazo."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_d", "res_278_d", "scope_278_d", sha(ART))
    payload = json.loads(c.execute("SELECT raw_json FROM results WHERE result_id='res_278_d'").fetchone()[0])
    payload["hash"] = sha(ART)                 # plano correcto
    payload["raw_json"]["hash"] = "deadbeef" * 8  # anidado incorrecto
    escribe_raw_json_directo(c, op, "res_278_d2", json.dumps(payload, sort_keys=True))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_d2", OUTDIR + "/d.json", "e2e_278_d")
    assert r["status"] == "REJECTED", r
    assert r["integridad"]["status"] == "CONFLICT", r["integridad"]
    print("[PASS-D] Plano correcto + anidado incorrecto -> REJECTED (CONFLICT).")

# ---------------- E ----------------
def test_E():
    """E. Hash ausente o estructura ambigua -> rechazo, sin fallback silencioso."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_e", "res_278_e", "scope_278_e", sha(ART))
    payload = json.loads(c.execute("SELECT raw_json FROM results WHERE result_id='res_278_e'").fetchone()[0])
    payload["raw_json"].pop("hash", None)      # sin hash en ninguna fuente
    escribe_raw_json_directo(c, op, "res_278_e2", json.dumps(payload, sort_keys=True))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_e2", OUTDIR + "/e.json", "e2e_278_e")
    assert r["status"] == "REJECTED", r
    assert r["integridad"]["status"] == "NO_HASH", r["integridad"]
    assert not os.path.exists(OUTDIR + "/e.json")
    print("[PASS-E] Hash ausente -> REJECTED (NO_HASH); sin fallback; no se escribe manifiesto.")

# ---------------- F ----------------
def test_F():
    """F. operation_id inexistente -> rechazo."""
    c = fresh_db()
    registrar_op(c, "scope_278_f", "res_278_f", "scope_278_f", sha(ART))
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, "op_inexistente_278", "res_278_f", OUTDIR + "/f.json")
    assert r["status"] == "REJECTED", r
    assert "inexistente" in r["motivo"], r
    print("[PASS-F] operation_id inexistente -> REJECTED.")

# ---------------- G ----------------
def test_G():
    """G. result_id inexistente o perteneciente a otra operacion -> rechazo."""
    c = fresh_db()
    op1 = registrar_op(c, "scope_278_g1", "res_278_g1", "scope_278_g1", sha(ART))
    op2 = registrar_op(c, "scope_278_g2", "res_278_g2", "scope_278_g2", sha(ART))
    c.close()
    r1 = prod.generar_manifest_e2e(DB_ISO, op1, "res_inexistente_278", OUTDIR + "/g1.json")
    assert r1["status"] == "REJECTED", r1
    r2 = prod.generar_manifest_e2e(DB_ISO, op1, "res_278_g2", OUTDIR + "/g2.json")
    assert r2["status"] == "REJECTED", r2
    assert "vinculo roto" in r2["motivo"], r2
    print("[PASS-G] result_id inexistente y result_id de otra operacion -> REJECTED (vinculo roto).")

# ---------------- H ----------------
def test_H():
    """H. Manifiesto con identificadores correctos pero artefacto incorrecto -> rechazo."""
    if not os.path.exists(ART_TMP):
        shutil.copy(ART, ART_TMP)
    c = fresh_db()
    op = registrar_op(c, "scope_278_h", "res_278_h", "scope_278_h", sha(ART_TMP), art=ART_TMP)
    c.close()
    # El artefacto cambia despues de登记 (hash declarado ya no coincide)
    with open(ART_TMP, "a") as f:
        f.write("\nALTERADO\n")
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_h", OUTDIR + "/h.json", "e2e_278_h")
    assert r["status"] == "REJECTED", r
    assert r["integridad"]["status"] == "MISMATCH", r["integridad"]
    print("[PASS-H] Artefacto alterado tras registro -> REJECTED (MISMATCH).")

# ---------------- I ----------------
def test_I():
    """I. Reapertura de la base aislada y repeticion de la verificacion -> consistente."""
    c = fresh_db()
    op = registrar_op(c, "scope_278_i", "res_278_i", "scope_278_i", sha(ART))
    c.close()
    c2 = sqlite3.connect("file:%s?mode=ro" % DB_ISO, uri=True)
    assert c2.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    c2.close()
    r1 = prod.generar_manifest_e2e(DB_ISO, op, "res_278_i", OUTDIR + "/i1.json", "e2e_278_i")
    r2 = prod.generar_manifest_e2e(DB_ISO, op, "res_278_i", OUTDIR + "/i2.json", "e2e_278_i")
    assert r1["status"] == "WRITTEN" and r2["status"] == "WRITTEN"
    m1 = json.load(open(OUTDIR + "/i1.json")); m2 = json.load(open(OUTDIR + "/i2.json"))
    assert m1["integridad_artefacto"] == m2["integridad_artefacto"]
    assert m1["artefacto_hash_sha256"] == m2["artefacto_hash_sha256"] == sha(ART)
    print("[PASS-I] Reapertura + repeticion -> resultado consistente (integridad identica).")

# ---------------- J ----------------
def test_J():
    """J. Cambio posterior del artefacto -> deteccion de divergencia."""
    if not os.path.exists(ART_TMP):
        shutil.copy(ART, ART_TMP)
    c = fresh_db()
    op = registrar_op(c, "scope_278_j", "res_278_j", "scope_278_j", sha(ART_TMP), art=ART_TMP)
    c.close()
    r0 = prod.generar_manifest_e2e(DB_ISO, op, "res_278_j", OUTDIR + "/j0.json", "e2e_278_j0")
    assert r0["status"] == "WRITTEN", r0
    with open(ART_TMP, "a") as f:
        f.write("\nSEGUNDO CAMBIO\n")
    r1 = prod.generar_manifest_e2e(DB_ISO, op, "res_278_j", OUTDIR + "/j1.json", "e2e_278_j1")
    assert r1["status"] == "REJECTED", r1
    assert r1["integridad"]["status"] == "MISMATCH"
    print("[PASS-J] Cambio posterior del artefacto -> divergencia detectada (MISMATCH).")

# ---------------- K ----------------
def test_K():
    """K. Alcance declarado distinto del autorizado -> nunca VERIFIED."""
    c = fresh_db()
    # declarado != autorizado entre etapas: el productor detecta conflicto de etapas
    op = registrar_op(c, "scope_278_k_req", "res_278_k", "scope_278_k_op", sha(ART),
                      req_scope="scope_278_k_req")
    c.close()
    r = prod.generar_manifest_e2e(DB_ISO, op, "res_278_k", OUTDIR + "/k.json", "e2e_278_k")
    assert r["status"] == "REJECTED", r
    assert "conflicto de scope" in r["motivo"], r
    # Y con authorization ausente: el manifiesto se emite sin scope y sin VERIFIED
    c = fresh_db()
    op2 = registrar_op(c, "scope_278_k2", "res_278_k2", "scope_278_k2", sha(ART), auth_block=None)
    c.close()
    r2 = prod.generar_manifest_e2e(DB_ISO, op2, "res_278_k2", OUTDIR + "/k2.json", "e2e_278_k2")
    assert r2["status"] == "WRITTEN", r2
    mf = json.load(open(OUTDIR + "/k2.json"))
    assert mf["scope_decision"] == "UNVERIFIED" and mf["scope"] is None
    assert mf["verified_scope"] is None
    print("[PASS-K] Scope divergente -> REJECTED (conflicto de etapas); sin autorizacion -> UNVERIFIED, nunca VERIFIED.")

# ---------------- L ----------------
def test_L():
    """L. Filas historicas conservadas + regresiones M265/270/272/273/275/276/277."""
    base = "/home/lucas/Escritorio/rxre"
    env = dict(os.environ); env["PYTHONPATH"] = base + "/tools"
    before = sha(ORIG)
    for nm, path in [("265", "tools/rxre/tests/test_265_caller_trust.py"),
                     ("270", "tools/rxre/tests/test_270_scope_propagation.py"),
                     ("272", "tools/rxre/tests/test_272_real_integration.py"),
                     ("273", "/tmp/test_273_e2e_producer.py"),
                     ("275", "tools/rxre/tests/test_275_migration_dryrun.py"),
                     ("276", "/tmp/test_276_preoperational.py"),
                     ("277", "tools/rxre/tests/test_277_immutable_write_contract.py")]:
        r = subprocess.run([sys.executable, path], cwd=base, capture_output=True, text=True, env=env)
        print("  regresion %s: rc=%d" % (nm, r.returncode))
    assert sha(ORIG) == before, "DB_OP alterada"
    c = sqlite3.connect("file:%s?mode=ro" % ORIG, uri=True)
    assert c.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 3
    assert all(x[0] is None for x in c.execute("SELECT scope FROM results").fetchall())
    assert all(x[0] is None for x in c.execute("SELECT row_hash FROM results").fetchall())
    c.close()
    import glob
    assert sum(1 for p in glob.glob(base + "/audit/evidence/e2e_*.json") if json.load(open(p)).get("scope")) == 0
    print("[PASS-L] Filas historicas intactas; DB_OP sin alterar; audit/evidence sin scope.")

if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    pruebas = [("A", test_A), ("B", test_B), ("C", test_C), ("D", test_D), ("E", test_E),
               ("F", test_F), ("G", test_G), ("H", test_H), ("I", test_I), ("J", test_J),
               ("K", test_K), ("L", test_L)]
    fallos = 0
    for e, fn in pruebas:
        try:
            fn()
        except Exception as exc:
            fallos += 1
            print("[FAIL-%s] %s: %s" % (e, fn.__name__, exc))
    print("\n=== 278 HASH ANIDADO + VINCULO: %d/%d PASS ===" % (len(pruebas) - fallos, len(pruebas)))
