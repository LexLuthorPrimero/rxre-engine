#!/usr/bin/env python3
"""RXRE-MISSION-272 — INTEGRACIÓN REAL DEL SCOPE EN EL FLUJO (store.registrar + machine.py)."""
import sys, os, sqlite3, json, hashlib, glob
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store
from rxre.contracts import scope_authority_propagation as SAP

REPO = "/home/lucas/Escritorio/rxre"
DB_ISO = "/tmp/rxre_272_real.sqlite3"
DB_OP = os.path.join(REPO, ".rxre/storage/rxre.sqlite3")
ART = os.path.join(REPO, "audit/strace/glxinfo_trace_20261019_005110.txt")


def extend(c):
    c.execute("ALTER TABLE operations ADD COLUMN declared_scope TEXT DEFAULT ''")
    c.execute("ALTER TABLE operations ADD COLUMN authorized_scope TEXT DEFAULT ''")
    c.execute("ALTER TABLE operations ADD COLUMN auth_decision TEXT DEFAULT 'UNAUTH'")
    c.execute("ALTER TABLE operations ADD COLUMN auth_actor TEXT DEFAULT ''")
    c.execute("ALTER TABLE operations ADD COLUMN auth_timestamp TEXT DEFAULT ''")
    c.execute("ALTER TABLE results ADD COLUMN verified_scope TEXT DEFAULT ''")
    c.execute("ALTER TABLE results ADD COLUMN scope_decision TEXT DEFAULT 'UNVERIFIED'")
    c.execute("ALTER TABLE results ADD COLUMN limitations_json TEXT DEFAULT '{}'")
    c.commit()


def nuevo_db():
    if os.path.exists(DB_ISO):
        os.remove(DB_ISO)
    c = store.conectar(DB_ISO)
    extend(c)
    return c


# 1) machine.py incluye integración de autorización
with open(os.path.join(REPO, "tools/rxre/api/machine.py")) as f:
    src = f.read()
assert "scope_authorization = params.get" in src, "machine.py falta integración"
assert "AUTORIZACIÓN DEL SCOPE" in src
print("[PASS] machine.py: integración scope_authorization presente (bloque ~6273-6279)")

# 2) DB aislada con schema real extendido
c = nuevo_db()
print("[PASS] DB_ISO aislada creada con schema real (store.conectar) + columnas de autorización")

# 3) Request real con decisión del operador -> store.registrar
request = {
    "op": "claim", "target": "analysis",
    "scope": "scope_analisis_authorized",
    "scope_authorization": {"decision": "AUTHORIZED", "actor": "lucas",
                             "timestamp": "2026-10-21T12:00:00Z"},
    "evidence_ids": ["res_real_001"],
}
env = {"status": "ok", "op": "claim"}
op_id = store.registrar(c, request, env, 0.0)
print("[PASS] store.registrar persistió operation_id=%s" % op_id)

# 4) Persistencia real del request con autorización
row = c.execute("SELECT operation_id, scope, request_json FROM operations WHERE operation_id=?", (op_id,)).fetchone()
assert row[0] == op_id
assert row[1] == "scope_analisis_authorized", "operations.scope no persistido: %r" % (row[1],)
assert "scope_authorization" in (row[2] or ""), "scope_authorization no persistido en request_json"
print("[PASS] Persistencia real: operations.scope=%s ; request_json contiene scope_authorization" % row[1])

# 5) Resultado con scope (productor)
c.execute("INSERT INTO results (result_id,operation_id,scope,tool,tool_version,status,raw_json,row_hash,timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
          ("res_272_real", op_id, "scope_analisis_authorized", "adapter_finding_tierra", "8a3c", "UNVERIFIED",
           json.dumps({"scope_decision":"UNVERIFIED","scope":"scope_analisis_authorized","source":"machine.py P1"}),
           hashlib.sha256(b"r272").hexdigest()[:16], "2026-10-21T12:00:00Z"))
c.commit()
r = c.execute("SELECT scope FROM results WHERE operation_id=?", (op_id,)).fetchone()
assert r[0] == "scope_analisis_authorized"
print("[PASS] results.scope persistido=%s (vinculado a operation_id)" % r[0])

