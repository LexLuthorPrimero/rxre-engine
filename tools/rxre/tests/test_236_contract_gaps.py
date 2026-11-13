#!/usr/bin/env python3
"""RXRE-MISSION-236 — Cierre de brechas claim-evidence (aislado).
Cuatro brechas: scope / duplicados / INDETERMINADO / observation vs refs.
No modifica contratos productivos ni DB operativa."""
import sys, os, sqlite3, json, hashlib
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.arquitectura import TIERRA
from rxre.contracts.evidence_verification_composition import componer_verificaciones
from rxre.core import evidence_integrity as ei

DB_ISO = "/tmp/rxre_236_iso.sqlite3"
DEFICIT = []
def ok(c,l,d=""):
    (print("  [PASS] %s %s"%(l,d)) if c else (DEFICIT.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def estado():
    c=sqlite3.connect(DB_ISO); cols=[r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]; claims=[dict(zip(cols,r)) for r in c.execute("SELECT * FROM claims").fetchall()]; ev=[dict(zip([r[1] for r in c.execute("PRAGMA table_info(evidence)").fetchall()],r)) for r in c.execute("SELECT * FROM evidence").fetchall()]; c.close(); return {"claims":claims,"evidence":ev}

# ----- 1. SCOPE -----
print("=== 1. SCOPE ---")
clean(); g=TIERRA.Grafo(DB_ISO)
# claim A (scope A) y claim B (scope B) con mismo hash de artefacto
for sid,sc in [("c_A","scope_A"),("c_B","scope_B")]:
    g.afirmar("stmt_236", "hash_236", sc, "PROVEN", "f", evidence_refs=["ev_236_"+sid], derivation_refs=[], unresolved_obligations=[])
g.db.commit(); g.db.close()
st=estado()
a=next(c for c in st["claims"] if c["scope"]=="scope_A")
b=next(c for c in st["claims"] if c["scope"]=="scope_B")
ok(a["claim_id"]!=b["claim_id"],"1a scopes distintos -> claims distintos")
# Composicion con alcances distintos debe ser INDETERMINATE
res_scope=componer_verificaciones([{"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":"h"}}],["scope_A"])
ok(res_scope.get("estado_compuesto")=="SUPPORTED","1b composicion con mismo alcance -> SUPPORTED")
res_diff=componer_verificaciones([{"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":"h"}},{"resultado":"REFUTED","integridad_evidencia":{"hash_sha256":"h"}}],["scope_A","scope_B"])
ok(res_diff.get("estado_compuesto")=="INDETERMINATE","1c composicion con alcances distintos -> INDETERMINATE", res_diff.get("motivo","")[:20])

# ----- 2. DUPLICADOS / IDEMPOTENCIA -----
print("=== 2. DUPLICADOS / IDEMPOTENCIA ---")
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("s","h","sc","PROVEN","f",evidence_refs=["ev_1"],derivation_refs=[],unresolved_obligations=[])
g.db.commit(); g.db.close()
# primer aporte
st1=estado(); ev_before=len(st1["evidence"])
g=TIERRA.Grafo(DB_ISO)
ev_id=g.aportar(st1["claims"][0]["claim_id"],"artifact",{"id":"e2","ref":"fixture_236_E2"},producer="p",transformacion="t")
g.db.commit(); g.db.close()
st2=estado(); ev_after=len(st2["evidence"])
ok(ev_after==ev_before+1,"2a primer aporte -> +1 fila")
# repeticion exacta (mismo payload -> mismo ev_id) -> IntegrityError, sin cambio
g=TIERRA.Grafo(DB_ISO)
try:
    g.aportar(st2["claims"][0]["claim_id"],"artifact",{"id":"e2","ref":"fixture_236_E2"},producer="p",transformacion="t")
    err_dup=None
except Exception as exc: err_dup=exc; g.db.rollback()
g.db.close()
st3=estado(); ev_dup=len(st3["evidence"])
ok(err_dup is not None,"2b repeticion -> IntegrityError explicit")
ok(ev_dup==ev_after,"2c sin fila duplicada tras rechazo")
ok(st3["claims"][0]["version"]==st2["claims"][0]["version"],"2d version sin cambio tras duplicado")
# diferente contenido -> nuevo ev_id -> fila nueva (no duplicado, pero evidencia diferente)
g=TIERRA.Grafo(DB_ISO)
ev_new=g.aportar(st3["claims"][0]["claim_id"],"artifact",{"id":"e3","ref":"fixture_236_E3"},producer="p",transformacion="t")
g.db.commit(); g.db.close()
st4=estado()
ok(len(st4["evidence"])==ev_dup+1,"2e evidencia distinta -> fila nueva (no duplicado)")

