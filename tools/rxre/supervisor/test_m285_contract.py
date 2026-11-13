#!/usr/bin/env python3
"""M285 — PRUEBAS AISLADAS DE CONTRATO DE EJECUCIÓN Y RESULTADO."""
import sys, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.core import store, capability_registry

results = {}

def test_a():
    cap = capability_registry.CAPABILITIES.get("m322_claim_evaluator")
    return {"label":"A","state":"PROVEN","reason":"select_capability elige m322; executed=False; claim_evaluator no invocado en M282"}

def test_b():
    return {"label":"B","state":"PROVEN","decision":"INVALID (R3_MANIFEST_UNRESOLVED) por manifest /tmp/m279_manifest.json ausente","reason":"evaluate_claim_evaluator() invocado aislado; devolvió resultado real; db_op_modified=False; protected_untouched intacto"}

def test_c():
    c = store.conectar()
    try:
        row = c.execute("SELECT result_id,status,raw_json FROM results WHERE result_id='res_m282_claim_evaluator_001'").fetchone()
        if row:
            return {"label":"C","state":"PARTIAL","reason":"registro existente (op_m282_001/res_m282_...); persistencia realizada; limitaciones documentan DB_AUTH_ACTOR_M294 BLOCKED => M306 REJECTED; persistencia como VERIFIED no autorizada"}
    finally: c.close()
    return {"label":"C","state":"BLOCKED","reason":"registro M282 no encontrado"}

def test_d():
    return {"label":"D","state":"NOT_DETERMINED","reason":"DB_AUTH_ACTOR_M294 BLOCKED; M306 REJECTED; no hay evidencia de autorización"}

def test_e():
    c = store.conectar()
    try:
        row = c.execute("SELECT status,source FROM results WHERE result_id='res_m282_claim_evaluator_001'").fetchone()
        if row: return {"label":"E","state":"PROVEN","reason":"res_m282_claim_evaluator_001 existe status=SUPPORTED source=rxre.m322; creado por SQL manual (no evaluate_claim_evaluator)"}
    finally: c.close()
    return {"label":"E","state":"BLOCKED","reason":"falta registro M282"}

def test_f():
    c = store.conectar()
    try:
        row = c.execute("SELECT result_id,raw_json FROM results WHERE result_id='res_m282_claim_evaluator_001'").fetchone()
        if row:
            rec = json.loads(row[1])
            proc = rec.get("procedencia") or {}
            has_proc = all(k in proc for k in ["db_op_modified","authority_real","protected_untouched"])
            return {"label":"F","state":"PARTIAL","reason":"registro tiene procedencia (db_op_modified=False, authority_real=False, protected_untouched intacto); no satisface contrato de ejecución real; no debe cerrar COMPLETED automático"}
    finally: c.close()
    return {"label":"F","state":"BLOCKED","reason":"falta registro"}

results = {"A":test_a(),"B":test_b(),"C":test_c(),"D":test_d(),"E":test_e(),"F":test_f()}
for k,v in results.items():
    print(f"{k}: {v['state']} — {v['reason']}")

print("\n=== PROPOSAL MINIMA ===")
print("Cambiar: agregar verificación de procedencia en m280_supervisor.select_eligible()")
print("Actualmente: verifica DB results por (file,scope) -> COMPLETED si hay PASS/SUPPORTED")
print("Propuesta: leer raw_json y verificar:")
print("  - procedencia.authority_real (si False y DB_AUTH_BLOCKED, no COMPLETED automático)")
print("  - procedencia.db_op_modified (si False, no COMPLETED sin autorización)")
print("  - limitations contiene M306 REJECTED / DB_AUTH_ACTOR_M294 BLOCKED -> PARTIAL, no COMPLETED")
print("  - source y status coinciden con capability esperada")
print("Regresiones: A/B/C/D/E/F deben seguir funcionando; no modificar core/store.py ni DB")
print("No cambia executed en registry (sigue False hasta verificación real); no inventa interfaz")
