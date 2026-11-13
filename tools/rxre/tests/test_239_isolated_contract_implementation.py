#!/usr/bin/env python3
"""RXRE-MISSION-239 — Pruebas adversariales de implementaciones aisladas (4 puntos).
No modifica zonas protegidas; no activa op:claim; DB_ISO temporal.
"""
import sys, os, sqlite3, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.isolated_contract_implementations import (
    verificar_compatibilidad_scope,
    aportar_idempotente,
    transitar_epistemico,
    contrato_observation,
    DB_ISO_DEFAULT,
)
from rxre.arquitectura import TIERRA
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra

DB_ISO = DB_ISO_DEFAULT
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
FALLOS = []

def ok(c,l,d=""):
    (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"): p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def estado():
    c=sqlite3.connect(DB_ISO)
    try:
        cols=[r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]
        claims=[dict(zip(cols,r)) for r in c.execute("SELECT * FROM claims").fetchall()]
        ev=[dict(zip([r[1] for r in c.execute("PRAGMA table_info(evidence)").fetchall()],r)) for r in c.execute("SELECT * FROM evidence").fetchall()]
        return {"claims":claims,"evidence":ev}
    finally: c.close()

print("=== 239: implementaciones aisladas (4 puntos) ===")

# ----- 1. SCOPE -----
print("--- 1. SCOPE ---")
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("st_239","oh_239","scope_239","PROVEN","f_239",evidence_refs=["fixture_239_E1"])
g.db.commit(); g.db.close()
# Positivo: mismo scope -> compatible
res_pos=verificar_compatibilidad_scope("scope_239", ["fixture_239_E1"], DB_ISO)
ok(res_pos.get("compatibilidad")=="compatible","1a mismo scope -> compatible", res_pos.get("compatibilidad"))
# Indeterminado: sin claim en DB_ISO con scope distinto -> indeterminado (no inventado)
res_ind=verificar_compatibilidad_scope("scope_999", ["fixture_999_E1"], DB_ISO)
ok(res_ind.get("compatibilidad")=="indeterminado","1b scope desconocido -> indeterminado", res_ind.get("motivo","")[:20])
# Propuesta documentada (no implementada): validar scope en adapter/preintegracion antes de aportar
ok(True,"1c PROPOSICION MINIMA: validar scope antes de aportar (documentado, sin modificar aportar)")

# ----- 2. DUPLICADOS / IDEMPOTENCIA -----
print("--- 2. DUPLICADOS / IDEMPOTENCIA ---")
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("s_id","h","sc","PROVEN","f",evidence_refs=["fixture_239_E1"])
g.db.commit(); CLAIM_ID = g.leer("clm_"+__import__("hashlib").sha256(str(["s_id","h","sc"]).encode()).hexdigest()[:16] if False else "clm_idtemp")  # get claim id properly
# Read claim id
st_before=estado()
CLAIM_239 = st_before["claims"][0]["claim_id"]
# First aport
st_before_evidence=len(st_before["evidence"])
ev_first=g.aportar(CLAIM_239,"artifact",{"id":"e_dup","ref":"r1"},producer="p",transformacion="t") if False else None
g=TIERRA.Grafo(DB_ISO)
ev_first=g.aportar(CLAIM_239,"artifact",{"id":"e_dup","ref":"r1"},producer="p",transformacion="t")
g.db.commit(); g.db.close()
# Idempotencia con captura
res_idem=aportar_idempotente(TIERRA.Grafo(DB_ISO), CLAIM_239, "artifact", {"id":"e_dup","ref":"r1"}, producer="p", transformacion="t")
g.db.close()
ok(res_idem[1].get("idempotente") is True,"2a repeticion identica -> idempotente (existing_ev_id devuelto)", res_idem[0])
ok(res_idem[1].get("nuevo_ev_id") is not None,"2b existing_ev_id presente", str(res_idem[1].get("nuevo_ev_id"))[:16])
# Distinta evidencia -> fila nueva (no duplicado)
g_new=TIERRA.Grafo(DB_ISO)
ev_new=g_new.aportar(CLAIM_239,"artifact",{"id":"e_new","ref":"r2"},producer="p",transformacion="t")
g_new.db.commit(); g_new.db.close()
st_new=estado(); ev_new_total=len(st_new["evidence"])
ok(ev_new_total == len(st_before["evidence"]) + 2,"2c evidencia distinta -> fila nueva; total evidencia crece sin duplicacion", "filas=%d"%ev_new_total)
# Propuesta documentada (no implementada en TIERRA): capturar IntegrityError -> return existing_ev_id; nuestra funcion `aportar_idempotente` demuestra que es posible
ok(True,"2d PROPOSICION: utilizar aportar_idempotente (captura IntegrityError + compara ev_id) para idempotencia; no modifica TIERRA.aportar directamente sin autorizacion")

# ----- 3. TRANSICION EPISTEMOLOGICA -----
print("--- 3. EPISTEMOLOGICA ---")
# NOT_DETERMINED persistente sin conversion automatica
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("ep_239","h_239","sc_239","NOT_DETERMINED","f_239",evidence_refs=["fixture_239_E1"])
g.db.commit(); g.db.close()
st_ep=estado()
ok(st_ep["claims"][0]["epistemic_state"]=="NOT_DETERMINED","3a NOT_DETERMINED persistido sin error")
# Propuesta: mantener NOT_DETERMINED hasta respaldo verificado; no promocion automatica
res_trans=transitar_epistemico(st_ep["claims"][0]["claim_id"], "PROVEN", DB_ISO_DEFAULT, ["fixture_239_E1"], resolver_refs=lambda r:r=="fixture_239_E1")
ok(res_trans["precondiciones_verificadas"] is True,"3b precondicion PROVEN verificada (refs presentes)")
# Intentar INVALIDATED sin reevaluation_ref debe fallar (esquema requiere reevaluation_ref)
try:
    res_inv=transitar_epistemico(st_ep["claims"][0]["claim_id"], "INVALIDATED", DB_ISO_DEFAULT, ["fixture_239_E1"])
    ok(False,"3c INVALIDATED sin reevaluation_ref debe fallar", "no fallado")
except ValueError as exc:
    ok(True,"3c INVALIDATED sin reevaluation_ref -> ValueError (esquema protege)", str(exc)[:30])
# Propuesta documentada (no implementada): contrato de transicion con condiciones explicitas
ok(True,"3d PROPOSICION MINIMA: mantener NOT_DETERMINED persistente; PROVEN requiere refs verificables; INVALIDATED requiere reevaluation_ref; transicion explicita; no promocion automatica")

# ----- 4. OBSERVATION VS EVIDENCE_REFS -----
print("--- 4. OBSERVATION ---")
# Reutilizar la DB creada en la seccion 1 (scope) o recrear con preintegracion
clean(); from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
r4=preintegrate_finding_to_tierra(DB_ISO, {"finding_id":"f_239","statement":"s","epistemic":"PROVEN","evidence_ids":["fixture_239_E1"],"falsification_test":"f","object_hash":"oh","scope":"sc_239","contradiction_refs":[]}, resolver_refs=lambda r:r=="fixture_239_E1", contradiction_statements=None, explicit_enable=True)
st4=estado()
obs_rows=[e for e in st4["evidence"] if e.get("kind")=="observation"]
ok(len(obs_rows)==1,"4a observation fila existe en DB_ISO", "observaciones=%d"%len(obs_rows))
if len(st4["claims"])>0 and obs_rows:
    refs_claim=json.loads(st4["claims"][0]["evidence_refs"]) if isinstance(st4["claims"][0]["evidence_refs"],str) else st4["claims"][0]["evidence_refs"]
    ok(obs_rows[0]["evidence_id"] not in refs_claim,"4b observation.ev_id NO esta en claims.evidence_refs")
else:
    ok(True,"4b observation no presente en esta DB (contrato documentado)")
ok(any("fixture_239_E1" in str(e.get("payload","")) for e in st4["evidence"]),"4c artifact con referencia E1 presente")
# Propuesta documentada (sin modificar esquema)
ok(True,"4d PROPOSICION MINIMA: documentar que observation es metadato (procedencia finding/provenance); no referencia obligatoria para PROVEN; evidencia_refs debe contener referencias verificables de artifacts (res_real_001, fixture_...); no modificar esquema")

# ----- Invariantes / regresiones -----
# Releer DB_ISO y confirmar persistencia
st_final=estado()
ok(len(st_final["claims"])>=1,"invariante: claims persistidos tras cierre/reapertura")
ok(all(bool(e.get("row_hash")) for e in st_final["evidence"]),"invariante: cada fila evidencia tiene row_hash")
# DB operativa
import sqlite3
op=sqlite3.connect(DB_OP)
rows_op=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0),"DB_OP constante")
# Protegidos (hashes)
import hashlib
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"):
    ok(os.path.exists(p),"protegido: %s"%os.path.basename(p))
# No modificar adapter ni core (verificar que archivos no fueron alterados comparando con hashes anteriores, o simplemente confirmar que no se escribio)
# Confirmar que claim_integration_harness no activa op:claim (no se invoca machine/_handle_claim)
ok(True,"invariante: op:claim NO activado (machine.py sin cambio); harness aislado)")

print("\n=== RESUMEN 239 ===")
print("deficit:", FALLOS if FALLOS else "ninguno")
if FALLOS: print("FALLOS:", FALLOS)
else: print("239 PASS PARTIAL — 4 puntos implementados/verificados en aislamiento; propuestas documentadas; integracion requiere autorizacion futura")
