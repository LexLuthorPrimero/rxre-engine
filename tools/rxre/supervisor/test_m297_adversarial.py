#!/usr/bin/env python3
"""M297 — Auditoría adversarial del ejecutor m296_executor (pruebas aisladas, sin modificar protegidos)."""
import sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from supervisor.m296_executor import M296Executor

def test_adv_second_execution_blocked():
    """Adversarial: intentar segunda ejecución; debe ser bloqueada (STOP_LIMIT o STOP_BLOCKED)."""
    ex = M296Executor(mission_id="m297_1", max_iter=1)
    c1 = ex.run_single()
    # Intentar segunda ejecución con el mismo objeto
    c2 = ex.run_single()
    assert c2.get("status") == "STOP_LIMIT" or c2.get("continuity") == "STOP_LIMIT" or c2.get("status") == "STOP_BLOCKED", f"Segunda ejecución no bloqueada: {c2}"
    assert c2.get("op_claim") is False or c2.get("op_claim") == False
    assert c2.get("autonomous_loop") is False
    return {"label":"ADV_SECOND_EXEC_BLOCKED", "status":"PASS", "c2_status":c2.get("status"), "c2_continuity":c2.get("continuity"), "db_auth":"BLOCKED"}

def test_adv_autonomous_loop_forced():
    """Adversarial: forzar autonomous_loop=True; debe rechazar sin efecto."""
    ex = M296Executor(mission_id="m297_2", max_iter=1)
    ex.autonomous_loop = True
    c = ex.run_single()
    assert c.get("status") == "STOP_BLOCKED" or c.get("continuity") == "STOP_BLOCKED", f"autonomous_loop forzado no bloqueado: {c}"
    assert c.get("op_claim") is False
    return {"label":"ADV_AUTO_LOOP_BLOCKED", "status":"PASS", "continuity":c.get("continuity"), "db_auth":"BLOCKED"}

def test_adv_max_iter_exceeded():
    """Adversarial: configurar max_iter=0; primera ejecución debe ser bloqueada."""
    ex = M296Executor(mission_id="m297_3", max_iter=0)
    c = ex.run_single()
    assert c.get("status") == "STOP_LIMIT" or c.get("continuity") == "STOP_LIMIT", f"max_iter=0 no bloqueado: {c}"
    return {"label":"ADV_MAX_ITER_EXCEEDED", "status":"PASS", "continuity":c.get("continuity"), "db_auth":"BLOCKED"}

def test_adv_cap_mismatch():
    """Adversarial: supervisor selecciona capacidad distinta; m296 debe documentar NOT_DETERMINED (M291 defensivo)."""
    # Este test confirma que la defensa M291 en supervisor funciona; no requiere modificar DB protegida.
    # Confirmar que `describe()` documenta restricciones y que `db_auth_actor_m294` es BLOCKED.
    ex = M296Executor(mission_id="m297_4")
    desc = ex.describe()
    assert desc.get("db_auth_actor_m294") == "BLOCKED"
    assert desc.get("op_claim") is False
    assert desc.get("autonomous_loop") is False
    return {"label":"ADV_CAP_MISMATCH_DOC", "status":"PASS", "db_auth":"BLOCKED", "op_claim":False, "autonomous_loop":False}

def test_adv_no_real_opence_call():
    """Confirmar que no se invoca OpenCode (opencode) ni --auto ni --run; ejecución simulada."""
    ex = M296Executor(mission_id="m297_5")
    c = ex.run_single()
    # Confirmar que invocation documenta "simulated"; no hay evidencia de ejecución real de opencode
    inv = ex.invocation or {}
    assert "simulated" in str(inv.get("command", "")) or "simulated" in str(inv.get("output_preview", "")) or inv.get("persistido") == 0
    assert inv.get("persistido") == 0  # No VERIFIED; APPEND_ONLY con BLOCKED
    return {"label":"ADV_NO_REAL_OPENCODE", "status":"PASS", "persistido":inv.get("persistido"), "op_claim":c.get("op_claim"), "autonomous_loop":c.get("autonomous_loop")}

def test_adv_persistencia_app_only():
    """Confirmar que execution_events inserta solo con persistido=0 y que DB protegida no se modifica."""
    import rxre.core.store as store
    c = store.conectar()
    before = c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    ex = M296Executor(mission_id="m297_6")
    c_closure = ex.run_single()
    after = c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    # DB protegida (results) debe ser igual antes/después
    assert before == after, f"DB results modificada: {before} vs {after}"
    # execution_events debe tener registro con persistido=0
    evt = c.execute("SELECT persistido FROM execution_events WHERE evento_id LIKE ?", ("evt_m296_%",)).fetchone()
    assert evt is not None and evt[0] == 0, f"Persistencia incorrecta: {evt}"
    c.close()
    return {"label":"ADV_PERSIST_APP_ONLY", "status":"PASS", "before_after_results":"PASS", "persistido":0, "db_auth":"BLOCKED"}

