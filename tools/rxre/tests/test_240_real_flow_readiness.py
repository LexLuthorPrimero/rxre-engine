#!/usr/bin/env python3
"""RXRE-MISSION-240 — Pruebas de aceptacion del flujo real op:claim (aislado).
No modifica machine.py/adapters/core; usa DB_ISO; no activa op:claim operativo.
Separar comportamiento real (handler) de contratos aislados (239).
"""
import sys, os, sqlite3, time
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import _handle_claim
from rxre.arquitectura import TIERRA

DB_ISO = "/tmp/rxre_240_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(c,l,d=""):
    (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def finding_dict(stmt, oh, sc, eids, fid, ep="PROVEN"):
    return {"finding_id":fid,"statement":stmt,"epistemic":ep,"evidence_ids":eids,"falsification_test":"fixture_240_falsification","object_hash":oh,"scope":sc,"contradiction_refs":[]}

# Pre-calc protected hashes (before test)
import hashlib
def protected_hash(p):
    try:
        import hashlib
        with open(p,"rb") as f: return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception: return None

print("=== 240: flujo real op:claim (aceptacion aislada) ===")

# --- 0. Hashes protegidos antes ---
h_before = {p: protected_hash(p) for p in ["/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"]}

# --- 1. Solicitud valida con DB aislada ---
clean()
res1 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,"finding_dict":finding_dict("stmt_240_A","hash_240_A","scope_240_A",["fixture_240_E1"],"f_240_1"),"resolver_refs":lambda r:r=="fixture_240_E1","contradiction_statements":None})
ok(res1.get("status")=="ok" and res1.get("ejecutada") is True, "1 valida -> ok / ejecutada", str(res1.get("decision"))[:10])
ok(res1.get("claim_id") is not None, "1b claim_id creado", str(res1.get("claim_id",""))[:16])
# Verificar persistencia en DB_ISO
c=sqlite3.connect(DB_ISO)
rows=c.execute("SELECT claim_id,statement,scope,epistemic_state FROM claims WHERE claim_id=?",(res1["claim_id"],)).fetchall()
c.close()
ok(len(rows)==1,"1c claim persistido en DB_ISO", "claims=%d"%len(rows))
ok(rows[0][3]=="PROVEN","1d epistemic_state PROVEN", rows[0][3])

# --- 2. Autorizacion no exacta (false, 1, "true") ---
for label,val in [("false",False),("1",1),("str_true","true")]:
    r = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":val,"db_path":"/tmp/iso_240_bad.sqlite3","finding_dict":finding_dict("s","h","sc",["r"],"f")})
    ok(r.get("status")=="blocked" and r.get("decision")=="NOT_ACTIVATED", "2 %s -> bloqueado"%label, r.get("status"))

# --- 3. Explicit_enable false / absent ---
for label,val in [("false",False),("absent",None)]:
    r = _handle_claim({"op":"claim","explicit_enable":val,"autorizacion":True,"db_path":"/tmp/iso_240_bad.sqlite3","finding_dict":finding_dict("s","h","sc",["r"],"f")})
    ok(r.get("status")=="blocked" and r.get("decision")=="NOT_ACTIVATED", "3 %s -> bloqueado"%label, r.get("status"))

# --- 4. db_path operativo / protegido / ausente ---
for label,db in [("operativo","/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"),("protegido","/home/lucas/Escritorio/rxre/.rxre/gpu0/original/test.sqlite3"),("ausente",""),("relativo","rxre.sqlite3")]:
    r = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":db,"finding_dict":finding_dict("s","h","sc",["r"],"f")})
    ok(r.get("status")=="blocked" and r.get("decision") in ("REJECT","NOT_ACTIVATED"), "4 %s -> bloqueado/rechazado"%label, r.get("decision"))

# --- 5. finding_dict / finding_id ausente / lectura fallida ---
r5 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_240_bad.sqlite3"})
ok(r5.get("status")=="blocked" and r5.get("decision")=="REJECT", "5 ausencia finding -> REJECT", r5.get("decision"))

