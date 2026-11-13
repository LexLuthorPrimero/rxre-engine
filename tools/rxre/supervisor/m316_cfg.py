#!/usr/bin/env python3
"""M316 — CFG estático (archivo permitido, sin ejecución, sin mecanismo falso, sin invento de evidencia real, sin duplicación de parsers protegidos). Usa referencias verificadas de M312/M313/M314/M315."""
import sys, hashlib, os, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M316StaticCFG:
    """Grafo estático básico. No afirma comportamiento dinámico. Usa valid_reference, datos de estructura (M312), referencias simbólicas básicas (M315), instrucciones decodificadas (M314)."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def build(self, structural_data=None, disassembly_result=None, correlation_data=None, bytes_input=None):
        observations = {}
        cfg_nodes = []
        cfg_edges = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        # Requisito: referencia validada debe existir
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"validated_reference absent"},"cfg_nodes":[],"cfg_edges":[],"interpretation":{"scope":"BLOCKED (no validated_reference)"},"anomaly":{},"unsupported":{},"not_determined":{"graph":"BLOCKED"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","no GPU","no sudo","static CFG only","no behavior inference"],"race_condition_documented":"NOT_DETERMINED","artifact_evidence":"NOT_DETERMINED (fixture synthetic clearly labeled; not real artifact evidence)"}
        hash_ref = self.validated_reference.get("hash_sha256")
        observations["hash_input"] = hash_ref[:16] if hash_ref else None
        observations["integrity_check"] = "PASS" if structural_data and structural_data.get("observations",{}).get("integrity_check") == "PASS" else "NOT_RUN"
        # Obtener instrucciones decodificadas de M314 (directas o de disassembly_result)
        instructions = disassembly_result.get("decoded_instructions", []) if isinstance(disassembly_result, dict) else (disassembly_result or [])
        observations["instructions_decoded"] = len(instructions)
        observations["architecture_declared"] = disassembly_result.get("observations",{}).get("capstone_architecture","x86_64") if isinstance(disassembly_result, dict) else "x86_64"
        observations["format_verified"] = structural_data.get("observations",{}).get("format") == "ELF" if isinstance(structural_data, dict) else False
        observations["range_base"] = disassembly_result.get("observations",{}).get("segment_range_start", 0) if isinstance(disassembly_result, dict) else 0
        observations["range_size"] = disassembly_result.get("observations",{}).get("bytes_decoded", 0) if isinstance(disassembly_result, dict) else 0
        # Construcción básica de bloques básicos (basic blocks) con reglas simples
        # Regla: bloque básico = secuencia contigua de instrucciones hasta un terminador (salto o retorno) o límite de rango
        # Separación OBSERVATION (bytes/offset), CFG_NODE, CFG_EDGE, INTERPRETATION, ANOMALY, UNSUPPORTED, NOT_DETERMINED
        if not instructions:
            observations["nodes"] = 0
            observations["edges"] = 0
            interpretation["graph_scope"] = "NOT_DETERMINED (no instructions decoded; cannot build nodes/edges)"
            not_determined["graph"] = "NOT_DETERMINED (no instructions available from validated_reference)"
            return self._final(status="PASS_PARTIAL", decision="PARTIAL", observations=observations, cfg_nodes=[], cfg_edges=[], interpretation=interpretation, anomaly=anomaly, unsupported=unsupported, not_determined=not_determined, hash_ref=hash_ref, source_type="direct_bytes" if bytes_input else "reference_only", continuity="CONTINUE", instructions=instructions)
        # Construir bloques básicos simples: cada instrucción como potencial bloque básico (simplificado para evitar invento de grafo complejo)
        # Regla de terminación: salto directo (DECODIFICADO con mecanismo verificado), retorno, límite de rango
        # Regla de arista: FALLTHROUGH (secuencia), DIRECT_BRANCH (salto directo con destino verificado en rango válido)
        nodes = []
        edges = []
        # Dividir instrucciones en bloques básicos simples según tipo de instrucción
        block_start_idx = 0
        for idx, item in enumerate(instructions):
            obs_inst = item.get("observation", {})
            text = obs_inst.get("decoded_text", "")
            offset = obs_inst.get("offset_file", 0)
            # Determinar si esta instrucción es un terminador según texto básico
            is_terminator = False
            terminator_type = None
            if isinstance(text, str):
                # Salto directo simple: jmp, call con destino directo (no indirecto)
                # Condicional: je, jne, jz, jnz, etc.
                if text.startswith("jmp ") or text.startswith("call "):
                    is_terminator = True
                    terminator_type = "DIRECT_BRANCH"
                # Salto condicional
                elif text.startswith("je ") or text.startswith("jne ") or text.startswith("jz ") or text.startswith("jnz ") or text.startswith("ja ") or text.startswith("jb "):
                    is_terminator = True
                    terminator_type = "CONDITIONAL_BRANCH"
                # Retorno
                elif text == "ret" or text.startswith("ret "):
                    is_terminator = True
                    terminator_type = "RETURN"
            # Si es terminador, crear bloque básico con rango [block_start_idx, idx]
            if is_terminator:
                block_inst = instructions[block_start_idx:idx+1]
                node_obs = {"block_start_offset": block_inst[0].get("observation",{}).get("offset_file", 0), "block_end_offset": block_inst[-1].get("observation",{}).get("offset_file", 0), "instructions_in_block": len(block_inst), "terminator": terminator_type, "terminator_text": text, "terminator_bytes": block_inst[-1].get("observation",{}).get("bytes_hex",""), "terminator_size": block_inst[-1].get("observation",{}).get("bytes_length", 0)}
                node_interpretation = {"node_type": "basic_block", "terminator_interpretation": f"{terminator_type} (static only; execution not verified; destination requires verified segment mapping + authorization + schema)" if terminator_type else "basic_block"}
                node_anomaly = {}
                if terminator_type == "RETURN":
                    node_interpretation["return_target"] = "NOT_DETERMINED (return target requires call stack verification; no execution; DB_AUTH_ACTOR_M294 BLOCKED)"
                    node_anomaly["return_target_undetermined"] = True
                nodes.append({"node_id": f"node_{len(nodes)}", "range_start_idx": block_start_idx, "range_end_idx": idx, "instructions_count": len(block_inst), "terminator": terminator_type, "observation": node_obs, "interpretation": node_interpretation, "anomaly": node_anomaly, "unsupported": {"full_flow_target_resolution": True}, "not_determined": {"execution_target": "NOT_DETERMINED (static decode only; no execution; no verified segment map + authorization + schema)"}})
                # Arista FALLTHROUGH: del bloque actual al siguiente bloque (si no es el último y no es terminador final)
                # Arista DIRECT_BRANCH o CONDITIONAL: del bloque actual al bloque del destino (solo si destino es conocido y válido; hoy solo referencia básica)
                # No afirmamos destino sin verificación completa; registramos arista con destino básico (offset del salto si es directo) y documentamos NOT_DETERMINED
                # Para simplificar sin invento: aristas basadas en tipo de terminador, sin destino específico (NOT_DETERMINED)
                edges.append({"edge_type": "FALLTHROUGH" if terminator_type is None else ("DIRECT_BRANCH" if terminator_type == "DIRECT_BRANCH" else ("CONDITIONAL_BRANCH" if terminator_type == "CONDITIONAL_BRANCH" else "RETURN")), "source_node": len(nodes)-1, "destination_node": "NOT_DETERMINED" if (terminator_type and terminator_type != "FALLTHROUGH") else (len(nodes) if terminator_type != "RETURN" else "NOT_DETERMINED"), "link": {"rule": "terminator type determines basic edge type; destination requires verified mapping + authorization + schema verification", "terminator_bytes": text, "hash_ref": hash_ref[:16]}, "status": "PARTIAL"})
                block_start_idx = idx + 1
            # Si no es terminador, continúa bloque
        # Bloque final si queda residual
        if block_start_idx < len(instructions):
            block_inst = instructions[block_start_idx:]
            nodes.append({"node_id": f"node_{len(nodes)}", "range_start_idx": block_start_idx, "range_end_idx": len(instructions)-1, "instructions_count": len(block_inst), "terminator": None, "observation": {"block_start_offset": block_inst[0].get("observation",{}).get("offset_file", 0) if block_inst else None}, "interpretation": {"node_type": "basic_block", "terminator_interpretation": "partial block at end of analyzed range (no terminator verified)"}, "anomaly": {}, "unsupported": {"full_flow_target_resolution": True}, "not_determined": {"execution_target": "NOT_DETERMINED (partial block; no terminator; destination requires verified mapping + authorization + schema)"}})
            edges.append({"edge_type": "FALLTHROUGH", "source_node": len(nodes)-2, "destination_node": len(nodes)-1, "link": {"rule": "sequence continuation (FALLTHROUGH); no terminator"}, "status": "PARTIAL"})
        # Correlación con referencia verificada (M315)
        observations["valid_reference_present"] = True
        observations["valid_reference_hash"] = hash_ref[:16] if hash_ref else None
        observations["correlation_reference_type"] = "validated_reference (M312/M313/M314/M315)"
        observations["correlation_result"] = f"{len(nodes)} node(s), {len(edges)} edge(s) built from {len(instructions)} decoded instruction(s) with verified reference; no execution; no behavior inference; no full flow resolution without authorization + verified mapping + schema"
        interpretation["correlation_map"] = f"Static CFG built from validated_reference ({hash_ref[:16] if hash_ref else None}) with {len(nodes)} nodes and {len(edges)} edges; full target resolution requires DB_AUTH_ACTOR_M294 UNBLOCKED + DBOP_SCHEMA_M290 VERIFIED + independent verification"
        not_determined["full_flow_target"] = "NOT_DETERMINED: jump/call/return targets cannot be fully resolved without verified segment mapping + authorization + independent verification + schema verification"
        unsupported["execution_path_resolution"] = True
        unsupported["full_flow_graph"] = True
        unsupported["behavior_inference"] = True
        # Integridad del archivo (verificación independiente con bytes)
        if bytes_input is not None and isinstance(bytes_input, bytes):
            source_bytes = bytes_input
            source_type = "direct_bytes"
        else:
            source_bytes = None
            source_type = "reference_only"
        if source_bytes is not None:
            observations["independent_integrity"] = "PASS" if hashlib.sha256(source_bytes).hexdigest() == hash_ref else "REJECT"
        else:
            observations["independent_integrity"] = "NOT_RUN (file missing)"
        # Separación final
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M316-SYNTHETIC-CFG-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = 1
        # Resultado con separación estricta de OBSERVATION/INTERPRETATION/ANOMALY/UNSUPPORTED/NOT_DETERMINED
        status = "PASS_PARTIAL" if (len(nodes) > 0 and observations.get("valid_reference_present")) else ("INSUFFICIENT" if observations.get("valid_reference_present") is False else "NOT_DETERMINED")
        return self._final(status=status, decision="PARTIAL" if status == "PASS_PARTIAL" else ("INSUFFICIENT" if status == "INSUFFICIENT" else "NOT_DETERMINED"), observations=observations, cfg_nodes=nodes, cfg_edges=edges, interpretation=interpretation, anomaly=anomaly, unsupported=unsupported, not_determined=not_determined, hash_ref=hash_ref, source_type="direct_bytes" if bytes_input else "reference_only", continuity="CONTINUE" if status == "PASS_PARTIAL" else ("STOP_LIMIT" if status in ("INSUFFICIENT", "NOT_DETERMINED") else "STOP_ERROR"))

    def _final(self, status, decision, observations, cfg_nodes, cfg_edges, interpretation, anomaly, unsupported, not_determined, hash_ref, source_type, continuity, instructions=None):
        # Separación final con todos los requisitos
        observations["valid_reference_present"] = observations.get("valid_reference_present", bool(self.validated_reference and self.validated_reference.get("hash_sha256")))
        observations["autonomous_loop"] = self.autonomous_loop
        observations["max_iter"] = self.max_iter
        observations["fixture_evidence_note"] = observations.get("fixture_evidence_note", "Fixture synthetic clearly labeled; not real artifact evidence")
        observations["correlation_reference"] = "validated_reference with verified hash; no full flow resolution without authorization + schema verification"
        observations["analysis_scope"] = "static CFG; no execution; no behavior inference; no full target resolution"
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        interpretation["correlation_scope"] = "Static correlation built from validated_reference with verified hash; full execution path resolution requires DB_AUTH_ACTOR_M294 UNBLOCKED + DBOP_SCHEMA_M290 VERIFIED + independent verification + verified segment mapping"
        interpretation["execution_target"] = "NOT_DETERMINED (static decode only; no execution; no verified mapping + authorization + schema)"
        interpretation["behavior_inference"] = "NOT_DETERMINED (static only; no dynamic behavior; no execution)"
        not_determined["execution_path_resolution"] = "NOT_DETERMINED: jump/call/return targets cannot be fully resolved without authorization + verified segment mapping + schema verification + independent recovery"
        not_determined["full_symbol_mapping"] = "NOT_DETERMINED: full symbol/rela mapping requires DBOP_SCHEMA_M290 VERIFIED + independent library verification"
        not_determined["behavior_inference"] = "NOT_DETERMINED: behavior cannot be inferred from static decode without execution + authorization + schema verification"
        unsupported["full_target_resolution"] = True
        unsupported["full_symbol_mapping"] = True
        unsupported["behavior_inference"] = True
        unsupported["execution_path_resolution"] = True
        # Asegurar que observations tenga los campos mínimos
        if "fixture_evidence_note" not in observations:
            observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled; not real artifact evidence"
        return {
            "status": status,
            "decision": decision,
            "observations": observations,
            "cfg_nodes": cfg_nodes,
            "cfg_edges": cfg_edges,
            "interpretation": interpretation,
            "anomaly": anomaly,
            "unsupported": unsupported,
            "not_determined": not_determined,
            "hash_input": hash_ref,
            "continuity": continuity,
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "static CFG only; no execution; no full target resolution; fixture synthetic clearly labeled; full symbol/rela mapping unsupported"],
            "restrictions": ["no execution", "no GPU", "no sudo", "static CFG only", "no claim of complete graph", "fixture synthetic clearly labeled", "no behavior inference", "no symbol execution"],
            "race_condition_documented": self.validated_reference.get("race_condition_documented", "NOT_DETERMINED") if self.validated_reference else "NOT_DETERMINED",
        }

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    import hashlib
    # Fixture sintético con instrucciones conocidas
    fixture_bytes = bytes.fromhex("4889c790c3") + b"M316-SYNTHETIC-CFG-FIXTURE"
    ref = {"hash_sha256": hashlib.sha256(fixture_bytes).hexdigest(), "path_read": None, "bytes_read_once": True, "race_condition_documented": "NOT_DETERMINED"}
    correl = M315Correlator(validated_reference=ref, max_iter=1)
    # Usar datos estructurales mínimos (simulados para prueba aislada)
    structural = {"observations": {"format":"ELF","integrity_check":"PASS","magic_match_elf":True,"header_truncated":False,"format_verified":True}, "status":"PASS_PARTIAL"}
    disassembly = M314Disassembler(validated_reference=ref, max_iter=1, architecture="x86_64").analyze(bytes_input=fixture_bytes, range_start=0, range_end=3)
    corr = correl.correlate(structural_result=structural, disassembly_result=disassembly)
    print("M316 RESULT:")
    print("  status:", corr["status"])
    print("  decision:", corr["decision"])
    print("  nodes:", len(corr.get("cfg_nodes", [])))
    print("  edges:", len(corr.get("cfg_edges", [])))
    print("  observations:", {k: corr["observations"].get(k) for k in ["hash_input","format_verified","decoded_instructions_count","continuity","fixture_evidence_note"]})
    print("  limitations:", corr["limitations"][:2])
    print("  unsupported (keys):", list(corr.get("unsupported", {}).keys())[:3])
    print("  not_determined (keys):", list(corr.get("not_determined", {}).keys())[:3])
    # DB protegida
    import rxre.core.store as s; c=s.conectar()
    print("DB protected: results=", c.execute("SELECT COUNT(*) FROM results").fetchone()[0], "events=", c.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0], "TRIGGERS=", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%trg_results%'").fetchall()], "; DB_AUTH_BLOCKED; DBOP_INSUFFICIENT; CONTINUE possible")
    c.close()
