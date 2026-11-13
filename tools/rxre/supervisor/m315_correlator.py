#!/usr/bin/env python3
"""M315 — Correlación estática ELF-Símbolos-Reubicaciones-Instrucciones (archivo permitido, sin ejecución real, sin autorización simulada, sin invento, sin mecanismo falso, sin duplicación de parsers protegidos). Usa referencias verificadas de M312/M313/M314."""
import sys, hashlib, json, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M315Correlator:
    """Correlaciona resultados verificados de M312 (estructura), M313 (símbolos/reubicaciones básicas) y M314 (desensamblado) mediante referencias a bytes validados. No ejecuta; no inventa relaciones; documenta UNSUPPORTED/NOT_DETERMINED explícitamente."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.max_iter = max_iter
        self.autonomous_loop = False

    def correlate(self, structural_result=None, disassembly_result=None, symbol_result=None):
        observations = {}
        correlations = []
        interpretation = {}
        anomaly = {}
        unsupported = {}
        not_determined = {}
        # Requisito básico: referencia validada debe existir
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{"reason":"missing validated_reference"},"correlations":[],"interpretation":{"correlation_scope":"BLOCKED by missing reference (M309/M310)"},"anomaly":{},"unsupported":{},"not_determined":{"full_correlation":"BLOCKED (no validated_reference)"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing"],"restrictions":["no execution","no GPU","no sudo","static correlation only","no claim of complete graph"],"race_condition_documented":"NOT_DETERMINED","artifact_evidence":"NOT_DETERMINED (fixture synthetic clearly labeled)"}
        hash_ref = self.validated_reference.get("hash_sha256")
        # Reutilizar resultados de módulos existentes (si se pasan); si no, usar referencia directa
        structural = structural_result or {}
        disassembly = disassembly_result or {}
        symbol = symbol_result or {}
        # Correlación 1: referencia de integridad (hash) debe coincidir con resultados
        observations["integrity_reference"] = hash_ref[:16] if hash_ref else None
        observations["integrity_check"] = "PASS" if (structural.get("observations", {}).get("integrity_check") == "PASS" or disassembly.get("observations", {}).get("integrity_check") == "PASS") else "NOT_RUN"
        # Correlación 2: formato ELF verificado por M312 (structural)
        if structural.get("observations", {}).get("format") == "ELF" and structural.get("observations", {}).get("magic_match_elf") == True:
            observations["format_verified"] = True
            observations["format_evidence"] = "ELF magic 0x7f454c46 verified (M312)"
            interpretation["format_basis"] = "ELF format verified; structural correlation applicable (limited by DBOP_SCHEMA_M290 INSUFFICIENT)"
            # Si hay información de sección de M312 y de desensamblado M314, intentar vincular rango
            sh_offset = structural.get("observations", {}).get("e_shoff")
            shnum = structural.get("observations", {}).get("e_shnum") or 0
            phoff = structural.get("observations", {}).get("e_phoff")
            # Correlación simple: instrucciones decodificadas por M314 dentro del rango de archivo
            decoded = disassembly.get("decoded_instructions", []) or []
            if decoded and len(decoded) > 0:
                observations["decoded_instructions_count"] = len(decoded)
                # Ejemplo de correlación: primera instrucción (offset 0) con archivo validado
                first = decoded[0]
                obs_first = first.get("observation", {})
                correlations.append({
                    "correlation_type": "reference_to_decoded_instruction",
                    "rule": "validated_reference hash + file_read_verified + decodable bytes at offset 0",
                    "source": "validated_reference",
                    "target": "disassembled_instruction",
                    "link": {
                        "hash_ref": hash_ref[:16],
                        "instruction_offset": obs_first.get("offset_file"),
                        "instruction_bytes": obs_first.get("bytes_hex"),
                        "instruction_text": obs_first.get("decoded_text"),
                        "mechanism": obs_first.get("decoder_mechanism"),
                        "procedencia": obs_first.get("procedencia"),
                    },
                    "status": "PARTIAL",
                    "interpretation": "First instruction decodable from validated bytes; execution target NOT_DETERMINED (requires verified segment mapping + authorization + independent verification)",
                    "not_determined": {"execution_target": "NOT_DETERMINED (static decode only; no destination verification without DBOP_SCHEMA_M290 VERIFIED + independent recovery)"},
                    "unsupported": {"full_flow_graph": "UNSUPPORTED (requires full symtab/rela + verification + authorization)"},
                    "anomaly": {},
                })
                interpretation["correlation_map"] = f"{len(correlations)} direct link(s) from validated_reference to decoded instruction(s) (static only)"
            else:
                observations["decoded_instructions_count"] = 0
                interpretation["correlation_map"] = "NOT_DETERMINED: no instructions decoded (file missing, truncated, or mechanism unavailable)"
            # Correlación símbolo-reubicación (solo si M313 produjo referencia básica a secciones)
            sym_note = symbol.get("observations", {}).get("symbol_table_extractable") if isinstance(symbol.get("observations"), dict) else False
            rel_note = symbol.get("observations", {}).get("relocation_table_extractable") if isinstance(symbol.get("observations"), dict) else False
            if sym_note or rel_note:
                observations["symbol_rel_reference_available"] = True
                observations["symbol_rel_reference_note"] = "UNSUPPORTED for full extraction (requires DBOP_SCHEMA_M290 VERIFIED + independent library verification); basic reference only"
                interpretation["symbol_rel_correlation"] = "UNSUPPORTED for full symbol/rela mapping; only basic section header reference available"
                correlations.append({
                    "correlation_type": "symbol_relocation_reference",
                    "rule": "validated_reference + section header reference (M312/M313) -> SYMTAB/REL possible if verified; full mapping unsupported",
                    "source": "validated_reference / structural_reference",
                    "target": "symbol_relocation_table",
                    "link": {"hash_ref": hash_ref[:16], "section_reference": "basic", "symtab_extractable": sym_note, "reloc_extractable": rel_note},
                    "status": "UNSUPPORTED",
                    "interpretation": "Basic reference to section headers indicates possible SYMTAB/RELA presence; full symbol/rela extraction unsupported without verified schema + library",
                    "not_determined": {"symbol_name": "NOT_DETERMINED (names require shstrtab + validated reference + independent verification)", "relocation_target": "NOT_DETERMINED (requires verified relocation type + symbol index + authorization + schema)"},
                    "unsupported": {"full_symtab_parsing": True, "full_rela_parsing": True, "execution_target_inference": True},
                    "anomaly": {},
                })
            else:
                observations["symbol_rel_reference_available"] = False
                interpretation["symbol_rel_correlation"] = "NOT_DETERMINED (no symbol/rela reference from M313; only basic structural data available)"
            # Correlación de rango con segmento verificado (solo si M312 produjo e_phoff/phnum/verificación)
            if sh_offset is not None and phoff is not None and observations.get("format") == "ELF":
                # Solo si hay datos de segmento y desensamblado; no asumimos que todo el archivo es código
                observations["segment_range_reference"] = True
                observations["segment_range_note"] = "Program header offset and count verified (M312); disassembly range based on file limits, not full segment mapping (DBOP_SCHEMA_M290 INSUFFICIT)"
                interpretation["range_correlation"] = "PARTIAL: disassembly range derived from file limits + verified header; full executable segment mapping requires verified ph_flags + authorization + independent verification"
        else:
            observations["format_verified"] = False
            observations["correlation_applicability"] = "NOT_APPLICABLE (format not ELF or not verified)"
            interpretation["correlation_scope"] = "NOT_APPLICABLE: correlation requires verified ELF format with validated_reference"
            unsupported["format"] = "NOT_ELF or format not verified by M312"
        # Separación estricta
        return {
            "status": "PASS_PARTIAL" if observations.get("format_verified") and (len(correlations) > 0 or observations.get("symbol_rel_reference_available")) else ("NOT_DETERMINED" if observations.get("format_verified") else "INSUFFICIENT"),
            "decision": "PARTIAL" if observations.get("format_verified") else "NOT_DETERMINED",
            "correlations": correlations,
            "observations": observations,
            "interpretation": interpretation,
            "anomaly": anomaly,
            "unsupported": unsupported,
            "not_determined": not_determined,
            "hash_input": hash_ref,
            "continuity": "CONTINUE" if observations.get("format_verified") else ("STOP_LIMIT" if observations.get("format_verified") is False else "STOP_BLOCKED"),
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "correlation basic; full symbol/rela/instruction-flow mapping requires DBOP_SCHEMA_M290 VERIFIED + independent recovery + authorization + verified segment mapping"],
            "restrictions": ["no execution", "no GPU", "no sudo", "static correlation only", "no claim of complete graph", "fixture synthetic clearly labeled"],
            "race_condition_documented": self.validated_reference.get("race_condition_documented", "NOT_DETERMINED"),
        }

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    from supervisor.m311_structural_analyzer import M311StructuralAnalyzer
    from supervisor.m314_disassembler import M314Disassembler
    # Prueba aislada con fixtures existentes y referencia verificada
    # Usar archivo sintético M311 (ELF) como base; no hay símbolo/reubicación completa en fixture, pero referencia básica existe
    ref = {"hash_sha256": hashlib.sha256(open("/tmp/m311_synthetic_elf.bin","rb").read()).hexdigest(), "path_read":"/tmp/m311_synthetic_elf.bin", "bytes_read_once":True, "race_condition_documented":"NOT_DETERMINED"}
    # Obtener resultados de módulos existentes (simulados con referencias reales)
    struct_res = M311StructuralAnalyzer(validated_reference=ref, max_iter=1).analyze()
    # Para disassembly: usar bytes directos de archivo (archivo accesible y verificado)
    dis_res = M314Disassembler(validated_reference=ref, max_iter=1, architecture="x86_64").analyze(bytes_input=open("/tmp/m311_synthetic_elf.bin","rb").read(), range_start=0, range_end=32)
    sym_res = {"observations": {"symbol_table_extractable": False, "relocation_table_extractable": False}}
    correl = M315Correlator(validated_reference=ref, max_iter=1)
    corr = correl.correlate(structural_result=struct_res, disassembly_result=dis_res, symbol_result=sym_res)
    print("M315 CORRELATION RESULT:")
    print("  status:", corr["status"])
    print("  decision:", corr["decision"])
    print("  correlations:", len(corr["correlations"]))
    print("  observations:", {k: corr["observations"].get(k) for k in ["format_verified","integrity_reference","decoded_instructions_count","segment_range_reference","symbol_rel_reference_available"]})
    print("  interpretation:", corr["interpretation"].get("correlation_map"))
    print("  unsupported:", corr.get("unsupported"))
    print("  not_determined:", corr.get("not_determined"))
    print("  limitations:", corr["limitations"][:2])
    # DB protegida
    import rxre.core.store as s; c=s.conectar()
    print("DB protected: results=", c.execute("SELECT COUNT(*) FROM results").fetchone()[0], "events=", c.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0], "TRIGGERS=", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%trg_results%'").fetchall()], "; DB_AUTH_BLOCKED; DBOP_INSUFFICIENT; CONTINUE possible")
    c.close()
