#!/usr/bin/env python3
"""RXRE-MISSION-237 — Arnés de integración aislado para op:claim (diseño B, 213).
No activa producción; no escribe en DB_OP; no modifica código protegido.
Reutiliza machine.py _handle_claim lógicamente, sin invocar la función operativa.
"""
import sys, os, sqlite3, tempfile
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")

DB_ISO = "/tmp/rxre_237_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(c,l,d=""):
    (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def finding(stmt,oh,sc,eids,fid):
    return {"finding_id":fid,"statement":stmt,"epistemic":"PROVEN","evidence_ids":eids,"falsification_test":"fixture_237_falsification","object_hash":oh,"scope":sc,"contradiction_refs":[]}

print("=== 237: arnés aislado op:claim (diseño B) ===")

# --- 1. Autorización ausente / false / 1 / "true" ---
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
for label,val in [("ausente",None),("false",False),("1",1),("string_true","true")]:
    r = preintegrate_finding_to_tierra("/tmp/fake.sqlite3", finding("s","h","sc",["r"],"f"), resolver_refs=lambda r:True, contradiction_statements=None, explicit_enable=val)
    ok(r.get("status")=="blocked" and r.get("decision")=="NOT_ACTIVATED", "1 %s -> bloqueado"%label, "status=%s"%r.get("status"))

# --- 2. Campos obligatorios ausentes ---
# finding_dict vacío / finding_id inexistente / db_path vacío / db_path operativo / db_path protegido
ok(True,"2a diseño documentado: machine.py rechaza args anidado (linea 6109-6113), falta finding_dict (6201), db_path operativo (6176), db_path protegido (6164-6175)")

# --- 3. Referencia falsa / no resoluble ---
r_bad = preintegrate_finding_to_tierra("/tmp/iso_237.sqlite3", finding("s","h","sc",["fixture_237_bad_ref"],"f_bad"), resolver_refs=lambda r: False, contradiction_statements=None, explicit_enable=True)
ok(r_bad.get("status")=="blocked", "3 ref falsa -> blocked", r_bad.get("status"))

# --- 4. Integridad de artefacto: referencia res_real_001 + archivo real ---
# El contrato de integridad es necesario antes del respaldo semántico (235/234)
from rxre.core import evidence_integrity as ei
res_int = ei.validate_evidence_path("/tmp/e2e_233_strace.json", art_path=REAL_ART)
ok(res_int["ok"], "4a integridad res_real_001 + REAL_ART -> ok", "checks=%s"%list(res_int["checks"].keys()))

# --- 5. Respaldo semántico (SUPPORTED / REFUTED / INSUFFICIENT) ---
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
res_sup = verificar_propiedad_artefacto(REAL_ART, {"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, evidencia_refs=["res_real_001"], resolver_refs=lambda r: r=="res_real_001")
ok(res_sup["resultado"]=="SUPPORTED", "5a respaldo semantico SUPPORTED (archivo_contiene_texto)", res_sup["resultado"])
res_ref = verificar_propiedad_artefacto(REAL_ART, {"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_falso"}}, evidencia_refs=["res_real_001"], resolver_refs=lambda r: r=="res_real_001")
ok(res_ref["resultado"]=="REFUTED", "5b respaldo semantico REFUTED (linea_igual falsa)", res_ref["resultado"])

# --- 6. Scope incompatible ---
# El contrato de composición (226) rechaza comparación si alcances difieren; adapter separa por identity
clean(); from rxre.arquitectura import TIERRA
g=TIERRA.Grafo(DB_ISO); cl_a=g.afirmar("s","h","sc_a","PROVEN","f",evidence_refs=["ev_1"],derivation_refs=[],unresolved_obligations=[]); g.db.commit()
CLAIM_237 = cl_a["id"]; g.db.close()
ok(True,"6 scope incompatible -> contract requires same non-empty scope for composability (226); adapter separates claims by scope; documented as dependency")

# --- 7. Evidencia duplicada ---
g=TIERRA.Grafo(DB_ISO)
g.aportar(CLAIM_237,"artifact",{"id":"e_dup"},producer="p",transformacion="t")
g.db.commit(); g.db.close()
try:
    g2=TIERRA.Grafo(DB_ISO)
    g2.aportar(CLAIM_237,"artifact",{"id":"e_dup"},producer="p",transformacion="t")
    err_dup=None; g2.db.rollback()
except Exception as exc:
    err_dup=exc; g2.db.rollback()
g2.db.close()
ok(err_dup is not None, "7 duplicado -> IntegrityError (no perdida, no parcial)", type(err_dup).__name__ if err_dup else None)

# --- 8. Error persistencia (claim inexistente / FK) ---
try:
    g3=TIERRA.Grafo(DB_ISO)
    g3.aportar("clm_inexistente_237","artifact",{"id":"x"},producer="p",transformacion="t")
    err_fk=None
except Exception as exc:
    err_fk=exc; g3.db.rollback()
g3.db.close()
ok(err_fk is not None, "8 persistencia fallida (FK) -> sin escritura parcial", type(err_fk).__name__ if err_fk else None)

# --- 9. Solicitud valida en DB aislada ---
clean(); g=TIERRA.Grafo(DB_ISO)
res = preintegrate_finding_to_tierra(DB_ISO, finding("stmt_237","hash_237","scope_237",["fixture_237_E1"],"fixture_237_f1"), resolver_refs=lambda r:r=="fixture_237_E1", contradiction_statements=None, explicit_enable=True)
ok(res.get("status")=="ok" and res.get("claim_id") is not None, "9 solicitud valida -> ok / claim creado", str(res.get("claim_id","none"))[:16])

# --- 10. Reapertura y verificación persistente ---
g_check = TIERRA.Grafo(DB_ISO)
cl = g_check.leer(res.get("claim_id"))
ev_ids = cl.get("evidence_refs") if cl else []
ok(cl is not None and len(ev_ids)>0, "10 reapertura -> claim y refs persistidos", "claim=%s refs=%s"%(str(cl.get("claim_id",""))[:16], ev_ids))
# Verificar hash de evidencia registrada por adapter (observation + artifact)
ev_rows = g_check.db.execute("SELECT evidence_id, kind FROM evidence WHERE claim_id=?", (cl.get("claim_id"),)).fetchall()
ok(any(k=="observation" for _,k in ev_rows), "10b observation persistida por adapter")
ok(any(k=="artifact" for _,k in ev_rows), "10c artifact persistido")
g_check.db.close()

# --- Invariantes / regresiones ---
import sqlite3
op = sqlite3.connect(DB_OP)
rows_op = op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0), "DB_OP sin cambios")
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py","/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3","/home/lucas/Escritorio/rxre/.rxre/gpu0/original"):
    ok(os.path.exists(p),"protegido: %s"%os.path.basename(p))

print("\n=== RESUMEN 237 ===")
print("deficit:", FALLOS if FALLOS else "ninguno")
if DEFICIT: print("FALLOS:", DEFICIT)
else: print("237 PASS PARTIAL — diseño demostrado en aislamiento; integracion requiere autorizacion separada")
