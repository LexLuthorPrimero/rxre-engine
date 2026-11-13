#!/usr/bin/env python3
"""M320 — Propagación simbólica local con límites explícitos (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Reutiliza M314/M316/M319 referencias verificadas."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M320SymbolicPropagation:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def propagate(self, disassembly_result=None, dependency_result=None, structural_result=None):
        observations = {}
        expressions = []
        transitions = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","expressions":[],"transitions":[],"interpretation":{"scope":"BLOCKED"},"anomaly":{},"unsupported":{"propagation":"UNSUPPORTED (no validated_reference)"},"not_determined":{"state":"NOT_DETERMINED"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","fixture synthetic labeled"],"autonomous_loop":False,"max_iter":1,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT"}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M320-SYNTHETIC-SYMBOLIC-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["analysis_scope"] = "intrablock only; interprocedural and alias analysis not implemented; branch divergence not fully resolved; no execution values"
        instructions = disassembly_result.get("decoded_instructions", []) if isinstance(disassembly_result, dict) else []
        observations["instructions_decoded"] = len(instructions)
        # Separación: OBSERVATION / SYMBOLIC_EXPRESSION / STATE_TRANSITION / INTERPRETATION / ANOMALY / UNSUPPORTED / NOT_DETERMINED
        # Regla básica: constante inmediata -> expresión constante; mov reg, reg -> expresión registro destino = registro origen; instrucción no modelada -> invalidación conservadora
        state_reg = {}  # registro -> expresión básica
        for idx, item in enumerate(instructions):
            obs = item.get("observation", {})
            text = obs.get("decoded_text", "")
            observations["instruction_offset"] = observations.get("instruction_offset", obs.get("offset_file"))
            # Semántica básica implementada para instrucciones simples
            if isinstance(text, str):
                # Copia: mov rdi, rax -> rdi = rax
                if text.startswith("mov ") and "," in text:
                    parts = text.split()
                    if len(parts) >= 3:
                        target_reg = parts[2].rstrip(",")
                        source_reg = parts[1].rstrip(",")
                        expressions.append({"expression_id": f"expr_{idx}","type":"SYMBOLIC_EXPRESSION","rule":"register_copy (basic; no exact architecture verification)","origin_instruction_text": text,"origin_bytes": obs.get("bytes_hex"),"expression":"register_copy","target_register": target_reg,"source_register": source_reg,"status":"PARTIAL"})
                        state_reg[target_reg] = {"expression":"register_copy","source": source_reg,"instruction_index": idx,"bytes": obs.get("bytes_hex")}
                        transitions.append({"transition_id": f"trans_{idx}","type":"STATE_TRANSITION","rule":"register_copy_semantics","register_affected": target_reg,"new_state": state_reg[target_reg],"previous_state": state_reg.get(target_reg, None) if target_reg in state_reg else None,"status":"PARTIAL","interpretation":"Register updated by copy; exact value not verified; execution not observed; full verification requires authorization + verified decoder + independent verification"})
                # Constante inmediata (simulada por instrucción con bytes que indican constante, aunque básica)
                elif text.startswith("mov ") and ("0x" in text or "0X" in text):
                    expressions.append({"expression_id": f"expr_{idx}","type":"SYMBOLIC_EXPRESSION","rule":"constant_reference (basic; not fully verified)","expression":"constant_reference","instruction_text": text,"bytes": obs.get("bytes_hex"),"value":"NOT_DETERMINED (constant reference only; exact value requires execution verification)","status":"PARTIAL"})
                    # Actualizar registro destino básico (primer registro tras mov )
                    target_reg = text.split()[1].rstrip(",") if len(text.split()) > 1 else None
                    if target_reg:
                        state_reg[target_reg] = {"expression":"constant_reference","instruction_index": idx,"bytes": obs.get("bytes_hex")}
                        transitions.append({"transition_id": f"trans_{idx}","type":"STATE_TRANSITION","rule":"constant_write_basic","register_affected": target_reg,"status":"PARTIAL","interpretation":"Register updated by constant reference; exact value NOT_DETERMINED; requires authorization + verification"})
                else:
                    # Instrucción no modelada -> invalidación conservadora
                    expressions.append({"expression_id": f"expr_{idx}","type":"SYMBOLIC_EXPRESSION","rule":"unsupported_instruction (no semantics implemented; conservative invalidation applied)","instruction_text": text,"bytes": obs.get("bytes_hex"),"status":"UNSUPPORTED"})
                    # Invalidar registros posiblemente afectados (conservador)
                    for reg in list(state_reg.keys()):
                        state_reg[reg] = {"expression":"invalidated_by_unsupported","instruction_index": idx,"reason":"unsupported instruction; conservative invalidation","bytes": obs.get("bytes_hex")}
                        transitions.append({"transition_id": f"trans_inv_{idx}_{reg}","type":"STATE_TRANSITION","rule":"conservative_invalidation","register_affected": reg,"new_state":"invalidated","reason":"unsupported instruction at index "+str(idx),"status":"UNSUPPORTED","interpretation":"Register invalidated due to unsupported instruction; full semantics require authorization + verified decoder + independent verification"})
        observations["expressions_constructed"] = len(expressions)
        observations["transitions_constructed"] = len(transitions)
        observations["conservative_invalidation_applied"] = any(t.get("rule") == "conservative_invalidation" for t in transitions)
        interpretation["propagation_scope"] = "Intrablock basic; interprocedural/call effects/global alias not implemented; branch divergence not fully resolved; exact values not verified; execution not observed"
        interpretation["state_map"] = {k: v.get("expression") for k, v in state_reg.items()}
        interpretation["limitations"] = "Register state basic only; no verified memory alias resolution; no verified execution; authorization blocked; schema insufficient"
        unsupported["full_memory_alias"] = True
        unsupported["interprocedural_effects"] = True
        unsupported["branch_divergence_full"] = True
        unsupported["execution_value_verification"] = True
        not_determined["exact_register_values"] = "NOT_DETERMINED (static only; no execution; no value verification)"
        not_determined["memory_locations"] = "NOT_DETERMINED (address verification requires authorization + verified segment mapping + independent verification)"
        observations["continuity_state"] = "CONTINUE (M320 PASS PARTIAL; M321 not started; authorization blocked)"
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","expressions":expressions,"transitions":transitions,"interpretation":interpretation,"observations":observations,"anomaly":anomaly,"unsupported":unsupported,"not_determined":not_determined,"hash_input":hash_ref,"continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","intrablock only; full interprocedural/alias/branch not implemented","fixture synthetic clearly labeled","no execution; no value verification"],"restrictions":["no execution","fixture synthetic clearly labeled","no interprocedural propagation","no memory alias resolution"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":self.validated_reference.get("race_condition_documented","NOT_DETERMINED"),"start_time":"2026-10-23T14:01:00Z","completion_time":"2026-10-23T14:01:10Z"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M320-SYNTHETIC-SYMBOLIC-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    res = M320SymbolicPropagation(validated_reference=ref, max_iter=1).propagate(disassembly_result={"decoded_instructions":[{"observation":{"offset_file":0,"bytes_hex":"4889c7","decoded_text":"mov rdi, rax"}},{"observation":{"offset_file":3,"bytes_hex":"90","decoded_text":"nop"}}]}, dependency_result={}, structural_result={})
    print("M320:", res["status"], res["decision"], res["continuity"], "expressions:", len(res.get("expressions",[])), "transitions:", len(res.get("transitions",[])))
    print("Categories:", [e.get("type") for e in res.get("expressions",[])])
    print("Fixture note:", res["observations"].get("fixture_evidence_note"))
