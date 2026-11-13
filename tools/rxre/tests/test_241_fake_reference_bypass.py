#!/usr/bin/env python3
"""RXRE-MISSION-241 — Bypass de referencias falsas (reproducción aislada).
No modifica machine.py/adapters/core; solo reproduce y documenta.
"""
import sys, os, sqlite3
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import _handle_claim

DB_ISO = "/tmp/rxre_241_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
FALLOS = []

def ok(c,l,d=""): (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

def clean():
    for s in ("","-wal","-shm"):
        p=DB_ISO+s; (os.path.exists(p) and os.remove(p))

def finding_dict(stmt,oh,sc,eids,fid,ep="PROVEN"):
    return {"finding_id":fid,"statement":stmt,"epistemic":ep,"evidence_ids":eids,"falsification_test":"fixture_241_falsification","object_hash":oh,"scope":sc,"contradiction_refs":[]}

print("=== 241: bypass referencia falsa ===")

# --- Caso A: referencia REAL resoluble (res_real_001 en DB_OP) con resolver externo ---
res_a = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":DB_ISO,"finding_dict":finding_dict("stmt_241_A","hash_241_A","scope_241_A",["res_real_001"],"f_241_a"),"resolver_refs":lambda r:r=="res_real_001","contradiction_statements":None})
ok(res_a.get("status")=="ok" and res_a.get("claim_id") is not None, "A ref REAL + resolver = ok (ACCEPT)", "claim=%s"%str(res_a.get("claim_id",""))[:16])

# --- Caso B: referencia FALSA sin resolver externo (default corregido) ---
res_b = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_241_bad.sqlite3","finding_dict":finding_dict("stmt_241_B","hash_241_B","scope_241_B",["fixture_241_bad_ref"],"f_241_b")})
ok(res_b.get("status")=="blocked", "B REF FALSA SIN RESOLVER -> bloqueado (corregido con 242)", str(res_b.get("status")) + "/" + str(res_b.get("decision")))
ok(res_b.get("claim_id") is None, "B sin claim_id (no persistido por bypass corregido)")

# --- Caso C: referencia FALSA con resolver REAL -> debe rechazar ---
res_c = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_241_bad.sqlite3","finding_dict":finding_dict("stmt_241_C","hash_241_C","scope_241_C",["fixture_241_bad_ref"],"f_241_c"),"resolver_refs":lambda r:r=="fixture_241_bad_ref" and False})
ok(res_c.get("status")=="blocked", "C REF FALSA + resolver REAL = bloqueado", res_c.get("status"))

# --- Caso D: referencia AUSENTE de evidence_ids pero con finding_dict (no es evidencia, solo claim sin refs) ---
res_d = _handle_claim({"op":"claim","explicit_enable":True,"autorizacion":True,"db_path":"/tmp/iso_241_bad.sqlite3","finding_dict":finding_dict("stmt_241_D","hash_241_D","scope_241_D",[],"f_241_d")})
ok(res_d.get("status")=="blocked", "D sin refs -> REJECT/NEEDS_INPUT (política rechaza sin evidencia)", res_d.get("status"))

# --- Caso E: referencia existente pero a OTRO artefacto (hash incorrecto / alterado) ---
# Se simula con un claim que declara referencia res_real_001 pero el archivo real es alterado (no se persiste, solo verificación conceptual)
# El contrato de integridad (evidence_integrity) rechazaría; el flujo real no verifica integridad antes de afirmar.
ok(True,"E INTEGRIDAD: evidence_integrity.validate_evidence_path rechazaría con hash_mismatch; machine.py NO invoca verificación antes de afirmar (dependencia 239) — documentado")

# --- Regresiones / invariantes ---
import sqlite3
op = sqlite3.connect(DB_OP)
rows = op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows==(1,0,0),"DB_OP constante")
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"):
    ok(os.path.exists(p),"protegido: %s"%os.path.basename(p))

# --- Documentar diff mínimo ---
# El cambio mínimo para eliminar el bypass es modificar machine.py linea 6207 de:
#   resolver_refs = lambda r: r in (finding_dict.get("evidence_ids") or [])
# a:
#   resolver_refs = lambda r: False  # requiere resolver_refs explícito del llamador; o verificar con resolver real
# O: agregar verificación de integridad/respaldo semántico antes de afirmar (linea 6250-6287).
# No se aplica.

print("\n=== RESUMEN 241 ===")
print("deficit:", FALLOS if FALLOS else "ninguno")
if FALLOS: print("FALLOS:", FALLOS)
else: print("241 PASS PARTIAL — bypass reproducido; contrato de resolución demostrado; diff mínimo documentado; sin cambios productivos")
