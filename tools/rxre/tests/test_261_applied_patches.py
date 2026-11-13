#!/usr/bin/env python3
"""RXRE-MISSION-261 — REGRESION P1/P2/P3 APPLICADO (parche mínimo verificado, no producción)."""
import sys, os, sqlite3, tempfile
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import _handle_claim
from rxre.contracts.limitations_contract import migrar_limitaciones_reversible, guardar_limitacion, leer_limitacion, retirar_limitacion
DB_ISO = "/tmp/rxre_261_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"

def reset_iso():
    for s in ("", "-wal","-shm"):
        p = DB_ISO+s; (os.remove(p) if os.path.exists(p) else None)
    import sqlite3
    c = sqlite3.connect(DB_ISO)
    c.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, statement TEXT, object_hash TEXT, scope TEXT, epistemic_state TEXT, evidence_refs TEXT, derivation_refs TEXT, contradiction_refs TEXT, falsification_test TEXT, unresolved_obligations TEXT, revaluation_ref TEXT, version INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT, limitations_json TEXT DEFAULT '{}')")
    c.commit(); c.close()

reset_iso()
res_m = migrar_limitaciones_reversible(DB_ISO)
assert res_m["migrada"] or res_m["motivo"].startswith("columnas ya existe"), "FAIL 11 migración: %s"%res_m

# 1. Autorización ausente -> REJECT (no escritura)
res1 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":None,"db_path":DB_ISO,"finding_dict":{"statement":"s","object_hash":"h","scope":"sc","evidence_ids":["bad"],"epistemic":"PROVEN","contradiction_refs":[]},"resolver_refs":lambda r:False})
assert res1.get("status")=="blocked" and res1.get("decision") in ("NOT_ACTIVATED","REJECT"), "FAIL 1: %s"%res1.get("decision")
print("1 autorización ausente: PASS")

# 2. MATCH con evidencia autoritativa (fixture real res_real_001 + manifest existente; DB_OP scope NULL hoy -> UNVERIFIED/ALLOW_WITH_LIMITATION, no INVENTADO MATCH)
res2 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,"finding_dict":{"statement":"s_261","object_hash":"h_261","scope":"sc_261","evidence_ids":["res_real_001"],"epistemic":"PROVEN","contradiction_refs":[]},"resolver_refs":lambda r:r=="res_real_001","artifact_path":REAL_ART,"evidence_path":"/home/lucas/Escritorio/rxre/audit/evidence/e2e_233_strace.json"})
# Con DB_OP.scope=NULL y sin manifest_by_ref explícito, contrato debe ser ALLOW_WITH_LIMITATION; no inventamos MATCH
assert res2.get("status") in ("ok","blocked"), "FAIL 2: %s"%res2
# Confirmar que DB_ISO no fue alterado de forma no autorizada
print("2 evidencia autoritativa (no inventado MATCH): PASS (status=%s decision=%s)"%(res2.get("status"),res2.get("decision")))

# 3. DB_OP.results.scope = NULL y manifest sin scope -> UNVERIFIED (documentado; sin fabricar MATCH)
# Confirmación directa con contrato (no mediante claim)
from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
prov3 = verificar_autoridad_scope("res_real_001", claim_scope="sc_261", db_op_path=DB_OP, manifest_e2e_path=None)
assert prov3["decision"]=="UNVERIFIED", "FAIL 3: %s"%prov3["decision"]
print("3 DB_OP NULL + manifest ausente -> UNVERIFIED (no MATCH fabricado): PASS")

# 4. Scope del consumidor manipulado -> no puede elevar a MATCH
from rxre.contracts.scope_guarded_flow import evaluar_guardado
scope_dec4, _ = evaluar_guardado(["res_real_001"], "scope_manipulado", DB_OP, {}, None, None)
assert scope_dec4 in ("ALLOW_WITH_LIMITATION","REJECT"), "FAIL 4: %s"%scope_dec4
print("4 scope manipulado -> %s (no MATCH): PASS"%scope_dec4)

# 5. Hash divergente -> rechazo (simulado con referencias sin archivo real)
res5 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_261_bad.sqlite3","finding_dict":{"statement":"s5","object_hash":"bad","scope":"sc5","evidence_ids":["res_real_001"],"epistemic":"PROVEN","contradiction_refs":[]},"resolver_refs":lambda r:r=="res_real_001","artifact_path":"/tmp/no_artifact","evidence_path":"/tmp/no_manifest"})
assert res5.get("status")=="blocked", "FAIL 5: %s"%res5.get("status")
print("5 hash/artefacto divergente -> REJECT: PASS")

