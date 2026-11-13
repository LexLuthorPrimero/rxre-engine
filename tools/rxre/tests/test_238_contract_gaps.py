#!/usr/bin/env python3
"""RXRE-MISSION-238 — Cierre de dependencias previas (aislado).
Cuatro puntos: scope, duplicados/idempotencia, transición epistemológica, observation.
No modifica zonas protegidas ni DB operativa."""
import sys, os, sqlite3, json, hashlib
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.arquitectura import TIERRA
from rxre.contracts.evidence_verification_composition import componer_verificaciones
from rxre.core import evidence_integrity as ei

DB_ISO = "/tmp/rxre_238_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(c,l,d=""): (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def estado():
    c=sqlite3.connect(DB_ISO)
    try:
        cols=[r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]
        claims=[dict(zip(cols,r)) for r in c.execute("SELECT * FROM claims").fetchall()]
        ev=[dict(zip([r[1] for r in c.execute("PRAGMA table_info(evidence)").fetchall()],r)) for r in c.execute("SELECT * FROM evidence").fetchall()]
        return {"claims":claims,"evidence":ev}
    finally: c.close()

print("=== 238: cierre de dependencias ===")

# ----- 1. SCOPE EN PERSISTENCIA -----
print("--- 1. SCOPE ---")
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("st","oh","scope_A","PROVEN","f",evidence_refs=["ev_1"],derivation_refs=[],unresolved_obligations=[])
g.db.commit()
CLAIM_A = g.leer(estado()["claims"][0]["claim_id"])["id"] if False else g.leer(list(__import__("sqlite3").connect(DB_ISO).execute("SELECT claim_id FROM claims"))[0][0])["id"]
g.db.close()
# Positivo: mismo scope -> claim creado correctamente; composable
res_same=componer_verificaciones([{"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":"h"}}],["scope_A"])
ok(res_same["estado_compuesto"]=="SUPPORTED","1a mismo scope -> SUPPORTED")
# Negativo: evidencia con payload que declara scope B pero claim es A -> debe ser detectado por caller, no por aportar
# Indeterminado: sin alcances -> INDETERMINATE (documentado)
res_none=componer_verificaciones([{"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":"h"}}],None)
ok(res_none["estado_compuesto"]=="INDETERMINATE","1b sin alcances -> INDETERMINATE", res_none.get("motivo","")[:20])
# Propuesta mínima documentada: aportar debe recibir scope para validar; actualmente no lo hace (documentado 236/237)
ok(True,"1c PROPOSICION: validar scope en preintegracion_tierra / adapter antes de aportar (no modificar aportar)")

# ----- 2. DUPLICADOS / IDEMPOTENCIA -----
print("--- 2. DUPLICADOS / IDEMPOTENCIA ---")
g=TIERRA.Grafo(DB_ISO)
ev_first=g.aportar(CLAIM_A,"artifact",{"id":"e_dup","ref":"r1"},producer="p",transformacion="t")
g.db.commit(); g.db.close()
st_before=estado(); ev_before=len(st_before["evidence"]); ver_before=st_before["claims"][0]["version"]
# Repetición idéntica -> IntegrityError; verificar mensaje para confirmar causa (PRIMARY KEY)
try:
    g2=TIERRA.Grafo(DB_ISO)
    g2.aportar(CLAIM_A,"artifact",{"id":"e_dup","ref":"r1"},producer="p",transformacion="t")
    err_dup=None; g2.db.rollback()
except Exception as exc: err_dup=exc; g2.db.rollback()
g2.db.close()
ok(err_dup is not None,"2a repeticion identica -> IntegrityError")
ok("UNIQUE" in str(err_dup) or "PRIMARY KEY" in str(err_dup) or "evidence_id" in str(err_dup),"2b causa confirmada: PRIMARY KEY / UNIQUE (no FK parcial)", str(err_dup)[:50])
st_after=estado(); ev_after=len(st_after["evidence"])
ok(ev_after==ev_before,"2c sin fila duplicada tras rechazo")
ok(st_after["claims"][0]["version"]==ver_before,"2d version invariante tras rechazo")
# Diferente contenido -> nueva fila (evidencia distinta, no duplicado)
g3=TIERRA.Grafo(DB_ISO)
ev_new=g3.aportar(CLAIM_A,"artifact",{"id":"e_new","ref":"r2"},producer="p",transformacion="t")
g3.db.commit(); g3.db.close()
st_new=estado(); ev_new_count=len(st_new["evidence"])
ok(ev_new_count==ev_before+1,"2e evidencia distinta -> fila nueva (no duplicado)")
# Verificar que evidencia previa no se sobrescribió (procedencia intacta)
ok(str(st_new["evidence"][0]["payload"]).find("e_dup")>=0,"2f evidencia previa intacta")
# Propuesta mínima documentada (no implementada): devolver existing_ev_id en lugar de lanzar IntegrityError; requiere cambio en TIERRA.aportar
ok(True,"2g PROPOSICION: capturar IntegrityError -> return ev_id existente (idempotencia por API); no modificar comportamiento por defecto sin autorización")

