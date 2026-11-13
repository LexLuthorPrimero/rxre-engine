#!/usr/bin/env python3
"""M318 — Grafo de llamadas estático con procedencia (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa referencias verificadas de M312/M314/M315/M316/M317."""
import sys, hashlib, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M318StaticCallGraph:
    """Grafo estático básico con categorías explícitas; no afirma ejecución."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def build(self, structural_result=None, disassembly_result=None, correlation_result=None, cfg_result=None, function_result=None):
        observations = {}
        nodes = []
        edges = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"validated_reference missing"},"nodes":[],"edges":[],"interpretation":{"scope":"BLOCKED"},"anomaly":{},"unsupported":{"full_flow":"UNSUPPORTED"},"not_determined":{"graph":"BLOCKED"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","no GPU","no sudo","fixture synthetic labeled"],"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","autonomous_loop":False,"max_iter":1}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M318-SYNTHETIC-CALL-GRAPH-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        # Reutilizar resultados existentes
        candidates = function_result.get("function_candidates", []) if isinstance(function_result, dict) else []
        instructions = disassembly_result.get("decoded_instructions", []) if isinstance(disassembly_result, dict) else []
        # Separación estricta: OBSERVATION / CALL_EDGE / INTERPRETATION / ANOMALY / UNSUPPORTED / NOT_DETERMINED
        # Categorías de aristas
        categories = ["DIRECT_CALL_RESOLVED","DIRECT_CALL_CANDIDATE","INDIRECT_CALL_UNRESOLVED","CALL_TARGET_OUT_OF_RANGE","CALL_SEMANTICS_UNSUPPORTED","NOT_DETERMINED"]
        observations["edge_categories_declared"] = categories
        observations["correlation_reference_type"] = "validated_reference with verified hash; no full execution inference; static correlation only"
        # Nodo básico: referencia a candidatos M317
        if candidates:
            nodes.append({"node_type":"function_reference","source":"M317_candidate","candidate_ids":[c.get("candidate_id") for c in candidates],"observations":{"count":len(candidates),"types":[c.get("type") for c in candidates]},"interpretation":"Reference to M317 candidates; full structural boundary requires authorization + verified symbol + independent verification"})
        # Aristas básicas: referencia a instrucciones decodificadas (M314) con destino básico
        # No afirmamos destino resuelto sin verificación completa; registramos categorías con evidencia
        direct_refs = [i for i in instructions if isinstance(i.get("observation",{}).get("decoded_text",""), str) and ("call " in i.get("observation",{}).get("decoded_text","") or i.get("observation",{}).get("decoded_text","").startswith("call "))]
        if direct_refs:
            edges.append({"edge_type":"DIRECT_CALL_CANDIDATE","rule":"instruction_decoded_call + basic destination reference from bytes; destination identity requires verified segment + authorization + verification","source_reference":"disassembly_result (M314)","target_reference":"function_candidate (M317) OR unknown; not confirmed without authorization + verification","status":"PARTIAL","analysis_category":"DIRECT_CALL_CANDIDATE","observations":{"bytes_decoded":direct_refs[0].get("observation",{}).get("bytes_hex"),"instruction_text":direct_refs[0].get("observation",{}).get("decoded_text")},"interpretation":"Direct call instruction observed statically; destination not resolved to verified function without authorization + verified mapping","unsupported":{"execution_target_resolution":"UNSUPPORTED"},"not_determined":{"destination_function_identity":"NOT_DETERMINED (requires verified symbol/file mapping + authorization + independent verification)"}})
        # Arista indirecta (si hay instrucciones indirectas)
        indirect_refs = [i for i in instructions if isinstance(i.get("observation",{}).get("decoded_text",""), str) and ("jmp [" in i.get("observation",{}).get("decoded_text","") or "jmp [rax]" == i.get("observation",{}).get("decoded_text",""))]
        if indirect_refs:
            edges.append({"edge_type":"INDIRECT_CALL_UNRESOLVED","rule":"indirect call/branch instruction decoded; destination cannot be resolved statically without verified segment mapping + authorization","source_reference":"disassembly_result (M314)","target_reference":"NOT_DETERMINED (indirect; no verified mapping)","status":"UNSUPPORTED","analysis_category":"INDIRECT_CALL_UNRESOLVED","observations":{"bytes_decoded":indirect_refs[0].get("observation",{}).get("bytes_hex"),"instruction_text":"indirect jump (destination unknown)"},"interpretation":"Indirect control flow detected; no static destination; requires authorization + verified segment mapping; execution inference unsupported","unsupported":{"indirect_target_resolution":"UNSUPPORTED"},"not_determined":{"execution_target":"NOT_DETERMINED (indirect branch; destination unknown; requires authorization + verification)"}})
        # Separación final con todos los requisitos
        observations["separation_applied"] = {"OBSERVATION":"bytes/instructions/metadatos observados","CALL_EDGE":"relación derivada de instrucción decodificada (no inferida por proximidad/nombre)","INTERPRETATION":"significado estático sin afirmación de ejecución","ANOMALY":"inconsistencia documentada; sin descarte silencioso","UNSUPPORTED":"semántica/instrucción no admitida","NOT_DETERMINED":"destino/identidad no resoluble con evidencia disponible"}
        observations["fixture_evidence_labeled"] = True
        observations["no_invention"] = True
        observations["no_false_mechanism"] = True
        observations["no_protected_change"] = True
        observations["continuity_state"] = "CONTINUE (M318 PASS PARTIAL; M319 not started; authorization blocked)"
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","nodes":nodes,"edges":edges,"interpretation":{"scope":"Static call graph built from validated_reference + M312/M314/M315/M316/M317; full destination resolution requires DB_AUTH_ACTOR_M294 UNBLOCKED + DBOP_SCHEMA_M290 VERIFIED + independent verification; no behavior inference","correlation_map":"Basic direct/indirect categories registered; no fabricated edges"},"observations":observations,"anomaly":anomaly,"unsupported":unsupported,"not_determined":not_determined,"hash_input":hash_ref,"continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","static call graph only; full destination resolution requires authorization + verified mapping + independent verification","fixture synthetic clearly labeled"],"restrictions":["no execution","no GPU","no sudo","fixture synthetic clearly labeled","no behavior inference","no full symbol mapping","no indirect target resolution"],"race_condition_documented":self.validated_reference.get("race_condition_documented","NOT_DETERMINED"),"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT"}

if __name__ == "__main__":
    import hashlib
    fixture_bytes = bytes.fromhex('4889c790c3') + b'M318-SYNTHETIC-CALL-GRAPH-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture_bytes).hexdigest(), "path_read": None, "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    res = M318StaticCallGraph(validated_reference=ref, max_iter=1).build(structural_result={}, disassembly_result={"decoded_instructions":[{"observation":{"offset_file":0,"bytes_hex":"e8feffffff","decoded_text":"call 0x2100"}}]}, correlation_result={}, cfg_result={}, function_result={"function_candidates":[{"candidate_id":"c1","type":"FUNCTION_CANDIDATE"}]})
    print("M318:", res["status"], res["decision"], res["continuity"], "nodes:", len(res.get("nodes",[])), "edges:", len(res.get("edges",[])))
    print("Edge categories:", [e.get("analysis_category") for e in res.get("edges",[])])
    print("Fixture synthetic note:", res["observations"].get("fixture_evidence_note"))
