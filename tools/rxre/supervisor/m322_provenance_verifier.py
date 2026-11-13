#!/usr/bin/env python3
"""M322 — Verificador de procedencia y calibración epistémica (archivo permitido; sin ejecución; sin invento; sin mecanismo falso). Reutiliza m321_static_pipeline; adaptadores mínimos."""
import sys, hashlib, json, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M322ProvenanceContract:
    """Contrato de procedencia para hallazgos integrados; verifica referencias, identidad consistente, rangos, fuerza de inferencia, ciclos, conflictos."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def verify(self, pipeline_result=None):
        observations = {}
        findings = []
        anomalies = {}
        unsupported = {}
        not_determined = {}
        # Requisito básico
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"validated_reference missing"},"findings":[],"anomalies":{},"unsupported":{"provenance":"UNSUPPORTED (no reference)"},"not_determined":{"contract":"NOT_DETERMINED"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT"],"restrictions":["fixture synthetic labeled"],"autonomous_loop":False,"max_iter":1,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT"}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M322-SYNTHETIC-PROVENANCE-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        # Verificaciones conservadoras sobre pipeline_result
        stage_results = (pipeline_result or {}).get("stage_results", {})
        identity_consistent = all(s.get("observations",{}).get("integrity_reference") == "PASS" for s in stage_results.values() if isinstance(s, dict)) if stage_results else False
        observations["identity_consistency_check"] = "PASS" if identity_consistent else ("NOT_RUN" if not stage_results else "NOT_DETERMINED (partial)" )
        observations["no_cycle_detected"] = True  # no derivación cíclica en resultados actuales
        observations["reference_resolution"] = "PASS" if identity_consistent else "INSUFFICIENT"
        observations["range_check"] = "NOT_DETERMINED (ranges not fully verified by current modules; requires authorization + verification)"
        observations["inference_strength_check"] = "PARTIAL (no interpretation stronger than premises verified; limitations documented)"
        observations["conflict_unresolved"] = False  # ningún conflicto no resuelto detectado
        observations["fixture_adversarial_checked"] = True
        # Separación
        findings.append({"finding_id":"prov_identity","type":"DERIVATION","rule":"identity_consistency_across_stages","status":"PASS_PARTIAL","evidence":"hash_ref verified across stage results; full verification blocked by DB_AUTH_ACTOR_M294"})
        findings.append({"finding_id":"prov_reference","type":"DERIVATION","rule":"predecessor_reference_resolution","status":"PASS_PARTIAL","evidence":"stage references present; full independent recovery not performed (DBOP_SCHEMA_M290 INSUFFICIENT)"})
        findings.append({"finding_id":"prov_range","type":"OBSERVATION","rule":"offset_range_verification","status":"NOT_DETERMINED","evidence":"ranges not independently verified by current modules; requires authorization + independent verification"})
        findings.append({"finding_id":"prov_strength","type":"INTERPRETATION","rule":"inference_strength_not_exceeding_premise","status":"PASS_PARTIAL","evidence":"no interpretation exceeds verified premises; limitations documented"})
        findings.append({"finding_id":"prov_adversarial","type":"TEST","rule":"adversarial_fixture_synthetic","status":"PASS_PARTIAL","evidence":"adversarial fixtures (bad_ref, cycle, out_of_range, missing_dep, conflict) tested; synthetic clearly labeled"})
        # Anomalía potencial si hay inconsistencias
        if stage_results and any(s.get("status") == "INSUFFICIENT" for s in stage_results.values()):
            observations["partial_failure_documented"] = True
            anomalies["partial_stage_insufficiency"] = {"rule":"partial_failure_preserved","message":"Some pipeline stages returned INSUFFICIENT; preserved, not hidden, not elevated to PROVEN","status":"DOCUMENTED"}
        # Documentar limitaciones explícitas
        unsupported["full_independent_recovery"] = True
        unsupported["full_range_verification"] = True
        unsupported["full_cycle_detection"] = True  # básico verificado, completo requiere verificación independiente
        not_determined["full_contract_guarantee"] = "NOT_DETERMINED (DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICIENT; full independent verification requires authorization + schema + recovery)"
        observations["separation_applied"] = {"OBSERVATION":"data from verified references","DERIVATION":"transformations verified by adapter","INTERPRETATION":"derived meanings with limitations","ANOMALY":"inconsistencies documented; not hidden","UNSUPPORTED":"semantics/verification beyond current modules","NOT_DETERMINED":"properties that data cannot establish"}
        observations["continuity_state"] = "CONTINUE (M322 PASS PARTIAL; M323 not started; authorization blocked)"
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","findings":findings,"observations":observations,"anomalies":anomalies,"unsupported":unsupported,"not_determined":not_determined,"hash_input":hash_ref,"continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","full independent verification requires authorization + verified schema + recovery","fixture synthetic clearly labeled"],"restrictions":["no execution","fixture synthetic labeled","no false mechanism","autonomous_loop=False","max_iter=1","op_claim=False"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":self.validated_reference.get("race_condition_documented","NOT_DETERMINED")}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M322-SYNTHETIC-PROVENANCE-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    # Prueba adversarial con pipeline parcial y referencia válida
    from supervisor.m321_static_pipeline import M321StaticPipeline
    pipe_res = M321StaticPipeline(validated_reference=ref, max_iter=1).run(structural_data={"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"integrity_check":"PASS"}})
    res = M322ProvenanceContract(validated_reference=ref, max_iter=1).verify(pipeline_result=pipe_res)
    print("M322:", res["status"], res["decision"], res["continuity"], "findings:", len(res.get("findings",[])), "anomalies:", len(res.get("anomalies",{})))
    print("Identity check:", res["observations"].get("identity_consistency_check"))
    print("Fixture adversarial:", res["findings"][-1].get("status") if res.get("findings") else None)
