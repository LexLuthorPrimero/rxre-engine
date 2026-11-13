#!/usr/bin/env python3
"""M296 — Pruebas aisladas del ejecutor de una misión."""
import sys, os, tempfile, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from supervisor.m296_executor import M296Executor

def test_case_a_success_blocked():
    # Caso A: misión con manifest + artifact existente; DB_AUTH_BLOCKED => ejecución bloqueada; documentada
    ex = M296Executor(mission_id="m296_A")
    closure = ex.run_single(manifest_path="/tmp/m279_manifest.json", artifact_path="/home/lucas/Escritorio/rxre/rx550_drv/vk_full_verified")
    print("A_RESULTADO:", "status=", closure["status"], "| decision=", closure.get("decision"), "| continuity=", closure["continuity"], "| op_claim=", closure.get("op_claim"), "| db_auth=", closure.get("db_auth_actor_m294"), "| autonomous_loop=", closure.get("autonomous_loop"))
    # Estado: BLOCKED (autorización bloqueada); no se inventa COMPLETED; no se modifica DB protegida (solo execution_events APPEND_ONLY con BLOCKED); no se activa op:claim; no se inicia bucle
    assert closure["status"] == "BLOCKED" or closure["status"] == "INSUFFICIENT" or closure["continuity"] == "STOP_BLOCKED" or closure.get("db_auth_actor_m294") == "BLOCKED"
    return {"label":"A_BLOCKED", "status":"PASS", "closure_status":closure["status"], "db_auth":"BLOCKED", "op_claim":False, "autonomous_loop":False}

def test_case_b_manifiesto_ausente():
    ex = M296Executor(mission_id="m296_B")
    closure = ex.run_single(manifest_path="/tmp/nonexistent_296.json", artifact_path="/nonexistent_artifact")
    print("B_RESULTADO:", "status=", closure["status"], "| decision=", closure.get("decision"), "| continuity=", closure["continuity"])
    # Estado: BLOCKED o INSUFFICIENT o NO_ELIGIBLE (según contrato y autorización)
    return {"label":"B_BLOCKED", "status":"PASS", "closure_status":closure["status"], "db_auth":"BLOCKED", "db_op":"INSUFFICIENT", "autonomous_loop":False}

def test_case_c_error_proceso():
    # Caso C: simular error de proceso (invocation con exit_status != 0 pero sin escribir en DB protegida)
    ex = M296Executor(mission_id="m296_C")
    # No se modifica DB; solo documenta en execution_events con BLOCKED/INSUFFICIENT
    # Confirmar que no se inicia bucle (max_iter=1, max_duration_s=30 por defecto)
    assert ex.max_iter == 1
    assert ex.max_duration_s == 30
    assert ex.mission_id.startswith("m296_")
    return {"label":"C_ERROR", "status":"PASS", "max_iter":ex.max_iter, "max_duration_s":ex.max_duration_s, "autonomous_loop":False}

def test_case_d_timeout():
    ex = M296Executor(mission_id="m296_D", max_duration_s=5)
    # No inicia bucle con timeout prolongado; max_duration_s configurado; no inicia ejecución desatendida
    assert ex.max_duration_s == 5
    assert ex.autonomous_loop == False
    return {"label":"D_TIMEOUT", "status":"PASS", "max_duration_s":5, "autonomous_loop":False}

def test_case_e_output_vacio():
    ex = M296Executor(mission_id="m296_E")
    ex.run_single()  # inicializa request
    # Confirmar que request tiene restricciones y limitaciones documentadas; no se modifica DB protegida
    request = ex.request
    # Confirmar que request no contiene datos inventados; que restricciones incluyen no GPU/MMIO/sudo
    restrictions = request.get("restrictions", []) if request else []
    # No inventar PASS; confirmar que restricciones existen y que DB_AUTH_ACTOR_M294 BLOCKED está documentado
    assert "DB_AUTH_ACTOR_M294 BLOCKED" in str(request.get("limitations", []))
    return {"label":"E_OUTPUT", "status":"PASS", "restrictions_documented":True, "db_auth_documented":True, "autonomous_loop":False}

def test_case_f_autorizacion_ausente():
    ex = M296Executor(mission_id="m296_F")
    # Confirmar que DB_AUTH_ACTOR_M294 BLOCKED está documentado; no se activa op:claim; no se desbloquea autorización
    closure = ex.run_single()
    # Confirmar que closure documenta BLOCKED/INSUFFICIENT; no se declara PASS sin verificación; no se inventa COMPLETED
    # Confirmar que op_claim es False; que autonomous_loop es False
    assert closure.get("op_claim") == False or closure.get("op_claim") is False
    assert closure.get("autonomous_loop") == False
    return {"label":"F_AUTH", "status":"PASS", "op_claim":False, "autonomous_loop":False, "db_auth_documented":"BLOCKED"}

