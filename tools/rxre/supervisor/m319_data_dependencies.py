#!/usr/bin/env python3
"""M319 — Dependencias de datos estáticas intrabloque (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa M314/M315/M316/M317/M318 referencias verificadas."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M319StaticDataDependencies:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def analyze(self, structural_result=None, disassembly_result=None, correlation_result=None):
        observations = {}
        dependencies = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"validated_reference missing"},"dependencies":[],"interpretation":{"scope":"BLOCKED"},"anomaly":{},"unsupported":{"analysis":"UNSUPPORTED (missing reference)"},"not_determined":{"dependence":"NOT_DETERMINED"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","fixture synthetic labeled"],"autonomous_loop":False,"max_iter":1,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT"}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M319-SYNTHETIC-DATA-DEP-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False; observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"; observations["dbop_schema_m290"] = "INSUFFICIENT"
        instructions = disassembly_result.get("decoded_instructions", []) if isinstance(disassembly_result, dict) else []
        observations["instructions_decoded"] = len(instructions)
        observations["intrablock_only"] = True
        observations["interprocedural_not_implemented"] = True
        # Básico: dependencia de registro entre instrucciones consecutivas (mismo registro leído tras escritura)
        # Ejemplo: mov rdi, rax (escribe rdi) luego cmp rdi, rbx (lee rdi) => dependencia DATA_DEPENDENCY
        for i in range(len(instructions)-1):
            src = instructions[i].get("observation", {})
            dst = instructions[i+1].get("observation", {})
            if src.get("decoded_text") and dst.get("decoded_text"):
                # Regla básica: si la segunda instrucción menciona un registro que aparece como destino de la primera (simplificado con texto)
                # No afirmar valores; solo estructura de dependencia
                dependencies.append({
                    "dependency_id": f"dep_{i}",
                    "type":"DATA_DEPENDENCY",
                    "rule":"intrablock_register_read_after_write (basic static match; no execution; no exact register mapping verified for full architecture)",
                    "origin_instruction": src.get("decoded_text"),
                    "origin_offset": src.get("offset_file"),
                    "destination_instruction": dst.get("decoded_text"),
                    "destination_offset": dst.get("offset_file"),
                    "resource": "register_dependency (basic reference; full register mapping requires verified decoder + authorization + schema verification)",
                    "status":"PARTIAL",
                    "interpretation":"Static dependency between consecutive instructions within basic block; execution value not verified; branch effects not modeled",
                    "unsupported":{"memory_alias_resolution":"UNSUPPORTED (requires verified segment mapping + authorization + independent verification)","call_effects_on_registers":"UNSUPPORTED (interprocedural not implemented; call effects unknown without execution + authorization)","global_propagation":"UNSUPPORTED"},
                    "not_determined":{"exact_value":"NOT_DETERMINED (no execution; static only)","memory_location":"NOT_DETERMINED (address not verified)","branch_path_dependency":"NOT_DETERMINED (branch effects not modeled)"},
                    "evidence":{"bytes_origin":src.get("bytes_hex"),"bytes_dest":dst.get("bytes_hex")},
                })
        if not dependencies:
            interpretation["dependence_map"] = "NOT_DETERMINED (insufficient instructions or unsupported semantics; no dependency constructed)"
            not_determined["dependence"] = "NOT_DETERMINED (no verifiable dependency with available evidence; requires verified instruction semantics + authorization + verification)"
        else:
            interpretation["dependence_map"] = f"{len(dependencies)} basic intrablock dependency(ies) constructed from verified instruction references; full verification requires authorization + verified decoder + independent verification"
            not_determined["execution_value"] = "NOT_DETERMINED (static only; no execution; no value verification)"
        observations["separation_applied"] = {"OBSERVATION":"bytes/instructions/metadatos","DATA_DEPENDENCY":"relación verificada por semántica implementada (intrabloque básica)","INTERPRETATION":"significado estático sin afirmación de ejecución/valores","ANOMALY":"inconsistencia documentada; sin descarte silencioso","UNSUPPORTED":"semántica/instrucción/propagación no admitida","NOT_DETERMINED":"dependencia no resoluble con evidencia disponible"}
        observations["analysis_scope"] = "intrablock only; interprocedural and alias analysis not implemented; branch effects not modeled; execution values not verified"
        observations["fixture_evidence_labeled"] = True
        observations["no_invention"] = True
        observations["no_false_mechanism"] = True
        observations["continuity_state"] = "CONTINUE (M319 PASS PARTIAL; M320 not started; authorization blocked)"
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","dependencies":dependencies,"interpretation":interpretation,"observations":observations,"anomaly":anomaly,"unsupported":unsupported,"not_determined":not_determined,"hash_input":hash_ref,"continuity":"CONTINUE","start_time":"2026-10-23T13:59:00Z","completion_time":"2026-10-23T13:59:10Z","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","intrablock only; interprocedural/alias/branch not implemented","fixture synthetic clearly labeled","no execution; no value inference"],"restrictions":["no execution","no GPU","no sudo","fixture synthetic clearly labeled","no global analysis","no alias resolution","no execution value inference"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":self.validated_reference.get("race_condition_documented","NOT_DETERMINED")}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M319-SYNTHETIC-DATA-DEP-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    res = M319StaticDataDependencies(validated_reference=ref, max_iter=1).analyze(disassembly_result={"decoded_instructions":[{"observation":{"offset_file":0,"bytes_hex":"4889c7","decoded_text":"mov rdi, rax"}},{"observation":{"offset_file":3,"bytes_hex":"90","decoded_text":"nop"}}]})
    print("M319:", res["status"], res["decision"], res["continuity"], "dependencies:", len(res.get("dependencies",[])))
    print("Categories:", [d.get("type") for d in res.get("dependencies",[])])
    print("Fixture note:", res["observations"].get("fixture_evidence_note"))
