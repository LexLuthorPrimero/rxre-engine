#!/usr/bin/env python3
"""M329 — Memoria experimental y reutilización de evidencia (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa resultados M325-M328; almacenamiento local determinista; compatibilidad evaluada sin elevar evidencia."""
import sys, hashlib, json, os, time
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

FORMAT_VERSION = "rxre-v1.0-m329"
CATEGORIES = ["OBSERVED_EXPERIENCE","SYNTHETIC_EXPERIENCE","FAILED_EXPERIMENT","INCONCLUSIVE_EXPERIMENT","BLOCKED_EXPERIMENT","UNVERIFIED_EXPERIENCE"]
REQUIRED = ["experience_id","format_version","category","fixture_evidence_labeled","artifact_identity","continuity","limitations","restrictions","autonomous_loop","max_iter"]

class M329ExperienceStore:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter
        self.store_dir = "/tmp/m329_experiences"
        if not os.path.isdir(self.store_dir): os.makedirs(self.store_dir, exist_ok=True)

    def record(self, evaluation_result=None, research_task=None, experiment_result=None):
        observations = {}
        experience = {}
        interpretation = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", observations={"reason":"validated_reference missing"}, experience={}, continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"], restrictions=["fixture synthetic labeled"])
        observations["hash_input"] = self.validated_reference.get("hash_sha256","")[:16]
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M329-SYNTHETIC-EXPERIENCE-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"; observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["continuity_state"] = "CONTINUE"
        observations["store_local_only"] = True
        observations["no_db_write"] = True
        observations["no_false_causal_inference"] = True
        observations["no_similarity_as_compatibility"] = True
        # Construir registro determinista
        art_identity = (evaluation_result or {}).get("evaluation",{}).get("run_id","")
        # Si hay hash del artefacto en referencia validada, conservarlo
        art_hash = self.validated_reference.get("hash_sha256")
        # Categoría basada en resultado de evaluación (no inventada)
        eval_status = (evaluation_result or {}).get("evaluation",{}).get("status","NOT_DETERMINED")
        if (experiment_result or {}).get("record",{}).get("fixture_evidence_labeled") is True:
            category = "SYNTHETIC_EXPERIENCE"
        elif eval_status == "RESOLVED":
            category = "OBSERVED_EXPERIENCE"
        elif eval_status == "BLOCKED":
            category = "BLOCKED_EXPERIMENT"
        elif eval_status == "INSUFFICIENT":
            category = "UNVERIFIED_EXPERIENCE"
        else:
            # Si es mecanismo observado pero sin resolución completa => OBSERVED pero con limitaciones; o si falló => FAILED; aquí conservador
            # Por defecto: si hay registro de ejecución y está admitido => OBSERVED; si criterio no satisfecho (mecanismo observado) => INCONCLUSIVE
            admitted = (experiment_result or {}).get("record",{}).get("admitted", False)
            exit_stat = (experiment_result or {}).get("record",{}).get("exit_status", "NOT_DETERMINED")
            if admitted and exit_stat == "PASS_PARTIAL" and eval_status not in ("RESOLVED","INSUFFICIENT","NOT_DETERMINED"):
                category = "INCONCLUSIVE_EXPERIMENT"
            elif admitted and (exit_stat == "INSUFFICIENT" or exit_stat == "BLOCKED"):
                category = "FAILED_EXPERIMENT"
            else:
                category = "UNVERIFIED_EXPERIENCE"
        experience["experience_id"] = f"EXP-{art_identity}" if art_identity else f"EXP-{time.time()}"
        experience["format_version"] = FORMAT_VERSION
        experience["category"] = category
        experience["fixture_evidence_labeled"] = (experiment_result or {}).get("record",{}).get("fixture_evidence_labeled", observations.get("fixture_evidence_note") == "Fixture synthetic clearly labeled (M329-SYNTHETIC-EXPERIENCE-FIXTURE); not real artifact evidence")
        experience["artifact_identity"] = art_hash or "NOT_DETERMINED"
        experience["continuity"] = "CONTINUE"
        experience["limitations"] = ["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fixture synthetic clearly labeled","similarity is not compatibility","independent verification required for reuse","no causal inference from single experience"]
        experience["restrictions"] = ["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no DB writes","no false mechanism","no protected file change"]
        experience["autonomous_loop"] = False
        experience["max_iter"] = self.max_iter
        experience["db_auth_actor_m294"] = "BLOCKED"
        experience["dbop_schema_m290"] = "INSUFFICIENT"
        experience["race_condition_documented"] = self.validated_reference.get("race_condition_documented","NOT_DETERMINED")
        # Procedencia / referencias
        experience["provenance_refs"] = {
            "research_task_id": (research_task or {}).get("task_id"),
            "experiment_id": (experiment_result or {}).get("record",{}).get("experiment_id"),
            "run_id": (experiment_result or {}).get("record",{}).get("run_id"),
            "pipeline_reference": observations.get("hash_input"),
            "fixture_evidence_note": observations.get("fixture_evidence_note"),
        }
        # Observaciones de ejecución (conservador: no afirmar resultados como hechos)
        experience["observations"] = {
            "evaluation_status": eval_status,
            "execution_admitted": (experiment_result or {}).get("record",{}).get("admitted"),
            "execution_classification": (experiment_result or {}).get("record",{}).get("classification"),
            "exit_status": (experiment_result or {}).get("record",{}).get("exit_status"),
            "criteria_met": (experiment_result or {}).get("record",{}).get("criteria_met"),
            "fixture_synthetic": observations.get("fixture_evidence_labeled"),
            "independent_verification": False
        }
        # Hipótesis (del plan) y su respaldo (no modificado automáticamente)
        experience["hypotheses"] = (research_task or {}).get("hypotheses", [])
        experience["evaluation_result"] = evaluation_result if (evaluation_result is not None and isinstance(evaluation_result, dict)) else {"status":"NOT_DETERMINED","reason":"evaluation_result missing or invalid"}
        # Guardar archivo local (solo local, sin DB)
        path = os.path.join(self.store_dir, experience.get("experience_id") + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"experience": experience, "hash_input": art_hash}, f, sort_keys=True, indent=2, ensure_ascii=False)
        observations["store_path"] = path
        observations["record_written"] = True
        observations["experience_category"] = category
        observations["no_false_elevation"] = True
        observations["similarity_is_not_compatibility"] = True
        interpretation["reuse_note"] = f"Experience category: {category}; synthetic fixture labeled; similarity is not compatibility; reuse requires verified prerequisites + independent recovery; no promotion by similarity alone."
        interpretation["evidence_note"] = "Single experience does not prove behavior; independent verification required; authorization blocked (DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290)."
        unsupported["full_compatibility_verification"] = True
        unsupported["independent_recovery"] = True
        unsupported["behavioral_inference"] = True
        not_determined["reuse_compatibility"] = "NOT_DETERMINED (similarity is not compatibility; prerequisites blocked; independent verification required)"
        return self._final(status="PASS_PARTIAL", decision="PARTIAL", observations=observations, experience=experience, interpretation=interpretation, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def retrieve(self, query_criteria=None):
        observations = {}
        results = []
        observations["query_criteria"] = query_criteria or {}
        observations["store_dir_exists"] = os.path.isdir(self.store_dir)
        observations["experience_files_found"] = 0
        observations["no_db_used"] = True
        observations["autonomous_loop"] = False; observations["max_iter"] = 1
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_labeled"] = True
        observations["similarity_not_compatibility"] = True
        observations["continuity_state"] = "CONTINUE"
        if not os.path.isdir(self.store_dir):
            observations["store_dir_exists"] = False
            return {"status":"INSUFFICIENT","decision":"NOT_DETERMINED","results":results,"observations":observations,"interpretation":{"scope":"INSUFFICIENT (store directory missing)"},"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","store not available"],"restrictions":["fixture synthetic labeled","autonomous_loop=False","max_iter=1","op_claim=False"],"continuity":"CONTINUE","autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}
        files = [f for f in os.listdir(self.store_dir) if f.endswith(".json")]
        observations["experience_files_found"] = len(files)
        # Recuperar todos y filtrar por criterios básicos (sin inferir causalidad)
        for fname in files:
            path = os.path.join(self.store_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                exp = data.get("experience", {})
                # Verificar integridad mínima: debe tener categoría y experiencia válida
                if exp and isinstance(exp, dict) and "category" in exp:
                    results.append({"experience_id": exp.get("experience_id"),"path":path,"category":exp.get("category"),"artifact_identity":exp.get("artifact_identity"),"fixture_evidence_labeled":exp.get("fixture_evidence_labeled"),"provenance_refs":exp.get("provenance_refs",{}),"observations":exp.get("observations",{}),"evaluation_result":exp.get("evaluation_result",{}),"continuity":"CONTINUE"})
            except Exception as e:
                # No modificar archivo; no corregir; documentar
                observations["read_exception"] = observations.get("read_exception", []) + [str(e)]
        # Filtrar por query_criteria básico (determinista)
        if query_criteria:
            if query_criteria.get("category"):
                results = [r for r in results if r.get("category") == query_criteria.get("category")]
            if query_criteria.get("fixture_evidence_labeled") is not None:
                results = [r for r in results if r.get("fixture_evidence_labeled") == query_criteria.get("fixture_evidence_labeled")]
            if query_criteria.get("artifact_identity"):
                results = [r for r in results if r.get("artifact_identity") == query_criteria.get("artifact_identity")]
        observations["retrieved_count"] = len(results)
        observations["retrieved_ids"] = [r.get("experience_id") for r in results]
        observations["no_similarity_as_compatibility"] = True
        observations["no_false_compatibility"] = True
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","results":results,"observations":observations,"interpretation":{"scope":"Experiences retrieved deterministically; similarity is not compatibility; reuse requires verified prerequisites; authorization blocked","count":len(results)},"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","similarity is not compatibility","independent verification required for reuse","fixture synthetic clearly labeled","store local only (no DB)"],"restrictions":["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no DB writes","no protected file change","no false mechanism"],"continuity":"CONTINUE","autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

    def evaluate_compatibility(self, experience_a=None, experience_b=None):
        observations = {}
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"; observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_labeled"] = True; observations["similarity_not_compatibility"] = True
        observations["continuity_state"] = "CONTINUE"
        observations["store_local_only"] = True
        observations["no_false_compatibility"] = True
        observations["no_false_reuse"] = True
        if not experience_a or not experience_b:
            observations["compatibility_result"] = "INSUFFICIENT (missing experience input)"
            observations["reason"] = "No compatibility without both inputs; prerequisites blocked (DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290)"
            observations["recommended_action"] = "BLOCKED (prerequisites missing)"
            return {"status":"INSUFFICIENT","decision":"NOT_DETERMINED","observations":observations,"compatibility_result":"INSUFFICIENT","continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","missing input"],"restrictions":["fixture synthetic labeled","autonomous_loop=False","max_iter=1","op_claim=False","no DB writes"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}
        # Comparación determinista basada en propiedades estructurales, no en similitud de texto
        identity_match = (experience_a.get("artifact_identity") == experience_b.get("artifact_identity"))
        synthetic_match = (experience_a.get("fixture_evidence_labeled") == experience_b.get("fixture_evidence_labeled"))
        category_a = experience_a.get("category")
        category_b = experience_b.get("category")
        observations["identity_match"] = identity_match
        observations["fixture_evidence_match"] = synthetic_match
        observations["category_a"] = category_a
        observations["category_b"] = category_b
        observations["similar_text_not_compatibility"] = True
        if not identity_match:
            observations["compatibility_result"] = "INCOMPATIBLE (artifact identity different)"
            observations["recommended_action"] = "NOT_SUPPORTED (cross-artifact reuse not supported without independent verification)"
            observations["reason"] = "Different artifacts; similarity is not compatibility; reuse requires verified prerequisites and independent recovery."
            compatibility_final = "INCOMPATIBLE"
            action = "NOT_SUPPORTED"
        elif category_a == "SYNTHETIC_EXPERIENCE" or category_b == "SYNTHETIC_EXPERIENCE":
            observations["compatibility_result"] = "PARTIAL (synthetic experience; compatibility limited; no promotion to real artifact evidence)"
            observations["recommended_action"] = "BLOCKED (synthetic evidence; authorization/esquema required for real artifact verification)"
            observations["reason"] = "Synthetic fixtures clearly labeled; similarity is not compatibility; reuse requires authorization + verification."
            compatibility_final = "PARTIAL"
            action = "BLOCKED"
        else:
            # Si identidad coincide y categorías compatibles pero requisitos bloqueados => PARTIAL / BLOCKED para reutilización
            observations["compatibility_result"] = "PARTIAL (compatible identity; prerequisites blocked; authorization/esquema insufficient for reuse confirmation)"
            observations["recommended_action"] = "BLOCKED (prerequisites not satisfied; independent verification required before reuse)"
            observations["reason"] = "Compatible identity; authorization/esquema blocked (DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290); reuse requires verification + authorization."
            compatibility_final = "PARTIAL"
            action = "BLOCKED"
        observations["no_false_compatibility"] = True
        observations["continuity_state"] = "CONTINUE"
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","compatibility_result":compatibility_final,"recommended_action":action,"observations":observations,"continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","similarity is not compatibility","reuse requires authorization + verification","fixture synthetic clearly labeled"],"restrictions":["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no DB writes","no protected file change","no false mechanism"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

    def _final(self, status, decision, observations, experience=None, interpretation=None, unsupported=None, not_determined=None, continuity="CONTINUE"):
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["continuity_state"] = continuity
        observations["fixture_evidence_labeled"] = observations.get("fixture_evidence_labeled", False)
        observations["store_local_only"] = observations.get("store_local_only", True)
        observations["no_false_mechanism"] = True
        return {"status":status,"decision":decision,"observations":observations,"experience":experience or {},"interpretation":interpretation or {},"unsupported":unsupported or {},"not_determined":not_determined or {},"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","store local only (no DB)","similarity is not compatibility","fixture synthetic clearly labeled","reuse requires authorization + verification","independent verification required"],"restrictions":["autonomous_loop=False","max_iter=1","op_claim=False","fixture synthetic labeled","no protected file change","no DB writes","no false mechanism","no execution"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M329-SYNTHETIC-EXPERIENCE-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    store = M329ExperienceStore(validated_reference=ref, max_iter=1)
    # Simular registro de experiencia con evaluación sintética
    from supervisor.m328_research_evaluator import M328ResearchEvaluator
    eval_res = M328ResearchEvaluator(validated_reference=ref, max_iter=1).evaluate(research_task={"task_id":"T329","title":"Experiencia sintética","hypotheses":[{"label":"H_A","statement":"Resultado estático observado"}],"success_criteria":"Observación"}, experiment_result={"record":{"experiment_id":"EXP-SYNTH","admitted":True,"fixture_evidence_labeled":True,"exit_status":"PASS_PARTIAL","classification":"LOCAL_STATIC","criteria_met":False}})
    record_res = store.record(evaluation_result=eval_res, research_task={"task_id":"T329","title":"Experiencia sintética","hypotheses":[{"label":"H_A","statement":"Resultado estático observado"}],"success_criteria":"Observación"}, experiment_result={"record":{"experiment_id":"EXP-SYNTH","admitted":True,"fixture_evidence_labeled":True,"exit_status":"PASS_PARTIAL","classification":"LOCAL_STATIC","criteria_met":False}})
    print("M329 record:", record_res.get("status"), record_res.get("decision"), "experience_id=", record_res.get("experience",{}).get("experience_id"), "category=", record_res.get("experience",{}).get("category"))
    # Recuperar
    retrieve_res = store.retrieve(query_criteria={"category":"SYNTHETIC_EXPERIENCE","fixture_evidence_labeled":True})
    print("M329 retrieve:", retrieve_res.get("status"), retrieve_res.get("decision"), "count=", retrieve_res.get("observations",{}).get("retrieved_count"), "ids=", retrieve_res.get("observations",{}).get("retrieved_ids"))
    # Evaluar compatibilidad
    exp_a = {"experience_id":"EXP-A","category":"OBSERVED_EXPERIENCE","artifact_identity":"hash1","fixture_evidence_labeled":False,"continuity":"CONTINUE"}
    exp_b = {"experience_id":"EXP-B","category":"SYNTHETIC_EXPERIENCE","artifact_identity":"hash2","fixture_evidence_labeled":True,"continuity":"CONTINUE"}
    compat = store.evaluate_compatibility(experience_a=exp_a, experience_b=exp_b)
    print("M329 compatibility:", compat.get("status"), compat.get("decision"), "compatibility_result=", compat.get("compatibility_result"), "recommended_action=", compat.get("recommended_action"))
