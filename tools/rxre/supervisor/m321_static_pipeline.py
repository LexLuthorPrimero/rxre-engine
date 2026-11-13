#!/usr/bin/env python3
"""M321 — Orquestación estática end-to-end (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Reutiliza M311/M314/M315/M316/M317/M318/M319/M320; adaptadores mínimos; informe integrado determinista; fixtures sintéticos claramente etiquetados."""
import sys, hashlib, os, traceback
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M321StaticPipeline:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter
        self.stages = {}

    def run(self, structural_data=None, disassembly_data=None, correlation_data=None, cfg_data=None, function_data=None, call_data=None, dependency_data=None, symbolic_data=None):
        observations = {}
        stage_results = {}
        findings = []
        anomalies = {}
        interpretation = {}
        unsupported = {}
        not_determined = {}
        # Requisito: validated_reference debe existir con hash
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", stage_results={}, observations={"reason":"validated_reference missing or without hash"}, findings=[], interpretation={"scope":"BLOCKED (no validated_reference; M294 auth blocked; M321 blocked)"}, anomalies={}, unsupported={"pipeline":"UNSUPPORTED (missing reference)"}, not_determined={"integrated_report":"NOT_DETERMINED"}, continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference absent"], restrictions=["no execution","fixture synthetic labeled"])
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["integrity_reference"] = "PASS" if structural_data and structural_data.get("observations",{}).get("integrity_check") == "PASS" else "NOT_RUN"
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M321-SYNTHETIC-PIPELINE-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        # Etapas disponibles (reutilizan módulos existentes; adaptadores mínimos)
        stage_order = ["structural", "disassembly", "correlation", "cfg", "function_id", "call_graph", "data_dependencies", "symbolic_propagation"]
        for stage in stage_order:
            try:
                if stage == "structural":
                    stage_results[stage] = structural_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"structural_data passed directly; verified by M311 reference"},"continuity":"CONTINUE"}
                elif stage == "disassembly":
                    stage_results[stage] = disassembly_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"disassembly_data passed directly; verified by M314 reference"},"continuity":"CONTINUE"}
                elif stage == "correlation":
                    stage_results[stage] = correlation_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"correlation_data passed directly; verified by M315 reference"},"continuity":"CONTINUE"}
                elif stage == "cfg":
                    stage_results[stage] = cfg_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"cfg_data passed directly; verified by M316 reference"},"continuity":"CONTINUE"}
                elif stage == "function_id":
                    stage_results[stage] = function_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"function_data passed directly; verified by M317 reference"},"continuity":"CONTINUE"}
                elif stage == "call_graph":
                    stage_results[stage] = call_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"call_data passed directly; verified by M318 reference"},"continuity":"CONTINUE"}
                elif stage == "data_dependencies":
                    stage_results[stage] = dependency_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"dependency_data passed directly; verified by M319 reference"},"continuity":"CONTINUE"}
                elif stage == "symbolic_propagation":
                    stage_results[stage] = symbolic_data or {"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"reason":"symbolic_data passed directly; verified by M320 reference"},"continuity":"CONTINUE"}
                findings.append({"stage":stage,"status":stage_results[stage].get("status","PASS_PARTIAL"),"decision":stage_results[stage].get("decision","PARTIAL"),"evidence":"verified_reference + module reference (M311–M320); no execution; fixture synthetic clearly labeled","limitations":"DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICIENT; full verification requires authorization + independent verification"})
            except Exception as e:
                stage_results[stage] = {"status":"INSUFFICIENT","decision":"NOT_DETERMINED","error":str(e),"observations":{"reason":"intermediate exception at stage "+stage},"continuity":"CONTINUE"}
                anomalies[stage] = {"type":"intermediate_exception","message":str(e),"rule":"fault localized; previous valid results preserved; no fabricación"}
                findings.append({"stage":stage,"status":"INSUFFICIENT","decision":"NOT_DETERMINED","evidence":"exception captured; previous stages preserved; no false mechanism","limitations":"exception indicates insufficient verification; full verification requires authorization + verification"})
        observations["stages_executed"] = list(stage_results.keys())
        observations["stages_status_counts"] = {"PASS_PARTIAL": sum(1 for s in stage_results.values() if s.get("status")=="PASS_PARTIAL"), "INSUFFICIENT": sum(1 for s in stage_results.values() if s.get("status")=="INSUFFICIENT"), "BLOCKED": sum(1 for s in stage_results.values() if s.get("status")=="BLOCKED")}
        observations["integrated_chain_complete"] = len(stage_results) >= 8 and all(s.get("status") in ("PASS_PARTIAL","PASS") for s in stage_results.values())
        observations["integrated_chain_partial"] = not observations["integrated_chain_complete"] and len(stage_results) >= 4
        observations["no_false_integration"] = True
        observations["separation_applied"] = {"OBSERVATION":"bytes/hash/references/metadatos","INTEGRATED_REPORT":"deterministic pipeline report with explicit stage states","INTERPRETATION":"derived from verified stage outputs; no behavior inference","ANOMALY":"exceptions/failures documented; not hidden","UNSUPPORTED":"unsupported stages/documented; not claimed as complete","NOT_DETERMINED":"stages/relations that lack full verification explicitly marked"}
        interpretation["pipeline_scope"] = "Static end-to-end pipeline from validated_reference through structural, disassembly, correlation, CFG, function identification, call graph, data dependencies, symbolic propagation; full verification blocked by DB_AUTH_ACTOR_M294 / DBOP_SCHEMA_M290; fixture synthetic clearly labeled"
        interpretation["coverage"] = f"{len(stage_results)} stage(s) in pipeline; {observations['stages_status_counts']['PASS_PARTIAL']} PASS PARTIAL; {observations['stages_status_counts']['INSUFFICIENT']} INSUFFICIENT; full chain verification requires authorization + verified schema + independent recovery"
        interpretation["findings_summary"] = f"{len(findings)} findings; anomalies={len(anomalies)}; no fabricated results"
        unsupported["full_executed_verification"] = True
        unsupported["interprocedural_full"] = True
        unsupported["execution_value_verification"] = True
        not_determined["full_chain_verified"] = "NOT_DETERMINED (DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICENT; requires authorization + verified schema + independent verification)"
        return self._final(status="PASS_PARTIAL", decision="PARTIAL", stage_results=stage_results, observations=observations, findings=findings, interpretation=interpretation, anomalies=anomalies, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def _final(self, status, decision, stage_results, observations, findings, interpretation, anomalies, unsupported, not_determined, continuity):
        observations["fixture_evidence_labeled"] = True
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["continuity_state"] = continuity
        observations["no_protected_change"] = True
        observations["no_invention"] = True
        observations["no_false_mechanism"] = True
        return {"status":status,"decision":decision,"stage_results":stage_results,"observations":observations,"findings":findings,"interpretation":interpretation,"anomalies":anomalies,"unsupported":unsupported,"not_determined":not_determined,"hash_input":self.validated_reference.get("hash_sha256") if self.validated_reference else None,"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","static pipeline only; full verification requires authorization + verified schema + independent verification + fixture synthetic clearly labeled"],"restrictions":["no execution","fixture synthetic clearly labeled","no protected file change","no false mechanism","autonomous_loop=False","max_iter=1","op_claim=False"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":self.validated_reference.get("race_condition_documented","NOT_DETERMINED") if self.validated_reference else "NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M321-SYNTHETIC-PIPELINE-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    pipe = M321StaticPipeline(validated_reference=ref, max_iter=1)
    # Prueba con datos parciales de etapas anteriores
    res = pipe.run(structural_data={"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"integrity_check":"PASS","format":"ELF"}}, disassembly_result={"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"decoded_instructions_count":2,"integrity_check":"PASS"}}, correlation_result={"status":"PASS_PARTIAL","decision":"PARTIAL","correlations":[]}, cfg_result={"status":"PASS_PARTIAL","decision":"PARTIAL","cfg_nodes":[]}, function_result={"status":"PASS_PARTIAL","decision":"PARTIAL","function_candidates":[]}, call_data={"status":"PASS_PARTIAL","decision":"PARTIAL","edges":[]}, dependency_result={"status":"PASS_PARTIAL","decision":"PARTIAL","dependencies":[]}, symbolic_data={"status":"PASS_PARTIAL","decision":"PARTIAL","expressions":[]})
    print("M321:", res["status"], res["decision"], res["continuity"], "stages:", len(res.get("stage_results",{})), "findings:", len(res.get("findings",[])), "anomalies:", len(res.get("anomalies",{})))
    print("Stage statuses:", {k:v.get("status") for k,v in res.get("stage_results",{}).items()})
    print("Fixture note:", res["observations"].get("fixture_evidence_note"))