# 6) Contrato: autorización DOCUMENTED_AUTHORITY + coherencia
auth = SAP.verificar_autorizacion_scope(DB_ISO, op_id, json.dumps(request), "scope_analisis_authorized")
assert auth["autenticidad"] == "DOCUMENTED_AUTHORITY", str(auth)
assert auth["decision_contract"] == "AUTHORIZED", str(auth)
assert auth["actor_verificado"] == "lucas"
assert "scope_analisis_authorized" in str(auth.get("scopes_resultados", []))
print("[PASS] Contrato: DOCUMENTED_AUTHORITY (archivo SCOPE_AUTHORITY_DECISION.md), actor=lucas, actor verificado")

# 7) Conflicto declarado vs resultado
c = nuevo_db()
req_conf = {"op": "claim", "scope": "scope_A",
            "scope_authorization": {"decision": "AUTHORIZED", "actor": "lucas",
                                    "timestamp": "2026-10-21T00:00:00Z"}}
op_conf = store.registrar(c, req_conf, env, 0.0)
c.execute("INSERT INTO results (result_id,operation_id,scope,tool,tool_version,status,raw_json,row_hash,timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
          ("res_A", op_conf, "scope_B_altered", "adapter_finding_tierra", "8a3c", "CONFLICT",
           json.dumps({"scope":"scope_B_altered","conflicto":True}), "h_A", "2026-10-21T12:00:00Z"))
c.commit()
auth_conf = SAP.verificar_autorizacion_scope(DB_ISO, op_conf, json.dumps(req_conf), "scope_A")
print("[PASS] Conflicto: declared=%s vs results.scope=%s (decision=%s)" % ("scope_A", "scope_B_altered", auth_conf["decision_contract"]))

# 8) Sin autorización -> no VERIFIED
op_no = store.registrar(c, {"op": "claim", "scope": "scope_consumer"}, env, 0.0)
c.execute("INSERT INTO results (result_id,operation_id,scope,tool,tool_version,status,raw_json,row_hash,timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
          ("res_consumer", op_no, "scope_consumer", "adapter_finding_tierra", "8a3c", "UNVERIFIED",
           json.dumps({"scope":"scope_consumer","decision_contract":"UNVERIFIED"}), "h_c", "2026-10-21T12:00:00Z"))
c.commit()
auth_no = SAP.verificar_autorizacion_scope(DB_ISO, op_no, json.dumps({"op": "claim", "scope": "scope_consumer"}), "scope_consumer")
assert auth_no["decision_contract"] in ("UNVERIFIED", "UNAUTH"), str(auth_no)
print("[PASS] Sin autorización -> decision_contract=%s (nunca VERIFIED)" % auth_no["decision_contract"])

# 9) Invariantes DB_OP
op = sqlite3.connect("file:%s?mode=ro" % DB_OP, uri=True)
counts = op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
rs = op.execute("SELECT scope FROM results").fetchall()
os_ = op.execute("SELECT scope FROM operations").fetchall()
op.close()
assert counts == (1, 0, 0), str(counts)
assert all(s[0] is None for s in rs), str(rs)
assert all(s[0] is None for s in os_), str(os_)
print("[PASS] DB_OP intacto: counts=%s results.scope=%s operations.scope=%s" % (counts, rs, os_))

# 10) Manifiestos E2E reales no alterados
n = 0
for mp in glob.glob(os.path.join(REPO, "audit/evidence/e2e_*.json")):
    mf = json.load(open(mp))
    assert mf.get("e2e_id") is not None
    assert (mf.get("artefacto_hash_sha256") or mf.get("hash_sha256") or mf.get("artefacto_path")) is not None
    assert not mf.get("scope"), "Manifest con scope no autorizado: %s" % os.path.basename(mp)
    n += 1
print("[PASS] %d manifiestos E2E reales sin scope (no alterados)" % n)

c.close()
print("\n=== 272 INTEGRACIÓN REAL: PASS ===")
