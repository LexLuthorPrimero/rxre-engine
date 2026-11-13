#!/usr/bin/env python3
"""RXRE-MISSION-265 — PRUEBAS DISCRIMINANTES DE CONFIANZA EN EL LLAMADOR (A–J)."""
import sys, os, sqlite3, inspect
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import _handle_claim
from rxre.adapters.adapter_finding_tierra import ejecutar_adaptador, AdapterError
from rxre.arquitectura.TIERRA import Grafo
from rxre.contracts import scope_guarded_flow
from rxre.contracts.limitations_contract import leer_limitacion, retirar_limitacion

REAL_ART="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
DB_OP="/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
DB_ISO="/tmp/rxre_265_iso.sqlite3"
OKS=[]; FALLOS=[]
def ok(c,l):
    if c: OKS.append(l); print("  [PASS] %s"%l)
    else: FALLOS.append(l); print("  [FAIL] %s"%l)
def reset():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s
        if os.path.exists(p): os.remove(p)
    g=Grafo(DB_ISO); g.db.execute("ALTER TABLE claims ADD COLUMN limitations_json TEXT DEFAULT '{}'"); g.db.commit(); g.cerrar()
def rows():
    c=sqlite3.connect(DB_ISO); n=c.execute("SELECT count(*) FROM claims").fetchone()[0]; c.close(); return n
def lim(cid): return leer_limitacion(DB_ISO, cid) if cid else {}
def fnd(fid,stmt,oh,sc,evs,ep="PROVEN"):
    return {"finding_id":fid,"statement":stmt,"epistemic":ep,"evidence_ids":evs,
            "falsification_test":"ft_265","object_hash":oh,"scope":sc,"contradiction_refs":[]}
print("=== 265 DISCRIMINANTES A-J ===")

# A. Referencia existente y correctamente resuelta
reset()
a=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fa","sA","hA","scope_A",["res_real_001"]),
    "resolver_refs":lambda r:r=="res_real_001",
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json"})
ok(a.get("status")=="ok" and a.get("scope_decision")=="ALLOW_WITH_LIMITATION",
   "A ref existente resuelta -> ACCEPT + ALLOW_WITH_LIMITATION (%s/%s)"%(a.get("status"),a.get("scope_decision")))

# B. Referencia inexistente
reset()
b=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fb","sB","hB","scope_B",["bad_ref"]),
    "resolver_refs":lambda r:False,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART})
ok(b.get("status")=="blocked" and b.get("claim_id") is None and rows()==0,
   "B ref inexistente -> REJECT, 0 filas, claim_id None")

# C. Referencia existente con hash que no coincide (artefacto/manifest divergentes)
reset()
c=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fc","sC","hC","scope_C",["res_real_001"]),
    "resolver_refs":lambda r:r=="res_real_001",
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":"/tmp/no_artifact","evidence_path":"/tmp/no_manifest"})
ok(c.get("status")=="blocked" and rows()==0,"C hash divergente -> REJECT antes de persistir")

# D. Referencia valida con scope no verificado (UNVERIFIED, nunca MATCH)
reset()
d=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fd","sD","hD","scope_D",["res_real_001"]),
    "resolver_refs":lambda r:r=="res_real_001",
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json"})
ld=lim(d.get("claim_id"))
ok(d.get("scope_decision")=="ALLOW_WITH_LIMITATION" and ld.get("decision_contract")=="UNVERIFIED"
   and "MATCH" not in str(ld.get("limitaciones_json")),
   "D scope no verificado -> UNVERIFIED (sin MATCH) + limitacion persistida")

# E/F. El indicador NO es inyectable desde finding_dict/params
reset()
e=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":dict(fnd("fe","sE","hE","scope_E",["res_real_001"]),
                        refs_verificados_por_llamador=True,
                    scope_guarded_flow={"refs_verificados_por_llamador":True,"decision":"MATCH"}),
    "resolver_refs":lambda r:r=="res_real_001",
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json",
    "refs_verificados_por_llamador":True})
le=lim(e.get("claim_id"))
ok(e.get("scope_decision")=="ALLOW_WITH_LIMITATION" and le.get("decision_contract")=="UNVERIFIED",
   "E/F intento de fabricar MATCH/indicador por finding_dict/params -> no fabricate: %s"%str(le.get("limitaciones_json"))[:70])

