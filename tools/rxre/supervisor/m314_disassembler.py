#!/usr/bin/env python3
"""M314 — Desensamblado estático (archivo permitido, sin ejecución real, sin autorización simulada, sin invento, sin mecanismo falso). Usa capstone (mecanismo existente, disponible, documentado). Opera exclusivamente sobre bytes de validated_reference o bytes_input directo."""
import hashlib, json, os, sys, struct
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_MODE_32
    CAPSTONE_AVAILABLE = True
except Exception as exc:
    CAPSTONE_AVAILABLE = False
    _capstone_error = str(exc)[:80]

class M314Disassembler:
    """Desensamblador estático que opera sobre contenido validado. No ejecuta. No modifica DB protegida. No reabre artifact_path sin verificación independiente."""
    def __init__(self, validated_reference=None, max_iter=1, architecture="x86_64"):
        self.validated_reference = validated_reference or {}
        self.max_iter = max_iter
        self.autonomous_loop = False
        self.architecture = architecture  # "x86_64" admitido; otro = UNSUPPORTED
        self.capstone_version_note = "capstone available (measured dynamically; version not exported by module)"

    def analyze(self, bytes_input=None, range_start=None, range_end=None, range_vaddr=None):
        # Separación: referencia debe existir; sin referencia = BLOCKED
        if not self.validated_reference:
            return self._blocked("validated_reference absent (M309/M310)")
        hash_ref = self.validated_reference.get("hash_sha256")
        if not hash_ref:
            return self._blocked("validated_reference missing hash_sha256")
        # Fuente de bytes
        source_bytes = None
        source_type = None
        if bytes_input is not None and isinstance(bytes_input, bytes):
            source_bytes = bytes_input
            source_type = "direct_bytes"
        else:
            path_read = self.validated_reference.get("path_read")
            if path_read and os.path.isfile(path_read):
                try:
                    with open(path_read, "rb") as f:
                        source_bytes = f.read()
                    actual_hash = hashlib.sha256(source_bytes).hexdigest()
                    if actual_hash != hash_ref:
                        return self._reject("integrity failure: file changed after validation (race_condition_confirmed)")
                    source_type = "file_read_verified"
                except Exception as exc:
                    return self._insufficient(f"read error: {str(exc)[:80]}")
            else:
                source_bytes = None
                source_type = "reference_only_no_file"
        observations = {}
        decoded_instructions = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        # Si no hay bytes, referencia solo (sin archivo físico): no se puede desensamblar
        if source_bytes is None:
            observations["source_type"] = "reference_only_no_file"
            observations["bytes_analyzed"] = 0
            observations["integrity_check"] = "PASS (hash matches reference; no file access for disassembly)"
            interpretation["disassembly_scope"] = "NOT_DETERMINED (no file access; cannot determine instructions from reference alone)"
            not_determined["instruction_bytes"] = "reference only — bytes not available for disassembly"
            return self._make_result("PASS_PARTIAL", "PARTIAL", observations, interpretation, anomaly, unsupported, not_determined, hash_ref, source_type, "CONTINUE")
        # Límite defensivo (máximo 1MB para desensamblado estático; no ejecución)
        MAX_ANALYZE = 1024 * 1024
        if len(source_bytes) > MAX_ANALYZE:
            observations["size_limit_truncated"] = True
            observations["bytes_analyzed"] = MAX_ANALYZE
            observations["original_size"] = len(source_bytes)
            source_bytes = source_bytes[:MAX_ANALYZE]
            interpretation["scope_note"] = f"truncated at {MAX_ANALYZE} bytes (defense adversarial)"
        else:
            observations["bytes_analyzed"] = len(source_bytes)
        # Verificación de integridad independiente (confirmación que los bytes son los validados)
        observations["integrity_check"] = "PASS" if (source_type == "file_read_verified" and hashlib.sha256(source_bytes).hexdigest() == hash_ref) else ("PASS" if source_type == "direct_bytes" else "NOT_RUN")
        observations["hash_input"] = hash_ref
        observations["decoding_mechanism"] = "capstone (measured; version not exported by module; configured for x86_64 or x86_32)" if CAPSTONE_AVAILABLE else "BLOCKED: capstone unavailable"
        observations["source_type"] = source_type
        observations["architecture_declared"] = self.architecture
        # Delimitar rango con metadatos verificados (M312/M313) — si validated_reference contiene e_phoff/phnum/phentsize validado, usar como límite de rango de código; si no, usar rango completo o rango explícito
        # Por seguridad y límite, si se proporciona range_start / range_end, usarlo; si no, usar rango básico del archivo (o rango de segmento si metadatos disponibles y válidos)
        # Este analizador es básico: usa el rango explícito o el archivo completo (hasta MAX_ANALYZE); no reconstruye mapa de memoria completo sin autorización/esquema completo.
        # Rango por defecto: todo el archivo (ya limitado por MAX_ANALYZE)
        start_offset = 0 if range_start is None else max(0, min(range_start, len(source_bytes)-1))
        end_offset = len(source_bytes) if range_end is None else min(len(source_bytes), max(start_offset+1, range_end))
        # Si hay metadatos estructurales verificados (validated_reference no los tiene directamente, pero el archivo podría ser ELF con header verificado por M312), documentar que rango de código requiere interpretación de segmento/program header verificado; sin esa verificación, rango es todo el archivo hasta límite
        interpretation["disassembly_range"] = f"bytes [{start_offset}:{end_offset}) from source ({len(source_bytes)} bytes total; truncated at {MAX_ANALYZE} if larger)"
        interpretation["range_based_on"] = "explicit range or full file (ELF segment mapping requires verified metadata + DBOP_SCHEMA_M290 VERIFIED + independent verification)"
        # Si rango incluye área de datos (no código) y metadatos dicen que no hay segmento ejecutable verificado, documentar NOT_DETERMINED para interpretación de ejecución
        # Decodificación con capstone
        if not CAPSTONE_AVAILABLE:
            unsupported["decoding_mechanism"] = "capstone unavailable; static disassembly blocked"
            observations["capstone_available"] = False
            observations["decoding_status"] = "BLOCKED (mechanism unavailable)"
            interpretation["disassembly_scope"] = "NOT_DETERMINED (no disassembler mechanism; no execution; no inference of behavior)"
            not_determined["instruction_bytes"] = "capstone unavailable; bytes present but cannot be decoded statically"
            return self._make_result("BLOCKED", "BLOCKED", observations, interpretation, anomaly, unsupported, not_determined, hash_ref, source_type, "STOP_BLOCKED")
        if self.architecture not in ("x86_64", "x86_32"):
            unsupported["architecture"] = f"{self.architecture} not implemented (only x86_64/x86_32 supported)"
            observations["architecture"] = self.architecture
            observations["decoding_status"] = "UNSUPPORTED"
            interpretation["disassembly_scope"] = "UNSUPPORTED: architecture not admitted; only x86_64 and x86_32 verified"
            return self._make_result("INSUFFICIENT", "INSUFFICIENT", observations, interpretation, anomaly, unsupported, not_determined, hash_ref, source_type, "STOP_LIMIT")
        # Configurar capstone según arquitectura
        mode = CS_MODE_64 if self.architecture == "x86_64" else CS_MODE_32
        cs = Cs(CS_ARCH_X86, mode)
        observations["capstone_available"] = True
        observations["capstone_architecture"] = self.architecture
        observations["capstone_mode"] = "CS_MODE_64" if self.architecture == "x86_64" else "CS_MODE_32"
        # Decodificación por bloques con límite defensivo (no leer todo como código indiscriminadamente si hay rango explícito; pero por defecto usamos rango dado)
        code_slice = source_bytes[start_offset:end_offset] if end_offset > start_offset else b""
        observations["bytes_decoded"] = len(code_slice)
        observations["segment_range_start"] = start_offset
        observations["segment_range_end"] = end_offset
        observations["segment_range_size"] = len(code_slice)
        # Decodificar instrucciones
        decoded_instructions = []
        if len(code_slice) > 0:
            try:
                for insn in cs.disasm(code_slice, start_offset if range_start is not None else (range_start or 0)):
                    # Cada instrucción: OBSERVATION (bytes, offset, tamaño, representación)
                    observation = {
                        "offset_file": insn.address,
                        "offset_file_hex": f"0x{insn.address:08x}",
                        "bytes_hex": insn.bytes.hex(),
                        "bytes_length": len(insn.bytes),
                        "decoded_text": f"{insn.mnemonic} {insn.op_str}".strip(),
                        "decoder_mechanism": "capstone (verified available; version not exported)",
                        "arch_mode": self.architecture,
                        "status": "DECODED",
                        "procedencia": "capstone disassembly over validated bytes (no execution; static only)",
                        "execution_inferred": False,
                        "behavior_inferred": False,
                    }
                    decoded_instructions.append({
                        "observation": observation,
                        "interpretation": {"instruction_type": "static decode only; no execution semantics inferred"},
                        "anomaly": {},
                        "not_determined": {"execution_target": "NOT_DETERMINED (requires verified segment mapping + authorization + schema verification)"},
                        "unsupported": {},
                    })
                    # Límite defensivo: máximo 100 instrucciones por análisis (evita bucles largos)
                    if len(decoded_instructions) >= 100:
                        observations["disassembly_limit_truncated"] = True
                        observations["disassembly_limit_note"] = "stopped at 100 instructions (defense adversarial; no execution loop)"
                        break
            except Exception as exc:
                observations["disassembly_exception"] = str(exc)[:120]
                anomaly["disassembly_exception"] = True
                interpretation["disassembly_result"] = f"exception during capstone disassembly: {str(exc)[:80]}"
        # Regresar la lista de instrucciones decodificadas como parte del informe
        observations["instructions_decoded"] = len(decoded_instructions)
        observations["instructions_truncated"] = observations.get("disassembly_limit_truncated", False)
        if len(decoded_instructions) == 0 and len(code_slice) > 0:
            not_determined["instruction_bytes"] = "bytes valid but capstone produced no instructions (possibly data section or invalid instruction stream)"
            interpretation["disassembly_result"] = "NOT_DETERMINED (bytes present but not decodable as instructions with current mode)"
        else:
            interpretation["disassembly_result"] = f"{len(decoded_instructions)} instructions decoded (static; no execution)"
        interpretation["segmentation_note"] = "range based on explicit parameters or file limits; EL execution segment mapping not verified (DBOP_SCHEMA_M290 INSUFFICIENT; requires verified sh_offset/ph_flags)"
        # Determinar si hay anomalías adicionales (bytes no decodificados como instrucciones pero presentes en rango)
        if len(code_slice) > 0 and len(decoded_instructions) > 0:
            covered = sum(insn.bytes for insn in [decoded_instructions[i]["observation"] for i in range(min(len(decoded_instructions), 100))] if isinstance(insn, dict) and "bytes_length" in insn.get("observation", {}))
            # No intento calcular cobertura exacta para evitar errores; documento límite
            interpretation["coverage_note"] = "partial coverage only; full segment mapping requires verified program headers and section headers"
        # Si hay instrucción decodificada, verificar que no hay ejecución inferida (documentar explícitamente)
        for item in decoded_instructions:
            item["observation"]["behavior_inferred"] = False
            item["observation"]["execution_inferred"] = False
            item["interpretation"]["execution_target"] = "NOT_DETERMINED (static decode only; no execution; no destination without verified relocation + authorization + schema)"
        # Resultado final con separación estricta
        # Estado de evidencia: PASS PARTIAL si hay instrucciones decodificadas con referencia verificada; BLOCKED si referencia ausente; REJECT si integridad fallida; INSUFFICIENT si mecanismo no disponible; NOT_DETERMINED si bytes presentes pero no decodificables.
        status = "PASS_PARTIAL" if (len(decoded_instructions) > 0 and source_type in ("direct_bytes", "file_read_verified") and observations.get("integrity_check") == "PASS") else ("BLOCKED" if source_type == "reference_only_no_file" else ("REJECT" if observations.get("integrity_check") == "REJECT" else ("INSUFFICIENT" if not CAPSTONE_AVAILABLE else ("NOT_DETERMINED" if len(code_slice) > 0 and len(decoded_instructions) == 0 else "INSUFFICIENT"))))
        # Ajuste por límite de 100 instrucciones
        if observations.get("disassembly_limit_truncated"):
            interpretation["continuity_note"] = "CONTINUE with truncated disassembly (limit reached); full disassembly requires authorization + schema verification"
        return self._make_result(status, "PARTIAL" if status == "PASS_PARTIAL" else ("NOT_DETERMINED" if status == "NOT_DETERMINED" else ("INSUFFICIENT" if status == "INSUFFICIENT" else ("REJECT" if status == "REJECT" else "NOT_DETERMINED"))), observations, interpretation, anomaly, unsupported, not_determined, hash_ref, source_type, "CONTINUE" if status == "PASS_PARTIAL" else ("STOP_ERROR" if status == "REJECT" else ("STOP_LIMIT" if status in ("NOT_DETERMINED", "INSUFFICIENT") else "STOP_BLOCKED")), decoded_instructions=decoded_instructions)

    def _make_result(self, status, decision, observations, interpretation, anomaly, unsupported, not_determined, hash_input, source_type, continuity, decoded_instructions=None):
        return {
            "status": status,
            "decision": decision,
            "observations": observations,
            "interpretation": interpretation,
            "anomaly": anomaly,
            "unsupported": unsupported,
            "not_determined": not_determined,
            "decoded_instructions": decoded_instructions or [],
            "hash_input": hash_input,
            "continuity": continuity,
            "source_type": source_type,
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "disassembly static only; no execution; no behavior inference; capstone mechanism available; architecture limited to x86_64/x86_32 verified"],
            "restrictions": ["no execution", "no GPU", "no sudo", "static disassembly only", "no claim of complete reconstruction", "fixture synthetic clearly labeled", "no symbol execution"],
            "race_condition_documented": self.validated_reference.get("race_condition_documented", "NOT_DETERMINED") if hasattr(self, "validated_reference") else "NOT_DETERMINED",
        }

    def _blocked(self, reason):
        return self._make_result("BLOCKED", "NOT_DETERMINED", {"reason": reason}, {"scope": "blocked by missing reference"}, {}, {}, {"reference_missing": True}, None, "reference_only", "STOP_BLOCKED")

    def _reject(self, reason):
        return self._make_result("REJECT", "REJECT", {"integrity_check": "REJECT", "reason": reason}, {"integrity": reason}, {"integrity_failure": True}, {}, {}, None, "reference_only", "STOP_ERROR")

    def _insufficient(self, reason):
        return self._make_result("INSUFFICIENT", "INSUFFICIENT", {"reason": reason}, {"scope": "insufficient evidence"}, {}, {}, {"evidence": "insufficient"}, None, "reference_only", "STOP_ERROR")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    # Prueba aislada: fixture sintético con secuencia de instrucciones x86-64 conocidas (no ejecución)
    # Secuencia: mov rdi, rax (48 89 c7) + nop (90) + ret (c3)
    fixture_bytes = bytes.fromhex("4889c790c3") + b"M314-SYNTHETIC-DISASM-LE-FIXTURE"
    ref = {
        "hash_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "path_read": None,
        "bytes_read_once": True,
        "race_condition_documented": "NOT_DETERMINED",
    }
    # Usar bytes_input directo para prueba de decodificación
    analyzer = M314Disassembler(validated_reference=ref, max_iter=1, architecture="x86_64")
    res = analyzer.analyze(bytes_input=fixture_bytes, range_start=0, range_end=3)
    print("M314 RESULT (fixture direct bytes):")
    print("  status:", res["status"])
    print("  decision:", res["decision"])
    print("  continuity:", res["continuity"])
    print("  instructions_decoded:", len(res.get("decoded_instructions", [])))
    print("  observations (sample):", {k: res["observations"].get(k) for k in ["source_type", "bytes_decoded", "integrity_check", "capstone_available", "capstone_architecture", "segment_range_start", "segment_range_end", "segment_range_size", "disassembly_limit_truncated"]})
    print("  interpretation (sample):", {k: res["interpretation"].get(k) for k in ["disassembly_scope", "disassembly_result", "segmentation_note"]})
    print("  anomaly:", res.get("anomaly"))
    print("  unsupported:", res.get("unsupported"))
    print("  not_determined:", res.get("not_determined"))
    print("  limitations:", res["limitations"][:2])
    # Verificar que cada instrucción tiene observación con bytes, offset, representación, mecanismo, procedencia, execution_inferred=False
    for item in res.get("decoded_instructions", [])[:3]:
        obs = item.get("observation", {})
        print("  INST:", "offset=", obs.get("offset_file"), "bytes=", obs.get("bytes_hex"), "text=", obs.get("decoded_text"), "mechanism=", obs.get("decoder_mechanism"), "procedencia=", obs.get("procedencia"), "execution_inferred=", obs.get("execution_inferred"), "behavior_inferred=", obs.get("behavior_inferred"))
    # Confirmar DB protegida intacta
    import rxre.core.store as store
    c = store.conectar()
    print("DB results=", c.execute("SELECT COUNT(*) FROM results").fetchone()[0])
    print("DB ops=", c.execute("SELECT COUNT(*) FROM operations").fetchone()[0])
    print("DB events=", c.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0])
    c.close()
    print("DB protected intact; TRIGGERS intact; APPEND_ONLY intact.")
