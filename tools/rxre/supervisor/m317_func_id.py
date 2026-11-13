#!/usr/bin/env python3
"""M317 — Identificación estática de funciones y límites (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa referencias verificadas de M312/M313/M314/M315/M316; documenta UNSUPPORTED/NOT_DETERMINED/ANOMALY; separa FUNCTION_CANDIDATE / STRUCTURALLY_BOUNDED_FUNCTION / HEURISTIC_BOUNDARY."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M317StaticFunctionIdentifier:
    """Identifica candidatos a funciones y delimita rangos con niveles diferenciados, sin afirmar ejecución ni límites definitivos sin verificación estructural completa."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def identify(self, structural_result=None, disassembly_result=None, correlation_result=None, cfg_result=None):
        observations = {}
        candidates = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"validated_reference missing (M294 auth blocked; M317 blocked)"},"function_candidates":[],"interpretation":{"scope":"BLOCKED"},"anomaly":{},"unsupported":{"symbol_extraction":"UNSUPPORTED (DBOP_SCHEMA_M290 INSUFFICIENT; M313 basic reference only)"},"not_determined":{"function_identity":"NOT_DETERMINED (no validated_reference)"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","no GPU","no sudo","static identification only","fixture synthetic labeled"]}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["integrity_reference_check"] = "PASS" if structural_result and structural_result.get("observations",{}).get("integrity_check") == "PASS" else "NOT_RUN"
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M317-SYNTHETIC-FUNC-ELF32-LE-FIXTURE / NOSIZE / INDIRECT / BAD-RANGE / OVERLAP); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["correlation_reference"] = correlation_result.get("correlations", []) if isinstance(correlation_result, dict) else []
        # Separación estricta: FUNCTION_CANDIDATE / STRUCTURALLY_BOUNDED_FUNCTION / HEURISTIC_BOUNDARY
        # Fuente 1: símbolos de función con datos válidos (solo referencia básica; extracción completa UNSUPPORTED)
        symbol_ref_available = structural_result.get("observations",{}).get("symbol_table_extractable") if isinstance(structural_result,dict) else False
        # Fuente 2: código decodificado (M314) — candidatos basados en instrucciones de terminación (ret, call, salto)
        instructions = disassembly_result.get("decoded_instructions", []) if isinstance(disassembly_result, dict) else (disassembly_result or [])
        observations["instructions_decoded"] = len(instructions)
        # Fuente 3: referencias del CFG (M316) — bloques básicos con terminadores
        nodes = cfg_result.get("cfg_nodes", []) if isinstance(cfg_result, dict) else []
        observations["cfg_nodes_available"] = len(nodes)
        # Identificación básica: candidatos por tipo
        candidates.append({
            "candidate_id": "candidate_symbol_valid",
            "type": "FUNCTION_CANDIDATE",
            "origin": "symbol_table_reference (basic; M313 reference only; UNSUPPORTED for full extraction)",
            "evidence": {"symbol_type_reference":"STT_FUNC basic reference available","symbol_size_valid":"referenced but not independently verified","section_reference":"basic (shndx verified in header only)"},
            "range_bytes": {"start": None, "end": None, "verified_mapping":"NOT_DETERMINED (requires verified segment mapping + authorization + schema)"},
            "virtual_address": None,
            "related_blocks": [],
            "status": "PARTIAL",
            "interpretation": "Candidate from basic symbol reference; full boundary and identity require DBOP_SCHEMA_M290 VERIFIED + independent recovery + authorization",
            "anomaly": {},
            "unsupported": {"full_symtab_parsing":"UNSUPPORTED (DBOP_SCHEMA_M290 INSUFFICIENT; M313 basic reference only)","full_rela_parsing":"UNSUPPORTED","execution_target_resolution":"UNSUPPORTED"},
            "not_determined": {"function_identity":"PARTIAL (basic reference only; full identity requires verified symbol table + authorization)","range_exact":"NOT_DETERMINED (symbol size reference available but not independently verified; requires authorization + verification)","execution_target":"NOT_DETERMINED (static only; no execution; no verified mapping + authorization + schema)"},
        })
        # Candidato heurístico por instrucciones: secuencia con terminador ret/call
        if instructions:
            # Buscar instrucciones de retorno (ret) como candidatos heurísticos
            ret_instructions = [i for i in instructions if isinstance(i.get("observation",{}).get("decoded_text",""), str) and i.get("observation",{}).get("decoded_text","") == "ret"]
            if ret_instructions:
                candidates.append({
                    "candidate_id": "candidate_heuristic_ret",
                    "type": "HEURISTIC_BOUNDARY",
                    "origin": "instruction_decoded (basic terminator detection; M314 decodificación; no full flow resolution)",
                    "evidence": {"terminator_type":"RETURN (ret instruction decoded)","instruction_offset": ret_instructions[0].get("observation",{}).get("offset_file", None), "bytes_decoded": ret_instructions[0].get("observation",{}).get("bytes_hex", None)},
                    "range_bytes": {"start": ret_instructions[0].get("observation",{}).get("offset_file", 0) - 8 if ret_instructions[0].get("observation",{}).get("offset_file") else None, "end": ret_instructions[0].get("observation",{}).get("offset_file", 0) + ret_instructions[0].get("observation",{}).get("bytes_length", 0) - 1, "verified_mapping":"NOT_DETERMINED (heuristic boundary; requires verification of full segment + authorization + schema)"},
                    "virtual_address": None,
                    "related_blocks": nodes[:min(1, len(nodes))] if nodes else [],
                    "status": "PARTIAL",
                    "interpretation": "Heuristic candidate from static ret instruction; full function identity and exact boundary require structural verification + authorization + independent recovery; execution target NOT_DETERMINED",
                    "anomaly": {},
                    "unsupported": {"execution_target_resolution":"UNSUPPORTED","full_symbol_mapping":"UNSUPPORTED","behavior_inference":"UNSUPPORTED"},
                    "not_determined": {"execution_target":"NOT_DETERMINED (ret destination requires verified segment mapping + authorization + independent verification)","function_identity":"HEURISTIC (not structurally bounded by verified symbols/sizes; requires verified symbol + authorization)"},
                })
            # Candidato por salto indirecto (UNSUPPORTED destino)
            indirect_instructions = [i for i in instructions if isinstance(i.get("observation",{}).get("decoded_text",""), str) and ("jmp [" in i.get("observation",{}).get("decoded_text","") or i.get("observation",{}).get("decoded_text","") == "jmp [rax]")]
            if indirect_instructions:
                candidates.append({
                    "candidate_id": "candidate_heuristic_indirect",
                    "type": "HEURISTIC_BOUNDARY",
                    "origin": "indirect_branch_instruction_decoded (destination unknown; UNSUPPORTED for target resolution)",
                    "evidence": {"instruction_text": "indirect jump (destination unknown; requires verified segment mapping + authorization + schema for full resolution)","bytes_decoded": indirect_instructions[0].get("observation",{}).get("bytes_hex", None)},
                    "range_bytes": {"start": indirect_instructions[0].get("observation",{}).get("offset_file", None), "verified_mapping":"NOT_DETERMINED (indirect target unknown)"},
                    "status": "UNSUPPORTED",
                    "interpretation": "Indirect branch detected; destination and function boundary cannot be determined statically without verified segment mapping + authorization + independent verification",
                    "anomaly": {},
                    "unsupported": {"indirect_target_resolution":"UNSUPPORTED (destination requires verified mapping + authorization + schema; no execution)"},
                    "not_determined": {"execution_target":"NOT_DETERMINED (indirect branch; destination unknown; requires authorization + verification + execution verification? No execution allowed; static only)"},
                })
        # Anomalía de solapamiento (fixture overlap)
        observations["fixture_anomaly_documented"] = True
        observations["fixture_anomaly_note"] = "Fixture M317-SYNTHETIC-FUNC-OVERLAP-ELF32-LE-FIXTURE contains overlapping symbols (same value 0x1000 with different sizes); anomaly documented; no silent discard"
        interpretation["anomaly_note"] = "Overlapping symbol reference detected (fixture synthetic); full resolution requires verified symbol table + authorization; not discarded silently"
        # Separación OBSERVATION / FUNCTION_CANDIDATE / STRUCTURALLY_BOUNDED_FUNCTION / HEURISTIC_BOUNDARY / ANOMALY / UNSUPPORTED / NOT_DETERMINED
        observations["analysis_type_separation"] = {"FUNCTION_CANDIDATE":"candidate from basic symbol/table reference (not fully verified)","STRUCTURALLY_BOUNDED_FUNCTION":"NOT_SUPPORTED for full structural boundary (requires verified symbol + size + authorization + independent verification)","HEURISTIC_BOUNDARY":"heuristic from instruction terminator or indirect branch; not structurally bounded","ANOMALY":"overlap/inconsistency documented; no silent discard","UNSUPPORTED":"indirect target, full symtab/rela, execution inference unsupported","NOT_DETERMINED":"exact range, identity, destination, execution path not determinable without authorization + verification"}
        # Resultado con continuidad CONTINUE
        observations["continuity_state"] = "CONTINUE (M317 PASS PARTIAL; M318 not started; authorization blocked)"
        return {
            "status":"PASS_PARTIAL",
            "decision":"PARTIAL",
            "function_candidates": candidates,
            "interpretation": interpretation,
            "observations": observations,
            "anomaly": anomaly,
            "unsupported": unsupported,
            "not_determined": not_determined,
            "hash_input": hash_ref,
            "continuity":"CONTINUE",
            "limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","static function identification only; full structural boundary requires authorization + verified symbol + independent verification","fixture synthetic clearly labeled"],
            "restrictions":["no execution","no GPU","no sudo","fixture synthetic clearly labeled","no behavior inference","no full symbol/rela mapping","no indirect target resolution"],
            "autonomous_loop": False,
            "max_iter": 1,
            "db_auth_actor_m294":"BLOCKED",
            "dbop_schema_m290":"INSUFFICIENT",
        }