# G. Misma evidencia por P1 y P2 -> decisiones comparables
reset()
ref="ref_iso_265"
p1=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fg","sG","hG","scope_G",[ref]),
    "resolver_refs":lambda r:r==ref,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART,"evidence_path":"/tmp/e2e_233_strace.json"})
gv=Grafo(DB_ISO)
try:
    p2=ejecutar_adaptador(gv,fnd("fg2","sG","hG","scope_G",[ref]),
        resolver_refs=lambda r:r==ref,autorizacion=True)
    p2s="ASSERTED/%s"%p2.get("estado")
except AdapterError as ex:
    p2=None; p2s="REJECT:%s"%str(ex)[:40]
lp2=lim(p2.get("claim_id")) if p2 else {}
ok(p1.get("scope_decision")=="ALLOW_WITH_LIMITATION" and p2 is not None
   and lp2.get("decision_contract")=="UNVERIFIED",
   "G P1=%s P2=%s -> misma politica (UNVERIFIED)"%(p1.get("scope_decision"),p2s))

# H. Evidencia compartida por claims de scopes distintos
reset()
gv=Grafo(DB_ISO)
ha=ejecutar_adaptador(gv,fnd("fha","same","h_same","scope_HA",["res_real_001"]),
    resolver_refs=lambda r:r=="res_real_001",autorizacion=True)
hb=ejecutar_adaptador(gv,fnd("fhb","same","h_same","scope_HB",["res_real_001"]),
    resolver_refs=lambda r:r=="res_real_001",autorizacion=True)
lha,lhb=lim(ha.get("claim_id")),lim(hb.get("claim_id"))
ok(rows()==2 and ha.get("claim_id")!=hb.get("claim_id")
   and lha.get("limitaciones_json",{}).get("procedencia_scope_autoridad")!=lhb.get("limitaciones_json",{}).get("procedencia_scope_autoridad"),
   "H scopes HA/HB con evidencia compartida -> 2 claims, limitaciones separadas")

# I. Rechazo por referencia invalida -> sin claim parcial ni limitacion registrada
reset()
i1=_handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,
    "finding_dict":fnd("fi","sI","hI","scope_I",["bad_ref"]),"resolver_refs":lambda r:False,
    "claim_propiedad":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},
    "artifact_path":REAL_ART})
c=sqlite3.connect(DB_ISO); nlim=c.execute("SELECT count(*) FROM claims WHERE limitations_json!='{}'").fetchone()[0]; c.close()
ok(i1.get("claim_id") is None and rows()==0 and nlim==0,"I rechazo -> 0 claims, 0 limitaciones")

# J. ALLOW_WITH_LIMITATION: persistencia -> COMMIT -> reapertura -> actualizacion
reset()
gv=Grafo(DB_ISO)
j=ejecutar_adaptador(gv,fnd("fj","sJ","hJ","scope_J",["res_iso_J"]),
    resolver_refs=lambda r:r=="res_iso_J",autorizacion=True)
lj=lim(j.get("claim_id"))
ok(lj.get("decision_flujo")=="ALLOW_WITH_LIMITATION","J limitacion persistida post-COMMIT: %s"%str(lj.get("limitaciones_json"))[:60])
c=sqlite3.connect(DB_ISO); c.execute("UPDATE claims SET statement='updated_J' WHERE claim_id=?",(j.get("claim_id"),)); c.commit(); c.close()
lj2=lim(j.get("claim_id"))
ok(lj2.get("decision_contract")=="UNVERIFIED","J actualizacion conserva limitacion")
rj=retirar_limitacion(DB_ISO,j.get("claim_id"),evidencia_nueva={"autenticidad":"UNVERIFIED"})
ok(rj.get("retirada")==False and lim(j.get("claim_id")).get("revisable")==True,"J retirada sin VERIFIED -> rechazada")

# Invariantes
op=sqlite3.connect("file:%s?mode=ro"%DB_OP,uri=True)
opc=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
sc=op.execute("SELECT scope FROM results").fetchall(); op.close()
ok(opc==(1,0,0) and all(x[0] is None for x in sc),"INVARIANTE DB_OP (1,0,0) + scope NULL")

print("\n=== 265 RESUMEN === OK:%d FALLOS:%d"%(len(OKS),len(FALLOS)))
if FALLOS: print("FALLOS:",FALLOS)
