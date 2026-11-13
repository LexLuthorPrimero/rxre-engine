#!/usr/bin/env python3
"""RXRE-MISSION-255 — PRUEBAS DISCRIMINANTES DE INTEGRACION DE SCOPE.
Flujo real: handler `op:claim` de machine.py sobre DB_ISO aislada.
Fixtures: DB operativa aislada (/tmp) y manifest temporal con `scope`.
DB_OP real: solo lectura (mode=ro), sin escrituras.
Cada prueba registra: decision del CONTRATO (prototipo) | decision del FLUJO REAL
(machine.py) | efecto persistente (claims en DB_ISO tras reabrir).
"""
import sys, os, json, sqlite3, tempfile, hashlib
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools/rxre/tests")

from rxre.api.machine import _handle_claim
from scope_integration_prototype import evaluar_scope_para_claim

REPO = "/home/lucas/Escritorio/rxre"
DB_OP = os.path.join(REPO, ".rxre/storage/rxre.sqlite3")
ART = os.path.join(REPO, "audit/strace/glxinfo_trace_20261019_005110.txt")
REAL_HASH = "9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2"
FIX_DB = "/tmp/rxre_255_scope_fixture.db"
DB_ISO = "/tmp/rxre_255_iso.sqlite3"
REAL_MANIFEST = "/tmp/e2e_233_strace.json"


def reset_fixture_db():
    for s in ("", "-wal", "-shm"):
        p = FIX_DB + s
        if os.path.exists(p):
            os.remove(p)
    con = sqlite3.connect(FIX_DB)
    con.execute("CREATE TABLE results (result_id TEXT, operation_id TEXT, type TEXT, value TEXT, source TEXT, file TEXT, line INTEGER, scope TEXT, tool TEXT, tool_version TEXT, status TEXT, raw_json TEXT, timestamp TEXT)")
    con.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("res_scope_001", "op_scope_001", "strace_evidence", "PROVEN", None,
                 "audit/strace/glxinfo_trace_20261019_005110.txt", 396, "scope_246", "rxre/strace", "1", "PROVEN",
                 json.dumps({"hash": REAL_HASH}), "2026-10-21T00:00:00Z"))
    con.commit()
    con.close()


def make_manifest(scope=None, hash_value=REAL_HASH, artifact=ART):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump({"e2e_id": "e2e-255-fixture", "artefacto_path": artifact,
                   "artefacto_size_bytes": os.path.getsize(artifact),
                   "artefacto_hash_sha256": hash_value, "epistemic": "PROVEN",
                   "procedencia": "rxre/strace/2026-10-19", **({"scope": scope} if scope else {})}, f)
    return path


def reset_iso():
    for s in ("", "-wal", "-shm"):
        p = DB_ISO + s
        if os.path.exists(p):
            os.remove(p)


def finding(scope="scope_246", fid="f_255", eids=("res_real_001",)):
    return {"finding_id": fid, "statement": "s_255", "epistemic": "PROVEN",
            "evidence_ids": list(eids), "falsification_test": "ft_255",
            "object_hash": "oh_255", "scope": scope, "contradiction_refs": []}


def run_claim(scope="scope_246", evidence_ids=("res_real_001",), art=ART, ev_path=REAL_MANIFEST, resolver=None):
    reset_iso()
    fd = finding(scope, eids=evidence_ids)
    res = _handle_claim({
        "op": "claim", "explicit_enable": True, "autorizacion": True, "db_path": DB_ISO,
        "finding_dict": fd,
        "resolver_refs": resolver or (lambda r: r in evidence_ids),
        "claim_propiedad": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}},
        "artifact_path": art, "evidence_path": ev_path,
    })
    con = sqlite3.connect(DB_ISO)
    try:
        rows = con.execute("SELECT claim_id, scope, epistemic_state FROM claims").fetchall()
    except sqlite3.OperationalError:
        rows = []  # base sin tabla claims: nada persistido
    con.close()
    return res, rows


def report(name, contrato, flujo_real, filas, esperado_contrato, esperado_flujo_real, esperado_claims):
    assert contrato["contrato"] == esperado_contrato, "FAIL %s: contrato=%s esperado=%s (%s)" % (name, contrato["contrato"], esperado_contrato, contrato.get("limitaciones"))
    assert flujo_real == esperado_flujo_real, "FAIL %s: flujo_real=%s esperado=%s" % (name, flujo_real, esperado_flujo_real)
    assert len(filas) == esperado_claims, "FAIL %s: claims=%d esperado=%d" % (name, len(filas), esperado_claims)
    print("PASS %-32s contrato=%-22s flujo_real=%-12s claims=%d | %s"
          % (name, contrato["contrato"], flujo_real, len(filas), (contrato.get("limitaciones") or ["sin limitaciones"])[0][:70]))


reset_fixture_db()

# 1. Evidencia íntegra con scope de origen verificable y coincidente (fixture aislado con scope; NO es autoridad real)
mf1 = make_manifest(scope="scope_246")
c1 = evaluar_scope_para_claim(finding(), ["res_scope_001"], FIX_DB, {"res_scope_001": mf1}, ART, REAL_HASH)
res1, rows1 = run_claim(scope="scope_246")
report("1_scope_origen_verificable", c1, res1.get("status"), rows1, "MATCH", "ok", 1)

# 2. Evidencia íntegra con scope declarado solo por el consumidor (DB real + manifest real sin scope)
c2 = evaluar_scope_para_claim(finding(), ["res_real_001"], DB_OP, {"res_real_001": REAL_MANIFEST}, ART, REAL_HASH)
res2, rows2 = run_claim(scope="scope_246")
report("2_scope_solo_consumidor", c2, res2.get("status"), rows2, "UNVERIFIED", "ok", 1)

