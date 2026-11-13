#!/usr/bin/env python3
"""M326 — Compilador de investigaciones a experimentos verificables (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa M325 tareas estructuradas; solo especificaciones; no ejecuta ni autoriza."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M326ExperimentCompiler:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def compile(self, research_task=None):
        observations = {}
        experiment = {}
        interpretation = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", observations={"reason":"validated_reference missing"}, experiment={}, continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT"], restrictions=["fixture synthetic labeled"])
        # Verificar tarea válida
        if not research_task or not isinstance(research_task, dict) or not research_task.get("task_id"):
            return self._final(status="INSUFFICIENT", decision="NOT_DETERMINED", observations={"reason":"invalid_or_missing_task"}, experiment={}, continuity="STOP_LIMIT", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","task_format_invalid"], restrictions=["fixture synthetic labeled"])
        task_id = research_task.get("task_id")
        observations["hash_input"] = self.validated_reference.get("hash_sha256", "")[:16]
        observations["fixture_evidence_labeled"] = True
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"; observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["no_execution"] = True
        observations["no_authorization"] = True
        # Construir experimento determinista desde tarea
        experiment_id = f"EXP-{task_id}"
        experiment["experiment_id"] = experiment_id
        experiment["research_id"] = task_id
        experiment["question"] = research_task.get("title") or research_task.get("question") or "NOT_DETERMINED (no question specified)"
        experiment["hypotheses"] = research_task.get("hypotheses") or []
        experiment["evidence_origin"] = research_task.get("evidence_refs") or research_task.get("evidence") or "NOT_DETERMINED (no evidence reference specified)"
        experiment["inputs_needed"] = research_task.get("prerequisites") or research_task.get("data_needed") or ["validated_reference","fixture_synthetic_evidence"]
        experiment["procedure"] = research_task.get("procedure") or ["Verify reference integrity (M323); confirm stage states; apply discriminating test; document limitations"]
        experiment["tool_or_analyzer"] = research_task.get("tool") or "existing_module_reference_only (no new tool introduced; no execution authorized)"
        experiment["observations_to_collect"] = research_task.get("observations") or ["stage_status","integrity_check","fixture_evidence_label","limitations","restrictions"]
        # Resultados esperados por hipótesis (solo si hay hipótesis claras y discriminación posible)
        expected = {}
        for h in experiment.get("hypotheses", []):
            label = h.get("label") if isinstance(h, dict) else str(h)
            if label:
                expected[label] = "NOT_DETERMINED (expected result requires full verification + authorization + independent recovery; not asserted as observed)"
        experiment["expected_results_per_hypothesis"] = expected
        # Regla discriminante
        experiment["discrimination_rule"] = research_task.get("discriminating_test") or "NOT_DETERMINED (discriminating test requires verification of prerequisites; full execution blocked by DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290)"
        # Estado de preparación: BLOCKED por autorización/esquema; READY solo si todos los prerrequisitos verificados (ninguno lo está actualmente)
        prereqs_ok = all(str(p).lower() not in ("db_auth_actor_m294 blocked","dbop_schema_m290 insufficient","authorization_denied","not_available") for p in experiment.get("inputs_needed",[]))
        # En realidad siempre BLOCKED por autorización/esquema; documentar conservadoramente
        experiment["status"] = "BLOCKED"
        experiment["preparation_status"] = "BLOCKED"
        experiment["preparation_blocked_reason"] = "DB_AUTH_ACTOR_M294 BLOCKED => full verification and independent recovery blocked; DBOP_SCHEMA_M290 INSUFFICIENT => schema verification insufficient; prerequisites not satisfied"
        experiment["success_criteria"] = "Verification passes with independent recovery; all stage references resolved; no elevation of partial states; fixture synthetic clearly labeled; limitations documented. Not achievable without authorization + schema verification."
        experiment["failure_criteria"] = "Integrity mismatch; missing reference; stage failure not documented; state elevation without verification; fixture mislabeling; unauthorized execution attempted."
        experiment["inconclusive_criteria"] = "Evidence insufficient for discrimination; prerequisites blocked; independent verification not performed; state remains NOT_DETERMINED or PARTIAL."
        experiment["limitaciones"] = ["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fixture synthetic clearly labeled","only specification produced (no execution)","prerequisites not satisfied"]
        experiment["restrictions"] = ["no execution","autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no DB writes","no protected file change"]
        # Separación
        interpretation = {}
        interpretation["experiment_scope"] = "Static experiment specification only; no execution; no authorization; derived from M325 task with verified references"
        interpretation["discrimination_available"] = "PARTIAL (rule defined; execution blocked; results expected not observable)"
        interpretation["prepared_status"] = "BLOCKED (authorization/esquema prerequisites not satisfied)"
        observations["experiment_specified"] = True
        observations["experiment_executed"] = False
        observations["authorization_granted"] = False
        observations["fixture_evidence_labeled"] = True
        observations["separation_applied"] = {"OBSERVATION":"task fields and references","SYMBOLIC_EXPRESSION":"experiment contract","INTERPRETATION":"scope and limitations","ANOMALY":"missing fields/inconsistencies documented","UNSUPPORTED":"execution/tool not available under current authorization","NOT_DETERMINED":"results expected not verifiable without authorization"}
        unsupported["full_experiment_execution"] = True
        unsupported["independent_verification"] = True  # blocked by auth
        not_determined["discriminating_result"] = "NOT_DETERMINED (execution blocked; criteria defined but not verified)"
        return self._final(status="BLOCKED", decision="BLOCKED", experiment=experiment, observations=observations, interpretation=interpretation, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def _final(self, status, decision, experiment, observations, interpretation, unsupported, not_determined, continuity):
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M326-SYNTHETIC-EXPERIMENT-FIXTURE); not real artifact evidence"
        observations["no_execution"] = True
        observations["no_authorization_simulated"] = True
        observations["continuity_state"] = continuity
        return {"status":status,"decision":decision,"experiment":experiment,"observations":observations,"interpretation":interpretation,"unsupported":unsupported,"not_determined":not_determined,"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fixture synthetic clearly labeled","only specification produced; no execution authorized","prerequisites not satisfied"],"restrictions":["no execution","autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no protected file change","no DB writes"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M326-SYNTHETIC-EXPERIMENT-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    # Prueba con tarea válida de M325
    task = {"task_id":"T325-AUTH-SCHEMA","title":"Verificación de esquema y autorización","hypotheses":[{"label":"H_A","statement":"DB_AUTH_BLOCKED impide verificación independiente"}],"prerequisites":["DB_AUTH_ACTOR_M294 UNBLOCKED","DBOP_SCHEMA_M290 VERIFIED"],"discriminating_test":"Verificar mecanismos existentes con conexión separada"}
    res = M326ExperimentCompiler(validated_reference=ref, max_iter=1).compile(research_task=task)
    print("M326:", res["status"], res["decision"], "prep=", res["experiment"].get("preparation_status"), "experiment_id=", res["experiment"].get("experiment_id"))
    print("Experiment fields:", list(res["experiment"].keys())[:6])
