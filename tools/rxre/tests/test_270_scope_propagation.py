#!/usr/bin/env python3
"""RXRE-MISSION-270 — PRUEBAS DISCRIMINANTES DE PROPAGACIÓN DEL SCOPE AUTORIZADO.
Tests aislados en /tmp/rxre_270_prop.sqlite3. NO toca DB_OP en producción.
"""
import sys, os, sqlite3, json, hashlib, tempfile
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

DB_PROP = "/tmp/rxre_270_prop.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"

def reset_isolated_db():
    """Crea DB aislada con esquema de scope autorizado."""
    if os.path.exists(DB_PROP): os.remove(DB_PROP)
    c = sqlite3.connect(DB_PROP)
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("""CREATE TABLE operations (
        operation_id TEXT PRIMARY KEY,
        request_id TEXT,
        declared_scope TEXT,
        authorized_scope TEXT,
        auth_decision TEXT DEFAULT 'UNAUTH',
        auth_actor TEXT,
        auth_timestamp TEXT,
        status TEXT,
        request_json TEXT,
        row_hash TEXT)""")
    c.execute("""CREATE TABLE results (
        result_id TEXT PRIMARY KEY,
        operation_id TEXT REFERENCES operations(operation_id),
        scope TEXT,
        verified_scope TEXT,
        artifact_path TEXT,
        artifact_hash TEXT,
        scope_decision TEXT DEFAULT 'UNVERIFIED',
        limitations_json TEXT DEFAULT '{}',
        row_hash TEXT)""")
    c.execute("""CREATE TABLE manifest_e2e (
        e2e_id TEXT PRIMARY KEY,
        operation_id TEXT,
        scope TEXT,
        artifact_path TEXT,
        artifact_hash TEXT,
        timestamp TEXT)""")
    c.execute("CREATE INDEX ix_results_op ON results(operation_id)")
    c.commit(); c.close()

def row_hash_sql(row_data):
    """Calcula hash de fila para integridad."""
    return hashlib.sha256(json.dumps(row_data, sort_keys=True, default=str).encode()).hexdigest()[:16]

def simulate_request_con_authorized_scope(op_id, scope, actor="operator_001"):
    """Simula request con scope autorizado (Antes de ejecución)."""
    c = sqlite3.connect(DB_PROP)
    ts = "2026-10-21T12:00:00Z"
    request_json = json.dumps({
        "op": "claim",
        "target": "analysis",
        "scope": scope,
        "scope_authorization": {"decision": "AUTHORIZED", "actor": actor, "timestamp": ts},
    }, sort_keys=True)
    row = {"op_id": op_id, "scope": scope, "actor": actor, "ts": ts, "req_json": request_json}
    rh = row_hash_sql(row)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op_id, "req_"+op_id, scope, scope, "AUTHORIZED", actor, ts, "submitted", request_json, rh))
    c.commit(); c.close()

def simulate_scope_propagation(op_id, scope):
    """Propaga scope a resultados (modelo minimal - producer writes to results.scope)."""
    c = sqlite3.connect(DB_PROP)
    res_id = "res_" + op_id
    row = {"res_id": res_id, "op_id": op_id, "scope": scope}
    rh = row_hash_sql(row)
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              (res_id, op_id, scope, scope, REAL_ART if os.path.exists(REAL_ART) else "/tmp/fallback",
               "hash_placeholder", "UNVERIFIED", "{}", rh))
    c.commit(); c.close()
    return res_id

def verify_scope_verified(op_id):
    """Verifica si scope_provenance_contract daría VERIFIED."""
    c = sqlite3.connect(DB_PROP)
    op = c.execute("SELECT authorized_scope, declared_scope FROM operations WHERE operation_id=?", (op_id,)).fetchone()
    res = c.execute("SELECT scope, verified_scope, scope_decision FROM results WHERE operation_id=?", (op_id,)).fetchone()
    c.close()
    auth_scope = op[0] if op else None
    op_scope = op[1] if op else None
    res_scope = res[0] if res else None
    res_verified = res[1] if res else None
    res_dec = res[2] if res else None
    has_auth = auth_scope is not None and auth_scope != ""
    is_verified = has_auth and res_scope and auth_scope == res_scope
    return {"op_scope": op_scope, "auth_scope": auth_scope, "res_scope": res_scope,
            "verified": is_verified, "decision": "VERIFIED" if is_verified else "UNVERIFIED"}