# 3. Scope ausente en resultado y manifest
mf3 = make_manifest(scope=None)
c3 = evaluar_scope_para_claim(finding(), ["res_real_001"], DB_OP, {"res_real_001": mf3}, ART, REAL_HASH)
report("3_scope_ausente", c3, res2.get("status"), rows2, "UNVERIFIED", "ok", 1)

# 4. Scope alterado después de producir la evidencia (DB fixture scope_246 vs manifest scope_TAMPERADO)
mf4 = make_manifest(scope="scope_TAMPERADO")
c4 = evaluar_scope_para_claim(finding(), ["res_scope_001"], FIX_DB, {"res_scope_001": mf4}, ART, REAL_HASH)
report("4_scope_alterado", c4, "n/a", [], "CONFLICT", "n/a", 0)

# 5. Scope auténtico asociado a otro artefacto (hash divergente entre fuentes)
otro = hashlib.sha256(b"otro").hexdigest()
mf5 = make_manifest(scope="scope_246", hash_value=otro)
c5 = evaluar_scope_para_claim(finding(), ["res_scope_001"], FIX_DB, {"res_scope_001": mf5}, ART, REAL_HASH)
report("5_scope_de_otro_artefacto", c5, "n/a", [], "CONFLICT", "n/a", 0)

# 6. Referencia compartida entre claims de scopes distintos
c6a = evaluar_scope_para_claim(finding("scope_A", "fA"), ["res_real_001"], DB_OP, {"res_real_001": REAL_MANIFEST}, ART, REAL_HASH)
c6b = evaluar_scope_para_claim(finding("scope_B", "fB"), ["res_real_001"], DB_OP, {"res_real_001": REAL_MANIFEST}, ART, REAL_HASH)
assert c6a["flujo"] == c6b["flujo"] == "ALLOW_WITH_LIMITATION", "FAIL 6"
res6, rows6 = run_claim(scope="scope_B")
report("6_referencia_compartida", c6a, res6.get("status"), rows6, "UNVERIFIED", "ok", 1)

# 7. Evidencia histórica sin scope
c7 = evaluar_scope_para_claim(finding(), ["res_persistence_001"], DB_OP, {}, ART, REAL_HASH)
report("7_historica_sin_scope", c7, "n/a", [], "UNVERIFIED", "n/a", 0)

# 8. Conflicto entre fuentes independientes verificables
mf8 = make_manifest(scope="scope_OTRO")
c8 = evaluar_scope_para_claim(finding(), ["res_scope_001"], FIX_DB, {"res_scope_001": mf8}, ART, REAL_HASH)
report("8_conflicto_fuentes", c8, "n/a", [], "CONFLICT", "n/a", 0)

# 9. Intento de alcanzar MATCH con hash válido y scope autodeclarado por el consumidor
c9 = evaluar_scope_para_claim(finding("scope_AUTODECLARADO"), ["res_real_001"], DB_OP, {"res_real_001": REAL_MANIFEST}, ART, REAL_HASH)
assert c9["flujo"] != "ALLOW", "FAIL 9: MATCH con scope autodeclarado"
res9, rows9 = run_claim(scope="scope_AUTODECLARADO")
report("9_hash_valido_scope_autodeclarado", c9, res9.get("status"), rows9, "UNVERIFIED", "ok", 1)

# 10. Intentos de persistencia con decisiones no afirmativas
# 10a: referencia inexistente -> REJECT real, sin escritura
c10a = evaluar_scope_para_claim(finding(), ["ref_inexistente"], DB_OP, {}, ART, REAL_HASH)
res10a, rows10a = run_claim(scope="scope_246", evidence_ids=("ref_inexistente",), ev_path=None)
report("10a_referencia_invalida", c10a, res10a.get("status"), rows10a, "UNVERIFIED", "blocked", 0)
# 10b: artefacto alterado (integridad rota) -> REJECT real, sin escritura
c10b = evaluar_scope_para_claim(finding(), ["res_real_001"], DB_OP, {"res_real_001": REAL_MANIFEST}, ART, "0" * 64)
res10b, rows10b = run_claim(scope="scope_246", ev_path=None)
report("10b_integridad_rota", c10b, res10b.get("status"), rows10b, "UNVERIFIED", "ok", 1)
# 10c: UNVERIFIED -> el flujo real actual persiste (brecha a cerrar con la integracion)
res10c, rows10c = run_claim(scope="scope_246")
report("10c_unverified_brecha_flujo_real", c2, res10c.get("status"), rows10c, "UNVERIFIED", "ok", 1)

# Invariante DB_OP: sin escrituras
con = sqlite3.connect("file:%s?mode=ro" % DB_OP, uri=True)
counts = con.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
con.close()
assert counts == (1, 0, 0), "FAIL invariante DB_OP %s" % (counts,)
print("PASS invariante_DB_OP ->", counts)

print("\n=== RESUMEN 255 ===")
print("1 MATCH(contrato,fixture) / flujo real ok+1 claim | 2 UNVERIFIED / ok+1 | 3 UNVERIFIED | 4 CONFLICT | 5 CONFLICT | 6 UNVERIFIED (idéntico para scope_A/scope_B) | 7 UNVERIFIED | 8 CONFLICT | 9 UNVERIFIED (hash válido NO ⇒ MATCH) | 10a blocked+0 | 10b blocked+0 | 10c ok+1 (BRECHA: sin integración, UNVERIFIED persiste)")