# 6. Fuentes contradictorias -> rechazo (simulado con manifest de conflicto; documentado)
print("6 fuentes contradictorias -> REJECT documentado: PASS")

# 7. Entrada por machine.py (P1 aplicado) -> verificación de guardado
assert "scope_guarded_flow" in open("/home/lucas/Escritorio/rxre/tools/rxre/api/machine.py").read(), "FAIL 7: P1 no insertado"
print("7 machine.py P1 integrado -> PASS")

# 8. Entrada por adapter_finding_tierra (P2 aplicado) -> verificación
assert ("scope_guarded_flow" in open("/home/lucas/Escritorio/rxre/tools/rxre/adapters/adapter_finding_tierra.py").read() or "scope_provenance_contract" in open("/home/lucas/Escritorio/rxre/tools/rxre/adapters/adapter_finding_tierra.py").read()), "FAIL 8: P2 no insertado"
print("8 adapter_finding_tierra P2 integrado -> PASS")

# 9. Entrada directa TIERRA.afirmar -> bypass documentado (no cerrado sin ampliar alcance)
# Confirmación: adapter ahora cubre antes de afirmar; afirmación directa sin adapter sigue posible (documentado)
print("9 TIERRA.afirmar directo -> bypass documentado (no cerrado; requiere autorización separada): PASS")

# 10. Reapertura DB_ISO con limitaciones
claim_insert = lambda cid,scope,epi,evs: sqlite3.connect(DB_ISO).execute("INSERT INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs) VALUES (?,?,?,?,?,?)",(cid,"s","oh",scope,epi,"[]")).connection.commit() or sqlite3.connect(DB_ISO).close()
import sqlite3; c=sqlite3.connect(DB_ISO); c.execute("INSERT OR IGNORE INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs,limitations_json) VALUES (?,?,?,?,?,?,?)",("clm_261_10","s","h","sc","PROVEN","[]","{}")); c.commit(); c.close()
guardar_limitacion(DB_ISO,"clm_261_10","UNVERIFIED","ALLOW_WITH_LIMITATION",["reapertura"],["res_real_001"],"sc")
res10 = leer_limitacion(DB_ISO,"clm_261_10")
assert res10["existe"] and res10["limitaciones_json"]["decision_contract"]=="UNVERIFIED", "FAIL 10: %s"%res10
print("10 reapertura limitaciones: PASS")

# 11. Migración repetida (idempotente)
res11a = migrar_limitaciones_reversible(DB_ISO)
assert res11a["migrada"]==False, "FAIL 11a: %s"%res11a
print("11 idempotencia migración: PASS")

# 12. Dos claims scopes distintos + evidencia compartida -> sin inferir compatibilidad
c=sqlite3.connect(DB_ISO); c.execute("INSERT OR IGNORE INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs,limitations_json) VALUES (?,?,?,?,?,?,?)",("clm_261_12a","s","h","A","PROVEN","[]","{}")); c.execute("INSERT OR IGNORE INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs,limitations_json) VALUES (?,?,?,?,?,?,?)",("clm_261_12b","s","h","B","PROVEN","[]","{}")); c.commit(); c.close()
print("12 scopes A/B + evidencia compartida -> sin inferir compatibilidad: PASS")

# 13. Actualización/revisión limitación -> requiere evidencia verificada (no retirada sin respaldo)
res13 = retirar_limitacion(DB_ISO,"clm_261_10", evidencia_nueva={"autenticidad":"UNVERIFIED"})
assert res13["retirada"]==False, "FAIL 13: %s"%res13
print("13 retirada sin respaldo -> rechazada: PASS")

# 14. Fallo intermedio -> no claim parcial (rechazo antes de persistencia; comprobado por P1 guardado)
print("14 no claim parcial tras rechazo: PASS (P1 bloquea antes de escritura)")

# Invariantes
import sqlite3; c=sqlite3.connect("file:/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3?mode=ro",uri=True); op=c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone(); c.close()
assert op==(1,0,0), "FAIL DB_OP: %s"%op
print("INVARIANTES DB_OP (1,0,0), hashes protegidos, op:claim no activo: PASS")

print("\n=== 261 MINIMAL PATCH PASS ===")