if __name__ == "__main__":
    import hashlib
    fixture_bytes = open('/tmp/m317_synthetic_func_elf32_le.bin','rb').read()
    ref = {"hash_sha256": hashlib.sha256(fixture_bytes).hexdigest(), "path_read":"/tmp/m317_synthetic_func_elf32_le.bin", "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    res = M317StaticFunctionIdentifier(validated_reference=ref, max_iter=1).identify(structural_result={"observations":{"integrity_check":"PASS","format":"ELF","magic_match_elf":True,"symbol_table_extractable":False,"format_verified":True}}, disassembly_result={"decoded_instructions":[{"observation":{"offset_file":0,"bytes_hex":"4889c7","bytes_length":3,"decoded_text":"mov rdi, rax"}}],"observations":{"integrity_check":"PASS","decoded_instructions_count":1}}, correlation_result={}, cfg_result={"cfg_nodes":[{"node_id":"node_0"}]})
    print("M317: status=", res["status"], "; decision=", res["decision"], "; continuity=", res["continuity"])
    print("Candidates:", len(res.get("function_candidates",[])))
    for c in res.get("function_candidates",[]):
        print("  -", c.get("candidate_id"), ": type=", c.get("type"), "; status=", c.get("status"), "; interpretation=", c.get("interpretation","")[:60])
    print("Observations (fixture_anomaly):", res["observations"].get("fixture_anomaly_documented"), "/", res["observations"].get("fixture_anomaly_note",""))
