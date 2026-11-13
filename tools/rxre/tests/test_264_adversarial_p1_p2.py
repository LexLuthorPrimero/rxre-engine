#!/usr/bin/env python3
"""RXRE-MISSION-264 — MATRIZ ADVERSARIAL P1/P2 (coherencia + persistencia). Rutas reales aisladas."""
import sys, os, sqlite3, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import _handle_claim
from rxre.adapters.adapter_finding_tierra import ejecutar_adaptador, AdapterError
from rxre.arquitectura.TIERRA import Grafo
from rxre.contracts.limitations_contract import leer_limitacion, retirar_limitacion

REAL_ART="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
DB_OP="/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
DB_ISO="/tmp/rxre_264_iso.sqlite3"
OKS=[]; FALLOS=[]
def ok(c,l):
    if c: OKS.append(l); print("  [PASS] %s"%l)
    else: FALLOS.append(l); print("  [FAIL] %s"%l)
def reset():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s
        if os.path.exists(p): os.remove(p)
    g=Grafo(DB_ISO)   # esquema real TIERRA
    g.db.execute("ALTER TABLE claims ADD COLUMN limitations_json TEXT DEFAULT '{}'")
    g.db.commit(); g.cerrar()
def rows():
    c=sqlite3.connect(DB_ISO); n=c.execute("SELECT count(*) FROM claims").fetchone()[0]; c.close(); return n
def lim(cid):
    return leer_limitacion(DB_ISO, cid) if cid else {}
def finding(fid,stmt,oh,sc,evs,ep="PROVEN"):
    return {"finding_id":fid,"statement":stmt,"epistemic":ep,"evidence_ids":evs,
            "falsification_test":"ft_264","object_hash":oh,"scope":sc,"contradiction_refs":[]}
def resolver(r): return r=="res_real_001"

print("=== 264 ADVERSARIAL P1/P2 ===")

# H5 + 14: rechazo -> claim_id None + motivo + 0 filas
reset()
r5=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":finding("f5","s","h","sc",["bad_ref"]),"resolver_refs":lambda r:False,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART})
ok(r5.get("claim_id") is None and rows()==0 and r5.get("motivo"),
   "H5/14 rechazo -> claim_id=None, motivo conservado, 0 filas: %s"%str(r5.get("motivo"))[:45])

# H7: autorizacion operativa independiente de la autoridad semantica
reset()
r7=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":1,"db_path":DB_ISO,
    "finding_dict":finding("f7","s","h","sc",["res_real_001"]),"resolver_refs":resolver,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART})
ok(r7.get("status")=="blocked" and r7.get("decision")=="NOT_ACTIVATED" and rows()==0,
   "H7 autorizacion=1 (no exacta) -> NOT_ACTIVATED, 0 filas")

# H1: coherencia P1 vs P2 sobre la MISMA entrada (ref verificada por resolver, ausente en DB_OP)
reset()
ref_shared="ref_iso_not_in_db_op"
p1=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":finding("f1","stmt_shared","oh_shared","scope_A",[ref_shared]),
    "resolver_refs":lambda r:r==ref_shared,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json"})
gv=Grafo(DB_ISO)
try:
    p2=ejecutar_adaptador(gv,finding("f2","stmt_shared","oh_shared","scope_A",[ref_shared]),
        resolver_refs=lambda r:r==ref_shared, autorizacion=True)
    p2_status="ASSERTED"
except AdapterError as e:
    p2=None; p2_status="REJECT:%s"%str(e)[:60]
print("  H1 P1(machine.py) -> %s/%s ; P2(adapter) -> %s"%(p1.get("status"),p1.get("decision"),p2_status))
H1_COHERENT = (p1.get("status")=="blocked") == (p2 is None)
ok(H1_COHERENT, "H1 P1 y P2 coinciden en decision para la misma entrada")

# H2 + 12: rechazo por referencia invalida -> 0 filas, sin escritura parcial
reset()
r12=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":finding("f12","s","h","sc",["bad_ref"]),"resolver_refs":lambda r:False,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART})
ok(r12.get("status")=="blocked" and rows()==0,"H2/12 rechazo previo a escritura: 0 filas")