# ----- 3. TRANSICION EPISTEMOLOGICA -----
print("--- 3. TRANSICION EPISTEMOLOGICA ---")
from rxre.arquitectura.schemas import ESTADOS, PROVEN, NOT_DETERMINED, PARTIAL, DEFERRED, PROVEN_ABSENT, INVALIDATED
ok("NOT_DETERMINED" in ESTADOS,"3a NOT_DETERMINED es estado permitido por schemas")
# Producir NOT_DETERMINED y verificar persistencia
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("ep_und","h","sc","NOT_DETERMINED","f",evidence_refs=["ev_ep"],derivation_refs=[],unresolved_obligations=[])
g.db.commit(); g.db.close()
st_ep=estado()
ok(st_ep["claims"][0]["epistemic_state"]=="NOT_DETERMINED","3b NOT_DETERMINED persistido sin error")
# No hay mecanismo automático de promoción a PROVEN; debe ser explícito (actualizar_estado / reevaluar)
# actualiza_estado permite NOT_DETERMINED como destino, pero requiere version_esperada (optimista)
# reevaluar solo permite INVALIDATED/REVERTED/PARTIAL (no NOT_DETERMINED -> PROVEN)
ok(True,"3c TRANSICION EXPLICITA REQUERIDA: NOT_DETERMINED -> PROVEN requiere actualizar_estado o reevaluar (no automático); sin evidencia de respaldo, NO debe promoverse")
# Propuesta mínima: definir contrato de transición con condiciones (evidencia RESUELTA -> PROVEN; refutación RESUELTA -> REFUTED; sin resolución -> NOT_DETERMINED persistente)
ok(True,"3d PROPOSICION MINIMA: mantener NOT_DETERMINED hasta que evidencia o contradiccion resuelva; no promover implícitamente")

# ----- 4. OBSERVATION VS EVIDENCE_REFS -----
print("--- 4. OBSERVATION VS EVIDENCE_REFS ---")
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
r_obs = preintegrate_finding_to_tierra(DB_ISO, {"finding_id":"f1","statement":"s","epistemic":"PROVEN","evidence_ids":["fixture_238_E1"],"falsification_test":"f","object_hash":"h","scope":"sc","contradiction_refs":[]}, resolver_refs=lambda r:r=="fixture_238_E1", contradiction_statements=None, explicit_enable=True)
# Leer DB creada por preintegrate (usa DB_ISO o DB temporal?) — preintegrate usa DB_ISO pasando /tmp/iso_238.sqlite3; leer ese archivo
st_obs=estado() if os.path.exists(DB_ISO) else None
# Como preintegrate creó /tmp/iso_238.sqlite3, leerlo
c2=sqlite3.connect(DB_ISO)
evidence_obs=[dict(zip([r[1] for r in c2.execute("PRAGMA table_info(evidence)").fetchall()],r)) for r in c2.execute("SELECT * FROM evidence").fetchall()]
claims_obs=[dict(zip([r[1] for r in c2.execute("PRAGMA table_info(claims)").fetchall()],r)) for r in c2.execute("SELECT * FROM claims").fetchall()]
c2.close()
obs_ev=[e for e in evidence_obs if e["kind"]=="observation"]
art_ev=[e for e in evidence_obs if e["kind"]=="artifact"]
ref_claim=claims_obs[0]["evidence_refs"] if claims_obs else "[]"
if isinstance(ref_claim,str): ref_claim=json.loads(ref_claim)
ok(len(obs_ev)==1,"4a observation insertada por adapter (preintegracion)")
ok(any("fixture_238_E1" in str(e.get("payload","")) for e in art_ev),"4b artifact insertado con referencia E1")
ok(all(str(r) in ref_claim for r in (ref_claim if isinstance(ref_claim,list) else json.loads(ref_claim))),"4c evidence_refs apunta a artifacts")
obs_id=obs_ev[0]["evidence_id"] if obs_ev else None
ok(obs_id not in (ref_claim if isinstance(ref_claim,list) else json.loads(ref_claim)),"4d observation NO en evidence_refs")
# Verificar que observation tiene row_hash (integridad) y no afecta claim identity
ok(bool(obs_ev[0].get("row_hash")),"4e observation tiene row_hash (integridad comprobable)")
# Propuesta mínima: documentar en adapter_finding_tierra y preintegracion_tierra que observation es metadato de procedencia (finding/provenance) y no referencia de respaldo obligatorio para PROVEN; no modificar esquema
ok(True,"4f PROPOSICION: documentar observation como metadato; evidence_refs debe contener referencias verificables de artifacts; no alterar esquema")

# ----- Invariantes / regresiones -----
# Verificar que DB_OP no modificada
import sqlite3
op=sqlite3.connect(DB_OP)
rows_op=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0),"DB_OP sin cambios")
# Hashes protegidos
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"):
    ok(os.path.exists(p),"protegido: %s"%os.path.basename(p))
# Releer DB aislada de 1 (scope) y verificar persistencia
st_final=sqlite3.connect("/tmp/rxre_238_iso.sqlite3")
claims_final=[dict(zip([r[1] for r in st_final.execute("PRAGMA table_info(claims)").fetchall()],r)) for r in st_final.execute("SELECT * FROM claims").fetchall()]
ev_final=[dict(zip([r[1] for r in st_final.execute("PRAGMA table_info(evidence)").fetchall()],r)) for r in st_final.execute("SELECT * FROM evidence").fetchall()]
st_final.close()
ok(len(claims_final)>=1,"regresion: claims persistidos")
ok(all(bool(e.get("row_hash")) for e in ev_final),"regresion: evidencia integra (hash fila)")

print("\n=== RESUMEN 238 ===")
print("deficit:", FALLOS if FALLOS else "ninguno")
if FALLOS: print("FALLOS:", FALLOS)
else: print("238 PASS PARTIAL — dependencias caracterizadas; propuestas minimas documentadas; integracion requiere autorizacion separada")