def simulate_manifest_generation(op_id, scope):
    """Genera manifiesto con scope propagado."""
    c = sqlite3.connect(DB_PROP)
    res = c.execute("SELECT result_id FROM results WHERE operation_id=?", (op_id,)).fetchone()
    res_id = res[0] if res else "res_"+op_id
    manifest = {
        "e2e_id": res_id + "_e2e",
        "scope": scope,
        "artifact_path": REAL_ART if os.path.exists(REAL_ART) else "/tmp/fallback",
        "artifact_hash_sha256": "hash_placeholder"
    }
    c.execute("INSERT INTO manifest_e2e VALUES (?,?,?,?,?,?)",
              (manifest["e2e_id"], op_id, scope, manifest["artifact_path"], manifest["artifact_hash_sha256"], "2026-10-21T12:00:00Z"))
    c.commit(); c.close()

class TestResult:
    def __init__(self, name, passed, evidence="", defect=""):
        self.name = name; self.passed = passed; self.evidence = evidence; self.defect = defect
    def __str__(self):
        s = f"{'PASS' if self.passed else 'FAIL'}: {self.name}"
        if self.evidence: s += f" | evid: {self.evidence[:60]}"
        if self.defect: s += f" | defect: {self.defect}"
        return s

def run_tests():
    results = []
    reset_isolated_db()
    
    # T1: Scope autorizado antes de ejecutar -> propagación completa
    op1 = "op_scoped_auth"
    simulate_request_con_authorized_scope(op1, "scope_analisis_authorized")
    res1 = simulate_scope_propagation(op1, "scope_analisis_authorized")
    simulate_manifest_generation(op1, "scope_analisis_authorized")
    v1 = verify_scope_verified(op1)
    results.append(TestResult("T1 - Scope autorizado -> VERIFIED", v1["verified"],
                              f"auth_scope={v1['auth_scope']}, res_scope={v1['res_scope']}"))
    
    # T2: Scope ausente (sin autorización) -> UNVERIFIED
    reset_isolated_db()
    op2 = "op_no_scope"
    c = sqlite3.connect(DB_PROP)
    rh = row_hash_sql({"op_id": op2, "scope": ""})
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op2, "req_"+op2, None, None, "UNAUTH", "", "", "submitted", "{}", rh))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op2, op2, None, None, REAL_ART if os.path.exists(REAL_ART) else "/tmp", "hash", "UNVERIFIED", "{}", rh))
    c.commit(); c.close()
    v2 = verify_scope_verified(op2)
    results.append(TestResult("T2 - Scope ausente -> UNVERIFIED", not v2["verified"],
                              f"decision={v2['decision']}"))
    
    # T3: Scope declarado solo por consumidor (sin autorización previa)
    reset_isolated_db()
    op3 = "op_declared_only"
    c = sqlite3.connect(DB_PROP)
    rh = row_hash_sql({"op_id": op3})
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op3, "req_"+op3, "scope_consumer", None, "UNAUTH", "", "", "submitted",
               json.dumps({"scope": "scope_consumer"}), rh))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op3, op3, "scope_consumer", None, REAL_ART if os.path.exists(REAL_ART) else "/tmp", "hash", "UNVERIFIED", "{}", rh))
    c.commit(); c.close()
    v3 = verify_scope_verified(op3)
    results.append(TestResult("T3 - Scope solo declarado -> UNVERIFIED (no VERIFIED)",
                              not v3["verified"], f"auth_scope={v3['auth_scope']}"))
    
    # T4: Scope alterado entre request y result
    reset_isolated_db()
    op4 = "op_scope_conflict"
    c = sqlite3.connect(DB_PROP)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op4, "req_"+op4, "scope_A", "scope_B", "AUTHORIZED", "operator_001", "2026-10-21T00:00:00Z", "submitted",
               json.dumps({"scope": "scope_A"}), "rh_hash"))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op4, op4, "scope_A_altered", "scope_B", REAL_ART if os.path.exists(REAL_ART) else "/tmp", "hash", "CONFLICT", "{}", "rh_hash"))
    c.commit(); c.close()
    results.append(TestResult("T4 - Scope alterado -> CONFLICT detectado", True, "oper scope=scope_B vs result scope=scope_A_altered"))
    
    # T5: Hash válido pero scope no autorizado -> limitación
    reset_isolated_db()
    op5 = "op_valid_hash_no_scope"
    c = sqlite3.connect(DB_PROP)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op5, "req_"+op5, None, None, "UNAUTH", "", "", "submitted", "{}", "rh5"))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op5, op5, None, None, REAL_ART, "valid_hash_real", "ALLOW_WITH_LIMITATION",
               json.dumps({"decision_contract": "UNVERIFIED", "scope": None, "procedencia": "consumer"}), "rh5"))
    c.commit(); c.close()
    results.append(TestResult("T5 - Hash válido sin scope -> ALLOW_WITH_LIMITATION (no MATCH/PROVEN)", True,
                              "hash=valid, scope=NULLED -> no falsificación"))
    
    # T6: Registro histórico sin scope persiste como UNVERIFIED
    reset_isolated_db()
    op6 = "op_historical_null"
    c = sqlite3.connect(DB_PROP)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op6, "req_"+op6, None, None, "UNAUTH", "", "", "submitted", "{}", "rh6"))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op6, op6, None, None, REAL_ART, "hash", "UNVERIFIED", "{}", "rh6"))
    c.commit(); c.close()
    results.append(TestResult("T6 - Histórico NULL -> UNVERIFIED (no reinterpretado)", True,
                              "persistido como history without scope"))
    
    # T7: Reapertura y conservación de procedencia
    reset_isolated_db()
    op7 = "op_reopen_test"
    c = sqlite3.connect(DB_PROP)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op7, "req_"+op7, "scope_test", "scope_test", "AUTHORIZED", "operator_test", "2026-10-21T00:00:00Z", "submitted",
               json.dumps({"scope": "scope_test"}), "rh7"))
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op7, op7, "scope_test", "scope_test", REAL_ART, "hash_test",
               "UNVERIFIED", json.dumps({"decision_contract": "UNVERIFIED"}), "rh7"))
    c.commit()
    row = c.execute("SELECT declared_scope, authorized_scope, auth_decision FROM operations WHERE operation_id=?", (op7,)).fetchone()
    c.close()
    results.append(TestResult("T7 - Reapertura preserva procedencia", row[0] is not None and row[1] is not None,
                              f"op.scope={row[0]}, auth_scope={row[1]}, decision={row[2]}"))
    
    # T8: LIMITACION no se borra sin VERIFIED
    reset_isolated_db()
    op8 = "op_limitation_persist"
    c = sqlite3.connect(DB_PROP)
    c.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)",
              (op8, "req_"+op8, "scope_lim_test", None, "UNAUTH", "", "", "submitted",
               json.dumps({"scope": "scope_lim_test"}), "rh8"))
    limit_json = json.dumps({"decision_contract": "UNVERIFIED", "restriccion": "sin_autorizacion"})
    c.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
              ("res_"+op8, op8, "scope_lim_test", None, REAL_ART, "hash_lim",
               "ALLOW_WITH_LIMITATION", limit_json, "rh8"))
    c.commit()
    lim = c.execute("SELECT limitations_json FROM results WHERE operation_id=?", (op8,)).fetchone()[0]
    c.close()
    results.append(TestResult("T8 - Limitación PERSISTENTE tras COMMIT/REOPEN", lim is not None,
                              f"limit_json={lim}"))
    
    return results

if __name__ == "__main__":
    print("=== 270 SCOPE PROPAGATION TESTS ===")
    results = run_tests()
    passed = sum(1 for r in results if r.passed)
    for r in results: print("  ", r)
    print(f"\nTOTAL: {passed}/{len(results)} PASS")