# H3: UNVERIFIED nunca promovido a MATCH/PROVEN por la segunda pasada (adapter)
reset()
gv=Grafo(DB_ISO)
a3=ejecutar_adaptador(gv,finding("f3a","s3","oh3","scope_U",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
l3=lim(a3.get("claim_id"))
ok(l3.get("decision_contract")=="UNVERIFIED" and l3.get("decision_flujo")=="ALLOW_WITH_LIMITATION",
   "H3 UNVERIFIED -> ALLOW_WITH_LIMITATION, sin MATCH: %s"%str(l3.get("limitaciones_json",{})))
c=sqlite3.connect(DB_ISO); epi=c.execute("SELECT epistemic_state FROM claims WHERE claim_id=?",(a3.get("claim_id"),)).fetchone()[0]; c.close()
ok(epi=="PROVEN","H3 estado epistemico preservado tal cual (no promovido por el contrato): %s"%epi)

# H4 + 11: persistencia y reapertura
reset()
gv=Grafo(DB_ISO)
a4=ejecutar_adaptador(gv,finding("f4","s4","oh4","scope_U",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
l4=lim(a4.get("claim_id"))
ok(l4.get("existe")==True,"H4 limitacion persistida tras reabrir: %s"%str(l4.get("limitaciones_json")))

# H6: misma evidencia, scopes distintos -> claims y limitaciones separadas
reset()
gv=Grafo(DB_ISO)
a6=ejecutar_adaptador(gv,finding("f6a","same","oh_same","scope_A",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
b6=ejecutar_adaptador(gv,finding("f6b","same","oh_same","scope_B",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
ok(rows()==2 and a6.get("claim_id")!=b6.get("claim_id"),"H6 dos scopes -> 2 claims distintos")
la,lb=lim(a6.get("claim_id")),lim(b6.get("claim_id"))
ok(la.get("limitaciones_json",{}).get("procedencia_scope_autoridad")!=lb.get("limitaciones_json",{}).get("procedencia_scope_autoridad"),
   "H6 limitaciones separadas por scope (sin compatibilidad inferida)")

# H8: adapter no bloquea legitimo; scope declarado no es autoridad
reset()
gv=Grafo(DB_ISO)
a8=ejecutar_adaptador(gv,finding("f8","legit","oh8","scope_declarado",["res_real_001"]),
    resolver_refs=lambda r:r=="res_real_001",autorizacion=True)
ok(a8 is not None and rows()==1,"H8 adapter no bloquea afirmacion legitima (1 fila)")
l8=lim(a8.get("claim_id"))
ok(l8.get("decision_contract") in ("UNVERIFIED",None),"H8 scope declarado NO es autoridad: %s"%str(l8.get("limitaciones_json",{}))[:80])

# 8: actualizacion no borra limitacion
c=sqlite3.connect(DB_ISO); c.execute("UPDATE claims SET statement='updated_264' WHERE claim_id=?",(a8.get("claim_id"),)); c.commit(); c.close()
l8b=lim(a8.get("claim_id"))
ok(l8b.get("existe")==True and l8b.get("decision_contract")==l8.get("decision_contract"),"8 actualizacion conserva limitacion")

# 9: retirada sin respaldo -> rechazada
r9=retirar_limitacion(DB_ISO,a8.get("claim_id"),evidencia_nueva={"autenticidad":"UNVERIFIED"})
ok(r9.get("retirada")==False and lim(a8.get("claim_id")).get("revisable")==True,"9 retirada sin VERIFIED -> rechazada")

# 10: retirada con respaldo VERIFIED -> revisada, no promoted
r10=retirar_limitacion(DB_ISO,a8.get("claim_id"),evidencia_nueva={"autenticidad":"VERIFIED","hash":"h"})
l10=lim(a8.get("claim_id"))
ok(r10.get("retirada")==True and l10.get("revisable")==False and l10.get("limitaciones_json",{}).get("retirada_resultado")=="LIMITACION_REVISADA",
   "10 retirada con VERIFIED -> LIMITACION_REVISADA, revisable=False")

# 13: idempotencia
reset()
gv=Grafo(DB_ISO)
a13=ejecutar_adaptador(gv,finding("f13","idem","oh13","scope_U",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
b13=ejecutar_adaptador(gv,finding("f13","idem","oh13","scope_U",["ref_iso"]),
    resolver_refs=lambda r:r=="ref_iso",autorizacion=True)
c=sqlite3.connect(DB_ISO); n13=c.execute("SELECT count(*) FROM claims").fetchone()[0]; c.close()
ok(n13==1 and a13.get("claim_id")==b13.get("claim_id"),"13 repeticion -> 1 claim, mismo claim_id (%d)"%n13)

# 2: P1 con autorizacion y scope UNVERIFIED -> limitacion persistida
reset()
r2=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":finding("f2","s2","oh2","scope_264",["res_real_001"]),"resolver_refs":resolver,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json"})
l2=lim(r2.get("claim_id"))
ok(r2.get("scope_decision")=="ALLOW_WITH_LIMITATION" and l2.get("decision_flujo")=="ALLOW_WITH_LIMITATION",
   "2 P1 UNVERIFIED -> limitacion persistida: %s"%str(l2.get("limitaciones_json"))[:90])

# Invariantes
op=sqlite3.connect("file:%s?mode=ro"%DB_OP,uri=True)
opc=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(opc==(1,0,0),"INVARIANTE DB_OP (1,0,0)")

print("\n=== 264 RESUMEN === OK:%d FALLOS:%d"%(len(OKS),len(FALLOS)))
if FALLOS: print("FALLOS:",FALLOS)
print("H1 divergencia observada:", not H1_COHERENT)