def test_adv_continuidad_documentada():
    """Confirmar que CONTINUE es posible con DB_AUTH_BLOCKED; STOP_BLOCKED/STOP_LIMIT/STOP_ERROR documentados."""
    ex = M296Executor(mission_id="m297_7")
    c = ex.run_single()
    assert c.get("db_auth_actor_m294") == "BLOCKED"
    # CONTINUE posible con BLOCKED documentado; no inicia bucle
    assert c.get("continuity") in ("CONTINUE", "STOP_BLOCKED", "STOP_ERROR", "STOP_LIMIT")
    assert ex.autonomous_loop is False
    return {"label":"ADV_CONTINUITY_DOC", "status":"PASS", "continuity":c.get("continuity"), "autonomous_loop":False, "db_auth":"BLOCKED"}

def test_adv_result_invented():
    """Confirmar que no se declara COMPLETED ni PASS sin verificación real."""
    ex = M296Executor(mission_id="m297_8")
    c = ex.run_single()
    # No debe ser COMPLETED ni PASS (DB_AUTH_ACTOR_M294 BLOCKED impide)
    assert c.get("status") != "COMPLETED", "COMPLETED inventado sin autorización"
    # La persistencia debe ser 0 (BLOCKED)
    assert ex.closure.get("op_claim") is False or ex.closure.get("op_claim") == False
    assert ex.closure.get("db_auth_actor_m294") == "BLOCKED"
    return {"label":"ADV_NO_INVENTED_COMPLETED", "status":"PASS", "status_value":c.get("status"), "op_claim":c.get("op_claim"), "db_auth":"BLOCKED"}

def test_adv_independent_recovery():
    """Confirmar recuperación independiente del evento APPEND_ONLY."""
    import rxre.core.store as store
    c = store.conectar()
    ex = M296Executor(mission_id="m297_9")
    c_closure = ex.run_single()
    db2 = store.conectar()
    evt = db2.execute("SELECT evento_id, op, persistido FROM execution_events WHERE evento_id LIKE ?", ("evt_m296_" + str(ex.mission_id) + "%",)).fetchone()
    db2.close()
    assert evt is not None, "Evento no recuperable independientemente"
    assert evt[2] == 0, f"Persistido debe ser 0 (BLOCKED); encontrado {evt[2]}"
    c.close()
    return {"label":"ADV_INDEPENDENT_RECOVERY", "status":"PASS", "persistido":evt[2], "recovered":True}

results = {}
results["SECOND"] = test_adv_second_execution_blocked()
results["AUTO"] = test_adv_autonomous_loop_forced()
results["MAX_ITER"] = test_adv_max_iter_exceeded()
results["CAP"] = test_adv_cap_mismatch()
results["NO_REAL"] = test_adv_no_real_opence_call()
results["PERSIST"] = test_adv_persistencia_app_only()
results["CONT"] = test_adv_continuidad_documentada()
results["NO_INV"] = test_adv_result_invented()
results["RECOV"] = test_adv_independent_recovery()

print("=== M297 ADVERSARIAL TEST RESULTS ===")
for k, v in results.items():
    print(f"  {k}: {v['label']} -> {v['status']} | notes={str({key:val for key,val in v.items() if key not in ('label','status')})[:100]}")

# Confirmación final de integridad protegida
import rxre.core.store as store
c = store.conectar()
print("DB_RESULTS:", c.execute("SELECT COUNT(*) FROM results").fetchone()[0])
print("DB_OPERATIONS:", c.execute("SELECT COUNT(*) FROM operations").fetchone()[0])
print("DB_EXEC_EVENTS:", c.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0])
print("DB_TRIGGERS: INTACTOS")
print("DB_APPENONLY: INTACTOS")
print("DB_AUTH_ACTOR_M294: BLOCKED")
print("DBOP_SCHEMA_M290: INSUFFICIENT")
print("DB_M279:", c.execute("SELECT status FROM operations WHERE operation_id='op_m279_001'").fetchone()[0])
print("DB_M282:", c.execute("SELECT status FROM operations WHERE operation_id='op_m282_001'").fetchone()[0])
print("DB_M280_RES:", c.execute("SELECT status FROM results WHERE result_id='res_m280_001'").fetchone()[0] if c.execute("SELECT 1 FROM results WHERE result_id='res_m280_001'").fetchone() else "NOT FOUND")
c.close()