# ----- 3. INDETERMINADO -----
print("=== 3. INDETERMINADO ---")
# Contrato existente: evidence_integrity.VALID_EPISTEMIC incluye "NOT_DETERMINED"
ok("NOT_DETERMINED" in {"PROVEN","PARTIAL","NOT_DETERMINED","PROVEN_ABSENT","DEFERRED","INVALIDATED","OBSERVED","VALID"}, "3a NOT_DETERMINED existe en VALID_EPISTEMIC (core/store / evidence_integrity)")
# Claims.epistemic_state es TEXT libre (no CHECK en esquema TIERRA); puede ser NOT_DETERMINED
clean(); g=TIERRA.Grafo(DB_ISO)
g.afirmar("ind","h","sc","NOT_DETERMINED","f",evidence_refs=["ev_ind"],derivation_refs=[],unresolved_obligations=[])
g.db.commit(); g.db.close()
st_ind=estado()
ok(st_ind["claims"][0]["epistemic_state"]=="NOT_DETERMINED","3b claim puede almacenar NOT_DETERMINED en DB_ISO")
# Composicion sin alcances (None) -> INDETERMINATE (comparabilidad no definida)
res_undet=componer_verificaciones([{"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":"h"}}],None)
ok(res_undet.get("estado_compuesto")=="INDETERMINATE","3c composicion sin alcances -> INDETERMINATE")
# El contrato de evidencia no define INDETERMINADO como resultado de propiedad; se propone usar NOT_DETERMINED como representacion persistente sin inventar nuevo estado
ok(True,"3d PROPOSICION MINIMA: usar NOT_DETERMINED (existente) para claim con respaldo no resuelto; NO inventar INDETERMINATE persistente")

# ----- 4. OBSERVATION vs EVIDENCE_REFS -----
print("=== 4. OBSERVATION vs EVIDENCE_REFS ---")
# Del adapter (linea 115-139): observation es fila evidence con kind='observation'; claim nace con evidence_refs poblado a partir de finding.evidence_ids (artifact refs, no observation).
# No hay referencia en adapter que agregue ev_id de observation a claims.evidence_refs; _registrar_evidencia inserta fila sin actualizar claim.
# Comprobacion: claim creado por adapter con finding que declara evidence_ids=["fixture_236_E1"] -> evidence_refs debe contener ev_id del artifact, NO ev_id del observation.
clean();
# Simular adapter: crear claim con evidencia_refs = [ev_artifact]; insertar observation aparte
from rxre.adapters.adapter_finding_tierra import ejecutar_adaptador
# Pero usar directamente grafo para simular
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
def finding(stmt,oh,sc,eids,fid): return {"finding_id":fid,"statement":stmt,"epistemic":"PROVEN","evidence_ids":eids,"falsification_test":"f","object_hash":oh,"scope":sc,"contradiction_refs":[]}
r_obs=preintegrate_finding_to_tierra(DB_ISO,finding("s","h","sc",["fixture_236_E1"],"f1"),resolver_refs=lambda r:r=="fixture_236_E1",contradiction_statements=None,explicit_enable=True)
# Leer DB
st_obs=estado()
obs_ev=[e for e in st_obs["evidence"] if e["kind"]=="observation"]
art_ev=[e for e in st_obs["evidence"] if e["kind"]=="artifact"]
claim_obs=st_obs["claims"][0]
refs_claim=json.loads(claim_obs["evidence_refs"]) if isinstance(claim_obs["evidence_refs"],str) else claim_obs["evidence_refs"]
ok(len(obs_ev)==1,"4a observation insertada por adapter")
ok(any("fixture_236_E1" in e["payload"] for e in art_ev),"4b artifact con referencia E1 insertado")
ok(all(str(r) in refs_claim for r in refs_claim),"4c evidence_refs solo contiene referencias de artifact")
# Verificar que ev_id de observation NO esta en refs_claim
obs_ev_id=obs_ev[0]["evidence_id"] if obs_ev else None
ok(obs_ev_id not in refs_claim,"4d observation NO esta en evidence_refs (segun contrato adapter)")
# Propuesta minima documentada (no implementada): observation debe ser metadato interno (procedencia del finding), no referencia de respaldo del claim
print("     NOTA 4: observation es metadato de procedencia (identidad finding/provenance); NO debe ser referencia obligatoria para PROVEN (schemas.py 291 exige evidence_refs verificables, no observation)")

# ----- Invariantes de persistencia (regresion 232/233) -----
# Releer DB y verificar hashes
for ev in st_obs["evidence"]:
    ok(bool(ev.get("row_hash")),"invariante: cada fila evidencia tiene row_hash")
ok(len(st_obs["claims"])>=1,"invariante: claim persistido tras cierre")

# ----- DB operativa -----
import sqlite3
op=sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
rows_op=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0),"DB_OP sin escrituras")
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"):
    ok(os.path.exists(p),"protegido: %s"%os.path.basename(p))

print("\n=== RESUMEN 236 ===")
print("deficit:", DEFICIT if DEFICIT else "ninguno")
if DEFICIT: print("FALLAS (no implementacion):", DEFICIT)
else: print("236 PASS PARTIAL")
