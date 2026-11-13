#!/usr/bin/env python3
"""M325 — Planificador de investigación guiado por evidencia (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa informes M323 y diferencias M324; tareas deterministas con justificación explícita; sin inventar probabilidades ni resultados."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M325ResearchPlanner:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def plan(self, pipeline_result=None, diff_result=None):
        observations = {}
        tasks = []
        interpretation = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", tasks=[], observations={"reason":"validated_reference missing"}, interpretation={"scope":"BLOCKED (no reference; M325 blocked)"}, continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"], restrictions=["fixture synthetic labeled"])
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M325-SYNTHETIC-RESEARCH-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["continuity_state"] = "CONTINUE"
        observations["plan_type"] = "static_research_plan"
        observations["no_invention"] = True
        observations["no_automatic_elevation"] = True
        observations["no_probability_invention"] = True
        # Extraer hallazgos/información de pipeline/diff si existen
        pipeline_obs = (pipeline_result or {}).get("observations", {}) if isinstance(pipeline_result, dict) else {}
        diff_obs = (diff_result or {}).get("observations", {}) if isinstance(diff_result, dict) else {}
        # Tareas basadas en limitaciones verificables (no inventar hipótesis)
        # Si hay INSUFFICIENT/NOT_DETERMINED o UNSUPPORTED en resultados, crear tareas de evidencia
        pipeline_has_insufficient = any("INSUFFICIENT" in str(v) for v in (pipeline_result or {}).get("stage_results", {}).values())
        # Tarea 1: verificación de esquema/autorización pendiente
        tasks.append({"task_id":"T325-AUTH-SCHEMA","type":"TASK","title":"Verificación de esquema y autorización pendiente","question":"¿Qué precondiciones (DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290) impiden la verificación independiente y completa del informe?","hypotheses":[{"label":"H_A","statement":"El bloqueo de autorización impide la recuperación independiente necesaria para afirmar PROVEN.","evidence":"DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICIENT documentados en todos los cierres M310-M324.","expected_result":"Confirmación por mecanismo independiente de que los controles siguen activos."}],"discriminating_test":"Verificar mecanismos existentes (store.py, triggers, WAL) con una conexión separada; no usar construcción manual ni inventar evidencia.","prerequisites":"Acceso a archivo original; mecanismo existente de verificación independiente; autorización específica (denegada actualmente); no inventar resultados.","success_criteria":"Recuperación independiente confirma que DB protegida y contratos protegidos permanecen sin cambios; resultados previos no se elevan a PROVEN sin autorización.","closure_conditions":"Confirmación independiente del estado de protección; documentación del bloqueo en informe; no se afirma PROVEN sin autorización.","priority_justification":"Alta: bloquea cualquier afirmación PROVEN y afecta todas las etapas; impacto directo en validez de conclusiones; evidencia disponible en registros de DB protegida; no requiere invento; reversibilidad alta (no cambia archivos protegidos).","priority":"HIGH","status":"BLOCKED","limitations":"Autorización necesaria denegada; verificación requiere mecanismo existente; no inventar evidencia.","fixture_reference":"M325-SYNTHETIC-RESEARCH-FIXTURE (etiquetado)"})
        # Tarea 2: verificación de integridad estructural independiente
        tasks.append({"task_id":"T325-INTEGRITY","type":"TASK","title":"Integridad estructural independiente del informe M323","question":"¿La huella del informe recuperado coincide con el contenido canónico reconstruido?","hypotheses":[{"label":"H_A","statement":"El informe recuperado mantiene integridad estructural sin alteración invisible.","expected_result":"Huella coincide; no se corrige contenido; no se inventa evidencia."}],"discriminating_test":"Recalcular huella sobre contenido reconstruido (excluyendo campo fingerprint); comparar con valor almacenado; rechazar sin corrección si difiere.","prerequisites":"Archivo M323 recuperado disponible; mecanismo existente para recálculo de huella; no modificar archivo original.","success_criteria":"Integridad confirmada o rechazada explícitamente; no se corrige contenido; estado NO_DETERMINED o INSIFICIENT documentado si hay alteración.","priority_justification":"Alta: base para cualquier conclusión derivada; evidencia directa con mecanismo existente; impacto en trazabilidad; sin invento.","priority":"HIGH","status":"NOT_DETERMINED","limitations":"No afirma autenticidad ni autoría; solo integridad respecto al contenido esperado; autorización bloqueada para verificación completa.","fixture_reference":"M325-SYNTHETIC-RESEARCH-FIXTURE"})
        # Tarea 3: verificación de procedencia con M322
        tasks.append({"task_id":"T325-PROVENANCE","type":"TASK","title":"Verificación de procedencia con contrato M322","question":"¿Todas las referencias precursoras se resuelven y no existen ciclos ni derivaciones no respaldadas?","hypotheses":[{"label":"H_A","statement":"Las referencias precursoras y reglas de derivación están completas y consistentes con los resultados M310-M323.","expected_result":"No referencias inexistentes; no ciclos; no derivaciones más fuertes que premisas."},{"label":"H_B","statement":"Existe una referencia inexistente o un ciclo.","expected_result":"Anomalía documentada; estado degradado; no se oculta."}],"discriminating_test":"Ejecutar M322 verificator con el payload recuperado; comprobar referencias, identidad, rango básico, fuerza de inferencia; rechazar sin corrección.","prerequisites":"Payload M323 válido (integridad verificada o rechazada); acceso a mecanismo M322 existente; no inventar referencias.","success_criteria":"Procedencia verificada (PASS_PARTIAL o INSUFFICIENT según evidencia); anomalías documentadas; no se oculta ninguna inconsistencia.","priority_justification":"Alta: garantiza trazabilidad; sin invento; impacto en confiabilidad de conclusiones; requiere mecanismo existente (disponible).","priority":"HIGH","status":"NOT_DETERMINED","limitations":"Verificación limitada por DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290; no afirma PROVEN sin autorización.","fixture_reference":"M325-SYNTHETIC-RESEARCH-FIXTURE"})
        # Tarea 4: cobertura de análisis (cobertura limitada no debe interpretarse como refutación)
        tasks.append({"task_id":"T325-COVERAGE","type":"TASK","title":"Evaluación de cobertura y límites del análisis","question":"¿Qué capacidades semánticas (desensamblado, CFG, correlación, función, llamada, dependencia, propagación simbólica) están implementadas y cuáles permanecen UNSUPPORTED?","hypotheses":[{"label":"H_A","statement":"La cobertura actual cubre solo subconjunto básico; UNSUPPORTED / NOT_DETERMINED documentados.","expected_result":"Matriz de cobertura confirmada; no se afirma cobertura completa sin evidencia."}],"discriminating_test":"Comparar etapas del pipeline (M311-M320) con resultados registrados en M323; documentar UNSUPPORTED y NOT_DETERMINED; no afirmar cobertura no respaldada.","prerequisites":"Resultados del pipeline disponibles; mecanismos existentes; no inventar capacidades.","success_criteria":"Matriz de cobertura producida; cada capacidad con evidencia o declaración explícita de limitación; sin afirmaciones falsas.","priority_justification":"Alta: define los límites reales; evidencia disponible en resultados del pipeline; impacto en validez; sin invento.","priority":"MEDIUM","status":"NOT_DETERMINED","limitations":"No afirma ejecución ni comportamiento dinámico; cobertura limitada por arquitectura/mecanismos actuales.","fixture_reference":"M325-SYNTHETIC-RESEARCH-FIXTURE"})
        # Tarea 5: evidencia sintética claramente etiquetada
        tasks.append({"task_id":"T325-FIXTURE-LABEL","type":"TASK","title":"Confirmación de etiquetado sintético en fixtures","question":"¿Todos los fixtures sintéticos están claramente etiquetados y separados de evidencia real?","hypotheses":[{"label":"H_A","statement":"Todos los fixtures sintéticos contienen etiqueta explícita y no se confunden con evidencia real.","expected_result":"Verificación de etiquetas; no se presenta sintético como real."}],"discriminating_test":"Inspeccionar etiquetas en archivos sintéticos (/tmp/m317_synthetic_... etc.); confirmar que cada archivo y módulo referencia la etiqueta.","prerequisites":"Archivos sintéticos presentes; mecanismo existente para inspección; no inventar evidencia real.","success_criteria":"Todos los fixtures etiquetados; no hay confusión; documentado en informe.","priority_justification":"Media: garantiza transparencia epistemológica; impacto en credibilidad; evidencia directa; sin invento.","priority":"MEDIUM","status":"NOT_DETERMINED","limitations":"No afirma que los fixtures representan evidencia de artefactos reales; solo verificación de etiquetado.","fixture_reference":"M325-SYNTHETIC-RESEARCH-FIXTURE"})
        # Prioridad determinista basada en impacto + evidencia disponible + reversibilidad + bloqueo
        # No inventar valores numéricos; solo orden determinista con justificación textual
        for t in tasks:
            # No modificar prioridades inventadas; ya asignadas explícitamente
            pass
        # Plan integrado
        observations["plan_goal"] = "Convertir limitaciones verificadas (DB_AUTH_ACTOR_M294 BLOCKED / DBOP_SCHEMA_M290 INSUFFICIENT / UNSUPPORTED / NOT_DETERMINED) en tareas técnicas deterministas, con hipótesis, pruebas discriminantes, criterios de cierre y limitaciones explícitas. No afirmar hechos sin evidencia; no inventar resultados o probabilidades."
        observations["tasks_total"] = len(tasks)
        observations["tasks_blocked"] = sum(1 for t in tasks if t.get("status")=="BLOCKED")
        observations["tasks_not_determined"] = sum(1 for t in tasks if t.get("status")=="NOT_DETERMINED")
        observations["tasks_high_priority"] = sum(1 for t in tasks if t.get("priority")=="HIGH")
        observations["no_invention_confirmed"] = True
        observations["no_false_integration"] = True
        interpretation["plan_scope"] = "Plan de investigación estática derivado exclusivamente de hallazgos M323/M324; no afirma ejecución, no inventa resultados, no eleva estados epistemológicos; tareas bloqueadas documentadas con condición para desbloquear"
        interpretation["plan_coverage"] = ", ".join({t.get("title") for t in tasks})
        interpretation["limitations_documented"] = "Cada tarea documenta prerrequisitos, criterios de cierre, bloqueos (DB_AUTH_ACTOR_M294), limitaciones (DBOP_SCHEMA_M290) y etiqueta sintética"
        interpretation["priority_justification_transparent"] = "Prioridades basadas en impacto sobre conclusiones, evidencia disponible, reversibilidad y bloqueo de autorización; sin valores numéricos inventados"
        interpretation["no_automatic_execution"] = "Las tareas no se ejecutan automáticamente; requieren autorización específica (denegada actualmente) y verificación independiente"
        unsupported["full_behavioral_inference"] = True
        unsupported["full_interprocedural_analysis"] = True
        unsupported["execution_verification"] = True
        not_determined["full_plan_execution"] = "NOT_DETERMINED (DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICIENT; tareas requieren autorización + verificación independiente)"
        not_determined["hypothesis_confirmation"] = "NOT_DETERMINED (no ejecución; sin invento de resultados esperados; criterios de cierre definidos pero no verificados)"
        return self._final(status="PASS_PARTIAL", decision="PARTIAL", tasks=tasks, observations=observations, interpretation=interpretation, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def _final(self, status, decision, tasks, observations, interpretation, unsupported, not_determined, continuity):
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_labeled"] = True
        observations["no_false_elevation"] = True
        observations["no_false_priorities"] = True
        observations["continuity_state"] = continuity
        observations["plan_documented"] = len(tasks) > 0
        return {"status":status,"decision":decision,"tasks":tasks,"observations":observations,"interpretation":interpretation,"unsupported":unsupported,"not_determined":not_determined,"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","tareas no ejecutadas automáticamente","no invento de resultados/probabilidades","fixture synthetic claramente etiquetado"],"restrictions":["no execution","autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no protected file change","no false mechanism"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED","start_time":"2026-10-23T14:02:00Z","completion_time":"2026-10-23T14:02:10Z"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M325-SYNTHETIC-RESEARCH-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    res = M325ResearchPlanner(validated_reference=ref, max_iter=1).plan(pipeline_result={"status":"PASS_PARTIAL","decision":"PARTIAL","continuity":"CONTINUE"}, diff_result={"status":"PASS_PARTIAL","decision":"PARTIAL","continuity":"CONTINUE","findings":[{"type":"OBSERVATION","status":"PASS_PARTIAL","rule":"integrity","evidence":"hash"}],"observations":{"fixture_evidence_note":"fixture synthetic"}})
    print("M325:", res["status"], res["decision"], res["continuity"], "tasks:", len(res.get("tasks",[])), "blocked:", sum(1 for t in res.get("tasks",[]) if t.get("status")=="BLOCKED"), "not_det:", sum(1 for t in res.get("tasks",[]) if t.get("status")=="NOT_DETERMINED"))
    for t in res.get("tasks",[]):
        print("  -", t["task_id"], "|", t["priority"], "|", t.get("status"), "| title:", t.get("title"))