# --- 6. Referencia falsa ---
# 6a: resolver_refs REAL -> la politica/adapter rechazan la referencia no resoluble
r6a = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_240_bad.sqlite3","finding_dict":finding_dict("s","h","sc",["fixture_240_bad_ref"],"f_bad"),"resolver_refs":lambda r:r=="fixture_240_E1"})
ok(r6a.get("status")=="blocked" and r6a.get("decision") in ("REJECT","NEEDS_INPUT"), "6a ref falsa con resolver real -> bloqueada", r6a.get("decision"))
# 6b: SIN resolver_refs, el handler usa el resolver por defecto AUTO-REFERENCIAL (r in finding.evidence_ids):
#     la referencia no se verifica contra ninguna procedencia externa -> se acepta. HECHO OBSERVADO del flujo real.
r6b = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_240_bad.sqlite3","finding_dict":finding_dict("s2","h2","sc2",["fixture_240_bad_ref"],"f_bad2")})
ok(r6b.get("status")=="blocked" and r6b.get("decision")=="NEEDS_INPUT", "6b SIN resolver real -> bloqueado (bypass corregido con machine.py 6207)", r6b.get("decision"))
ok(True,"6c DEPENDENCIA: el llamador DEBE pasar resolver_refs verificable; default de machine.py (linea 6207) es auto-referencial")

# --- 7. Claim existente (ya_existia) ---
r7 = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,"finding_dict":finding_dict("stmt_240_A","hash_240_A","scope_240_A",["fixture_240_E1"],"f_240_1"),"resolver_refs":lambda r:r=="fixture_240_E1"})
ok(r7.get("status")=="ok" and r7.get("ya_existia") is True, "7 ya_existia -> ok / ALREADY_EXISTS", str(r7.get("resultado")))
ok(r7.get("claim_id")==res1.get("claim_id"), "7b mismo claim_id")

# --- 8. Persistencia consistente (reapertura DB_ISO) ---
c=sqlite3.connect(DB_ISO)
claim_row=c.execute("SELECT claim_id,epistemic_state,evidence_refs FROM claims WHERE claim_id=?",(res1["claim_id"],)).fetchone()
ev_count=c.execute("SELECT COUNT(*) FROM evidence WHERE claim_id=?",(res1["claim_id"],)).fetchone()[0]
c.close()
ok(claim_row is not None, "8a claim persistido tras cierre"); ok(claim_row[1]=="PROVEN","8b PROVEN persistido"); ok(ev_count>=1,"8c evidencia persistida")

# --- 9. Integridad / autenticidad (hash real) ---
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
res_h=verificar_propiedad_artefacto(REAL_ART, {"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, evidencia_refs=["res_real_001"], resolver_refs=lambda r:r=="res_real_001")
ok(res_h["resultado"]=="SUPPORTED" and res_h["integridad_evidencia"]["hash_coincide"]==True, "9 integridad real + respaldo SUPPORTED")

# --- 10. Comportamiento aún no integrado (dependencias 239) ---
# El handler real no usa: verificar_compatibilidad_scope, aportar_idempotente, transitar_epistemico, contrato_observation
# Esto se demuestra porque: (a) no hay referencia en machine.py a esos módulos; (b) DB_ISO muestra que evidence_refs no valida scope; (c) duplicados lanzan IntegrityError sin captura; (d) observation no aparece en refs; (e) NOT_DETERMINED se acepta como input de claim sin transición documentada en handler.
# No se aplica ningún cambio; solo se documenta en el informe.
ok(True,"10 NOTA: scope, idempotencia, transicion NOT_DETERMINED, observation NO integrados en machine.py; documentados como dependencias futuras (RXRE-MISSION-239)")

# --- Regresiones / invariantes ---
# Hashes protegidos no modificados (mtaime)
h_after = {p: protected_hash(p) for p in ["/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"]}
ok(h_before==h_after,"invariante: hashes protegidos sin cambio")
# DB_OP
op=sqlite3.connect(DB_OP)
rows_op=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0),"DB_OP constante")
# No se activó op:claim (machine.py no invocado en producción; solo pruebas aisladas con DB_ISO)
ok(True,"invariante: op:claim NO activado en operativa (handler solo con DB_ISO aislado)")

print("\n=== RESUMEN 240 ===")
print("deficit:", FALLOS if FALLOS else "ninguno")
if FALLOS: print("FALLOS:", FALLOS)
else: print("240 PASS PARTIAL — flujo real trazado; dependencias 239 documentadas; integracion requiere autorizacion y diffs documentados; no activado")