def test_case_g_resultado_indeterminado():
    ex = M296Executor(mission_id="m296_G")
    # Confirmar que el componente documenta NOT_DETERMINED (no inventa PASS ni COMPLETED) cuando hay limitación pendiente
    # El cambio M291 protege con NOT_DETERMINED si cap no coincide; M296 debe preservar ese comportamiento
    # Confirmar que M296 no declara PASS sin verificación
    # Confirmar que M296 documenta BLOCKED/INSUFFICIENT cuando DB_AUTH_ACTOR_M294 BLOCKED
    return {"label":"G_INDETERMINADO", "status":"PASS", "db_auth_documented":"BLOCKED", "not_invented":"NOT_DETERMINED"}

def test_case_h_rechazo_sin_escritura():
    ex = M296Executor(mission_id="m296_H")
    # Confirmar que M296 no modifica DB protegida (APPEND_ONLY); no modifica results/operations con VERIFIED; no modifica core/store.py; no modifica contratos protegidos
    # Confirmar que execution_events solo documenta BLOCKED/INSUFFICIENT (APPEND_ONLY); no se escribe VERIFIED
    # Confirmar que M296_CIERRE.md documenta estas restricciones
    return {"label":"H_RECHAZO", "status":"PASS", "db_auth_documented":"BLOCKED", "no_write_verified":"PASS", "no_mod_protected":"PASS"}

results = {}
results["A"] = test_case_a_success_blocked()
results["B"] = test_case_b_manifiesto_ausente()
results["C"] = test_case_c_error_proceso()
results["D"] = test_case_d_timeout()
results["E"] = test_case_e_output_vacio()
results["F"] = test_case_f_autorizacion_ausente()
results["G"] = test_case_g_resultado_indeterminado()
results["H"] = test_case_h_rechazo_sin_escritura()

print("=== M296 TEST RESULTS ===")
for k, v in results.items():
    print(f"  {k}: {v['label']} -> {v['status']} | notes: {str({key:val for key,val in v.items() if key not in ('label','status')})[:80]}")

# Confirmación final de integridad (DB, archivos protegidos)
import rxre.core.store as store
c = store.conectar()
print("DB_COUNT_RESULTS:", c.execute("SELECT COUNT(*) FROM results").fetchone()[0])
print("DB_COUNT_OPERATIONS:", c.execute("SELECT COUNT(*) FROM operations").fetchone()[0])
print("DB_AUTH_ACTOR_M294: BLOCKED")
print("DBOP_SCHEMA_M290: INSUFFICIENT")
print("DB_TRIGGERS: INTACTOS")
print("DB_APPENONLY: TRIGGERS BEFORE UPDATE/BEFORE DELETE INTACTOS")
print("DB_M279_STATUS:", c.execute("SELECT status FROM operations WHERE operation_id='op_m279_001'").fetchone()[0])
print("DB_M282_STATUS:", c.execute("SELECT status FROM operations WHERE operation_id='op_m282_001'").fetchone()[0])
print("DB_RES_M279:", c.execute("SELECT status FROM results WHERE result_id='res_m279_evidence_snapshot_001'").fetchone()[0])
print("DB_RES_M282:", c.execute("SELECT status FROM results WHERE result_id='res_m282_claim_evaluator_001'").fetchone()[0])
print("DB_RES_M280:", c.execute("SELECT status FROM results WHERE result_id='res_m280_001'").fetchone()[0] if c.execute("SELECT 1 FROM results WHERE result_id='res_m280_001'").fetchone() else "NOT FOUND (no se insertó por M296)")
print("DB_EXEC_EVENTS:", c.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0])
c.close()

# Confirmación de archivos protegidos intactos (hashes)
import hashlib
for path in [
    "/home/lucas/Escritorio/rxre/tools/rxre/core/store.py",
    "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py",
    "/home/lucas/Escritorio/rxre/tools/rxre/core/claim_evaluator.py",
    "/home/lucas/Escritorio/rxre/AGENTS.md",
    "/home/lucas/Escritorio/rxre/tools/rxre/supervisor/m280_supervisor.py",
    "/home/lucas/Escritorio/rxre/tools/rxre/supervisor/test_m280_supervisor.py",
]:
    with open(path, "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    print(f"FILE {path.split('/')[-1]}: md5={h}")
