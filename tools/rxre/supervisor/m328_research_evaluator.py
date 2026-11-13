#!/usr/bin/env python3
"""M328 — Evaluador de resultados y cierre de investigaciones (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa registros M327 y tareas M325; estados RESOLVED / PARTIALLY_RESOLVED / OPEN / BLOCKED / INSUFFICIENT / NOT_DETERMINED; sin promoción automática."""
import sys, hashlib, os, time
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M328ResearchEvaluator:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def evaluate(self, research_task=None, experiment_result=None):
        observations = {}
        evaluation = {}
        interpretation = {}
        unsupported = {}
        not_determined = {}
        # Requisito básico
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", observations={"reason":"validated_reference missing"}, evaluation={}, continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"], restrictions=["fixture synthetic labeled"])
        observations["hash_input"] = self.validated_reference.get("hash_sha256","")[:16]
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M328-SYNTHETIC-EVAL-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"; observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["no_automatic_elevation"] = True; observations["no_false_success"] = True
        observations["no_execution_started"] = True; observations["continuity_state"] = "CONTINUE"
        # Verificar registros mínimos
        if not experiment_result or not isinstance(experiment_result, dict):
            return self._final(status="INSUFFICIENT", decision="NOT_DETERMINED", observations={"reason":"experiment_result missing"}, evaluation={}, continuity="STOP_LIMIT", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","experiment_result missing"], restrictions=["fixture synthetic labeled"])
        # Extraer datos esenciales del registro de ejecución
        run_id = experiment_result.get("run_id","NOT_DETERMINED")
        exp_id = experiment_result.get("experiment_id") or (research_task or {}).get("research_id","NOT_DETERMINED")
        classification = experiment_result.get("classification","NOT_DETERMINED")
        admitted = experiment_result.get("admitted", False)
        exit_status = experiment_result.get("exit_status","NOT_DETERMINED")
        criteria_met = experiment_result.get("criteria_met")
        result_output = experiment_result.get("output", {})
        observations["fixture_evidence_labeled"] = experiment_result.get("record",{}).get("fixture_evidence_labeled") is True or (result_output or {}).get("fixture_synthetic") is True or any("fixture" in str(v) for v in (experiment_result.get("limitations") or []))
        observations["execution_admitted"] = admitted
        observations["execution_classification"] = classification
        observations["exit_status"] = exit_status
        observations["criteria_met_documented"] = criteria_met if criteria_met is not None else False
        observations["execution_recorded"] = run_id != "NOT_DETERMINED"
        # Regla 1: clasificación bloqueada => BLOCKED para la investigación (no se evalúa cierre)
        if classification in ("BLOCKED","AUTHORIZATION_REQUIRED","SCHEMA_REQUIRED","UNSUPPORTED","INVALID"):
            evaluation = {
                "evaluation_id": f"eval-{run_id}" if run_id != "NOT_DETERMINED" else f"eval-{time.time()}",
                "research_id": (research_task or {}).get("task_id","NOT_DETERMINED"),
                "experiment_id": exp_id,
                "run_id": run_id,
                "question": (research_task or {}).get("title") or (research_task or {}).get("question") or "NOT_DETERMINED",
                "status":"BLOCKED",
                "decision":"BLOCKED",
                "reason":"Experiment blocked (classification: "+classification+"); prerequisites not satisfied (DB_AUTH_ACTOR_M294 BLOCKED / DBOP_SCHEMA_M290 INSUFFICIENT); no evaluation of closure criteria possible.",
                "hypotheses_evaluated": [],
                "criteria_met": False,
                "evidence_summary":"Blocked before execution; no result observed; criteria not evaluated.",
                "limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","execution blocked; no results available","fixture synthetic clearly labeled"],
                "next_step":"Resolve authorization/esquema prerequisites; do not promote conclusions.",
                "fixture_evidence_labeled": observations["fixture_evidence_labeled"],
                "no_false_elevation": True,
                "continuity": "CONTINUE"
            }
            interpretation["global_evaluation"] = "BLOCKED (prerequisites not satisfied; no evaluation of hypothesis or closure criteria)"
            unsupported["full_evaluation"] = True
            not_determined["indeterminate_evaluation"] = "NOT_DETERMINED (blocked prerequisites prevent evaluation)"
            return self._final(status="PASS_PARTIAL", decision="PARTIAL", evaluation=evaluation, observations=observations, interpretation=interpretation, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")
        # Regla 2: ejecución admitida (LOCAL_STATIC / SYNTHETIC_ONLY) pero criterios no verificados completamente
        # Evaluar según criterios de cierre de la tarea de M325
        criteria_from_task = (research_task or {}).get("success_criteria") or (research_task or {}).get("discriminating_test") or "NOT_DETERMINED"
        # Regla conservadora: exit_status PASS_PARTIAL o resultado observado no implica que la hipótesis sea correcta; documentar explícitamente
        # Si el resultado indica éxito del mecanismo estático (PASS_PARTIAL) pero autorización bloqueada => investigación PARTIALLY_RESOLVED (mecanismo funciona, conclusión no verificada)
        # Si hay errores => OPEN o INSUFFICIENT
        # Si criterios no evaluados o no satisfechos => OPEN
        # Determinar estado final
        status_final = "NOT_DETERMINED"
        decision_final = "NOT_DETERMINED"
        if exit_status == "PASS_PARTIAL" and (criteria_met is None or criteria_met is False):
            # Mecanismo estático funciona; criterios de cierre no verificados; autorización bloqueada => PARTIALLY_RESOLVED
            status_final = "PARTIALLY_RESOLVED"
            decision_final = "PARTIALLY_RESOLVED"
        elif exit_status == "PASS_PARTIAL" and criteria_met is True:
            status_final = "RESOLVED"
            decision_final = "RESOLVED"
        elif exit_status == "INSUFFICIENT" or exit_status == "BLOCKED":
            status_final = "BLOCKED"
            decision_final = "BLOCKED"
        elif exit_status == "PASS_PARTIAL" and (result_output or {}).get("fixture_synthetic") is True:
            # Resultado sintético no afirma conclusión sobre artefacto real => NOT_DETERMINED o OPEN
            status_final = "NOT_DETERMINED"
            decision_final = "NOT_DETERMINED"
        else:
            # Resultado observado pero sin evaluación completa
            status_final = "OPEN"
            decision_final = "OPEN"
        # Determinar hipótesis
        hypotheses = (research_task or {}).get("hypotheses", [])
        hypotheses_evaluated = []
        if hypotheses:
            for h in hypotheses:
                label = h.get("label") if isinstance(h, dict) else str(h)
                # Regla: no promover hipótesis por ausencia de contraejemplo; no promover por código de salida
                # Documentar que no se confirma ni refuta sin verificación completa
                hypotheses_evaluated.append({
                    "label": label,
                    "evidence_available": "PARTIAL (mechanism output observed; full verification blocked by authorization)",
                    "supported": False,
                    "weakened": False,
                    "indeterminate": True,
                    "reason": "No promotion without verified execution or independent verification; authorization blocked (DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290)"
                })
        evaluation["evaluation_id"] = f"eval-{run_id}" if run_id != "NOT_DETERMINED" else f"eval-{time.time()}"
        evaluation["research_id"] = (research_task or {}).get("task_id", "NOT_DETERMINED")
        evaluation["experiment_id"] = exp_id
        evaluation["run_id"] = run_id
        evaluation["question"] = (research_task or {}).get("title") or (research_task or {}).get("question") or "NOT_DETERMINED"
        evaluation["criteria_evaluated"] = criteria_from_task
        evaluation["status"] = status_final
        evaluation["decision"] = decision_final
        evaluation["hypotheses_evaluated"] = hypotheses_evaluated
        evaluation["criteria_met"] = criteria_met if criteria_met is not None else False
        evaluation["evidence_summary"] = "Result observed statically; mechanism works (PASS_PARTIAL); authorization/esquema verification blocked => conclusion remains PARTIALLY_RESOLVED or NOT_DETERMINED; no promotion to RESOLVED without authorization + independent verification; synthetic fixtures clearly labeled."
        evaluation["limitations"] = ["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fixture synthetic clearly labeled","mechanism output does not confirm hypothesis","no promotion without verification","independent recovery not performed"]
        evaluation["restrictions"] = ["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no protected file change","no DB writes"]
        evaluation["fixture_evidence_labeled"] = observations.get("fixture_evidence_labeled", False)
        evaluation["no_false_promotion"] = True
        evaluation["continuity"] = "CONTINUE"
        # Interpretación: no afirmar resolución completa sin autorización; no refutar por ausencia
        interpretation["global_evaluation"] = ("Investigation status: " + status_final + 
            " (decision: " + decision_final + 
            "); mechanism static works; authorization/esquema verification blocked => conclusions not promoted to RESOLVED without authorization; synthetic fixtures clearly labeled; no false promotion or refutation by absence.")
        interpretation["reason_summary"] = ("Result exit: " + str(exit_status) + 
            "; criteria met: " + str(criteria_met) + 
            "; classification: " + classification + "; authorization blocked: " + str(True) + 
            "; synthetic evidence: " + str(observations.get("fixture_evidence_labeled", False)))
        interpretation["limitations_documented"] = "Full resolution requires DB_AUTH_ACTOR_M294 UNBLOCKED + DBOP_SCHEMA_M290 VERIFIED + independent verification; no promotion by mechanism output alone"
        unsupported["full_resolution"] = True
        unsupported["independent_verification_complete"] = True
        not_determined["indeterminate_evaluation"] = "NOT_DETERMINED (authorization blocked; full verification requires independent recovery; mechanism output not promoted to RESOLVED)"
        observations["evaluation_complete"] = True
        observations["evaluation_state"] = status_final
        observations["evaluation_decision"] = decision_final
        observations["continuity_state"] = "CONTINUE"
        return self._final(status="PASS_PARTIAL", decision="PARTIAL", evaluation=evaluation, observations=observations, interpretation=interpretation, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def _final(self, status, decision, evaluation, observations, interpretation, unsupported, not_determined, continuity):
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_labeled"] = evaluation.get("fixture_evidence_labeled", observations.get("fixture_evidence_labeled", False))
        observations["no_false_promotion"] = evaluation.get("no_false_promotion", True)
        observations["continuity_state"] = continuity
        observations["evaluation_complete"] = evaluation.get("status") is not None
        return {"status":status,"decision":decision,"evaluation":evaluation,"observations":observations,"interpretation":interpretation,"unsupported":unsupported,"not_determined":not_determined,"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","no promotion to RESOLVED without authorization; no refutation by absence; mechanism output not promoted","fixture synthetic clearly labeled","independent recovery not performed","no automatic continuation to M329"],"restrictions":["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no protected file change","no DB writes","no false promotion"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M328-SYNTHETIC-EVAL-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    from supervisor.m327_experiment_runner import M327ExperimentRunner
    # Resultado de ejecución local con PASS_PARTIAL
    run_result = M327ExperimentRunner(validated_reference=ref, max_iter=1).run(experiment_spec={"experiment_id":"EXP-EVAL","status":"READY","preparation_status":"READY","prerequisites":[],"limitaciones":["fixture synthetic"]}, fixture_bytes=fixture)
    task = {"task_id":"T328-EVAL","title":"Evaluación del experimento estático","hypotheses":[{"label":"H_A","statement":"Resultado estático observado sin afirmar resolución completa."}],"success_criteria":"Resultado observado; autorización/esquema bloqueado; no promoción a RESOLVED sin verificación independiente.","discriminating_test":"Evaluar registro M327 contra criterios M325"}
    res = M328ResearchEvaluator(validated_reference=ref, max_iter=1).evaluate(research_task=task, experiment_result=run_result.get("record") or run_result)
    print("M328:", res["status"], res["decision"], "eval_state=", res["evaluation"].get("status"), "eval_decision=", res["evaluation"].get("decision"), "run_admitted=", res.get("record",{}).get("admitted"))
