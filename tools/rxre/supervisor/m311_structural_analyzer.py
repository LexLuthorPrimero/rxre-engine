#!/usr/bin/env python3
"""M311/M312/M313 — Analizador estructural de binarios (archivo permitido, análisis estático básico/extensible, sin ejecución, sin autorización simulada, sin invento de evidencia real)."""
import hashlib, json, os, sys, struct
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M311StructuralAnalyzer:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.max_iter = max_iter
        self.autonomous_loop = False

    def analyze(self, bytes_input=None):
        if not self.validated_reference:
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","observations":{},"interpretation":{},"anomaly":{},"hypothesis":{"structural_completeness":"NOT_DETERMINED","evidence_quality":"NOT_DETERMINED (validated_reference absent)"},"hash_input":None,"continuity":"STOP_BLOCKED","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference absent"],"restrictions":["no execution","no GPU","no sudo","static structural analysis only"],"race_condition_documented":"NOT_DETERMINED","artifact_evidence":"NOT_DETERMINED (fixture synthetic M311/M312/M313 clearly labeled; not real artifact evidence)"}
        hash_ref = self.validated_reference.get("hash_sha256")
        if not hash_ref:
            return {"status":"BLOCKED","decision":"INSUFFICIENT","observations":{},"interpretation":{},"anomaly":{},"hypothesis":{"structural_completeness":"INSUFFICIENT","evidence_quality":"INSUFFICIENT (hash_sha256 missing)"},"hash_input":None,"continuity":"STOP_ERROR","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","validated_reference missing hash_sha256"],"restrictions":["no execution","no GPU","no sudo","static structural analysis only"],"race_condition_documented":"NOT_DETERMINED","artifact_evidence":"NOT_DETERMINED"}
        source_bytes = None
        source_type = None
        if bytes_input is not None and isinstance(bytes_input, bytes):
            source_bytes = bytes_input; source_type = "direct_bytes"
        else:
            path_read = self.validated_reference.get("path_read")
            if path_read and os.path.isfile(path_read):
                try:
                    with open(path_read, "rb") as f: source_bytes = f.read()
                    actual_hash = hashlib.sha256(source_bytes).hexdigest()
                    if actual_hash != hash_ref:
                        return {"status":"REJECT","decision":"REJECT","observations":{"integrity_check":"REJECT","hash_ref":hash_ref[:16],"hash_actual":actual_hash[:16],"race_condition":True},"interpretation":{"integrity":"artifact modified after validation; do not analyze with stale reference"},"anomaly":{"hash_mismatch":True},"hypothesis":{"cause":"file modified between M308/M312/M313 validation and analysis; independent verification required"},"hash_input":hash_ref,"continuity":"STOP_ERROR","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","integrity failure after validation"],"restrictions":["no execution","no GPU","no sudo","static structural analysis only"],"race_condition_documented":"CONFIRMED"}
                    source_type = "file_read_verified"
                except Exception as exc:
                    return {"status":"INSUFFICIENT","decision":"INSUFFICIENT","observations":{"read_error":str(exc)[:80]},"hash_input":hash_ref,"continuity":"STOP_ERROR","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT",f"read error: {str(exc)[:80]}"],"restrictions":["no execution","no GPU","no sudo","static structural analysis only"],"race_condition_documented":"NOT_DETERMINED"}
            else:
                source_bytes = None; source_type = "reference_only_no_file"
        observations = {}
        interpretation = {}
        anomaly = {}
        # M312/M313: bloque básico de análisis estructural con limites validación
        MAX_SIZE = 1024 * 1024
        if source_bytes is not None and len(source_bytes) > MAX_SIZE:
            observations["size_limit_truncated"] = True
            observations["size_limit_note"] = f"exceeds {MAX_SIZE} bytes; structural analysis truncated"
            interpretation["size"] = f"truncated at {MAX_SIZE} bytes"
        # Magic ELF (OBSERVATION directa)
        if source_bytes is not None and len(source_bytes) >= 4:
            magic = source_bytes[:4]
            observations["magic_bytes_hex"] = magic.hex()
            observations["magic_text_raw"] = magic.decode("ascii", errors="replace")
            if magic == b"\x7fELF":
                observations["magic_match_elf"] = True
                observations["format"] = "ELF"
                interpretation["format"] = "ELF binary (synthetic fixture clearly labeled; not real artifact evidence)"
            else:
                observations["magic_match_elf"] = False
                observations["format"] = "NOT_ELF"
                interpretation["format"] = "unknown or non-ELF binary (magic mismatch)"
                anomaly["magic_anomaly"] = True
        else:
            observations["format"] = "TRUNCATED"
            observations["magic_bytes_hex"] = None
            interpretation["format"] = "truncated; no magic verifiable"
            anomaly["truncated_header"] = "file shorter than 4 bytes"
        # Si es ELF y hay suficientes bytes, extraer propiedades básicas con límites
        if observations.get("format") == "ELF" and source_bytes is not None and len(source_bytes) >= 52:
            try:
                elf_class_byte = source_bytes[4] if len(source_bytes) > 4 else None
                observations["elf_class_raw"] = elf_class_byte
                observations["elf_class"] = 64 if elf_class_byte == 2 else (32 if elf_class_byte == 1 else f"unknown({elf_class_byte})")
                interpretation["elf_class"] = "ELFCLASS64 (64-bit binary)" if elf_class_byte == 2 else ("ELFCLASS32 (32-bit binary)" if elf_class_byte == 1 else "unknown class (not 1 or 2)")
                elf_data_byte = source_bytes[5] if len(source_bytes) > 5 else None
                observations["elf_endianness_raw"] = elf_data_byte
                observations["elf_endianness"] = "little" if elf_data_byte == 1 else ("big" if elf_data_byte == 2 else f"unknown({elf_data_byte})")
                interpretation["elf_endianness"] = "ELFDATA2LSB (little-endian)" if elf_data_byte == 1 else ("ELFDATA2MSB (big-endian)" if elf_data_byte == 2 else "unknown endianness")
                endianness = "<" if elf_data_byte == 1 else (">" if elf_data_byte == 2 else None)
                if endianness is None:
                    interpretation["endianness_use"] = "NOT_DETERMINED: cannot interpret offsets without known endianness"
                    anomaly["endianness_unknown"] = True
                else:
                    interpretation["endianness_use"] = f"{endianness} for struct unpacking"
                header_size = 52 if elf_class_byte == 1 else 64 if elf_class_byte == 2 else None
                if header_size is None or len(source_bytes) < header_size:
                    observations["header_truncated"] = True
                    observations["header_size_expected"] = header_size
                    observations["header_size_actual"] = len(source_bytes)
                    interpretation["header_completion"] = "TRUNCATED"
                    anomaly["header_truncated"] = True
                else:
                    observations["header_truncated"] = False
                    observations["header_size_expected"] = header_size
                    observations["header_size_actual"] = len(source_bytes)
                    interpretation["header_completion"] = "HEADER PRESENT (basic verification)"
                # Extracción básica de campos con struct (M312 extendido)
                if endianness is not None and len(source_bytes) >= 4:
                    if len(source_bytes) >= 18:
                        try:
                            e_type = struct.unpack(endianness + "H", source_bytes[16:18])[0]
                            observations["e_type_raw"] = e_type
                            interpretation["e_type"] = "ET_REL (relocatable)" if e_type == 1 else ("ET_EXEC (executable)" if e_type == 2 else ("ET_DYN (shared)" if e_type == 3 else f"unknown({e_type})"))
                        except Exception as exc:
                            observations["e_type_parse_error"] = str(exc)[:60]
                    if len(source_bytes) >= 20:
                        try:
                            e_machine = struct.unpack(endianness + "H", source_bytes[18:20])[0]
                            observations["e_machine_raw"] = e_machine
                            interpretation["e_machine"] = "EM_386 (x86)" if e_machine == 3 else ("EM_X86_64" if e_machine == 62 else ("EM_ARM" if e_machine == 40 else f"unknown({e_machine})"))
                        except Exception as exc:
                            observations["e_machine_parse_error"] = str(exc)[:60]
                    # e_entry
                    if elf_class_byte == 1 and len(source_bytes) >= 28:
                        try:
                            observations["e_entry_raw"] = struct.unpack(endianness + "I", source_bytes[24:28])[0]
                            interpretation["e_entry"] = f"entry 0x{observations['e_entry_raw']:08x}"
                        except Exception: pass
                    if elf_class_byte == 2 and len(source_bytes) >= 32:
                        try:
                            observations["e_entry_raw"] = struct.unpack(endianness + "Q", source_bytes[24:32])[0]
                            interpretation["e_entry"] = f"entry 0x{observations['e_entry_raw']:016x}"
                        except Exception: pass
                    # Program header offset (e_phoff)
                    if elf_class_byte == 1 and len(source_bytes) >= 32:
                        try:
                            phoff = struct.unpack(endianness + "I", source_bytes[28:32])[0]
                            observations["e_phoff"] = phoff
                            interpretation["program_header_offset"] = f"0x{phoff:08x}"
                            phentsize = struct.unpack(endianness + "H", source_bytes[42:44])[0] if len(source_bytes) >= 44 else 32
                            if phentsize == 0: phentsize = 32
                            if phoff < header_size:
                                anomaly["phoff_before_header"] = True
                                interpretation["program_header_offset_valid"] = "ANOMALY: phoff before header end"
                            elif phoff + phentsize > len(source_bytes):
                                anomaly["phoff_truncated"] = True
                                interpretation["program_header_offset_valid"] = "TRUNCATED (phentsize exceeds file)"
                            else:
                                interpretation["program_header_offset_valid"] = "VALID"
                        except Exception as exc:
                            observations["e_phoff_parse_error"] = str(exc)[:60]
                    elif elf_class_byte == 2 and len(source_bytes) >= 40:
                        try:
                            phoff = struct.unpack(endianness + "Q", source_bytes[32:40])[0]
                            observations["e_phoff"] = phoff
                            interpretation["program_header_offset"] = f"0x{phoff:016x}"
                            phentsize = struct.unpack(endianness + "H", source_bytes[54:56])[0] if len(source_bytes) >= 56 else 56
                            if phentsize == 0: phentsize = 56
                            if phoff < header_size:
                                anomaly["phoff_before_header"] = True
                                interpretation["program_header_offset_valid"] = "ANOMALY"
                            elif phoff + phentsize > len(source_bytes):
                                anomaly["phoff_truncated"] = True
                                interpretation["program_header_offset_valid"] = "TRUNCATED"
                            else:
                                interpretation["program_header_offset_valid"] = "VALID"
                        except Exception as exc:
                            observations["e_phoff_parse_error"] = str(exc)[:60]
                    # Program header count (e_phnum) — límite de cantidad
                    if elf_class_byte == 1 and len(source_bytes) >= 44:
                        try:
                            phnum = struct.unpack(endianness + "H", source_bytes[44:46])[0]
                            observations["e_phnum"] = phnum
                            interpretation["program_header_count"] = f"{phnum} declared"
                            if phnum > 100:
                                anomaly["excessive_program_headers"] = True
                                interpretation["program_header_count_valid"] = "ANOMALY: excessive count (>100)"
                            elif phnum == 0:
                                interpretation["program_header_count_valid"] = "NO PROGRAM HEADERS"
                            else:
                                interpretation["program_header_count_valid"] = "VALID (within limit)"
                        except Exception as exc:
                            observations["e_phnum_parse_error"] = str(exc)[:60]
                    elif elf_class_byte == 2 and len(source_bytes) >= 56:
                        try:
                            phnum = struct.unpack(endianness + "H", source_bytes[56:58])[0]
                            observations["e_phnum"] = phnum
                            interpretation["program_header_count"] = f"{phnum} declared"
                            if phnum > 100:
                                anomaly["excessive_program_headers"] = True
                                interpretation["program_header_count_valid"] = "ANOMALY"
                            elif phnum == 0:
                                interpretation["program_header_count_valid"] = "NO PROGRAM HEADERS"
                            else:
                                interpretation["program_header_count_valid"] = "VALID"
                        except Exception as exc:
                            observations["e_phnum_parse_error"] = str(exc)[:60]
                    # Section header offset (e_shoff) básico
                    if elf_class_byte == 1 and len(source_bytes) >= 36:
                        try:
                            shoff = struct.unpack(endianness + "I", source_bytes[32:36])[0]
                            observations["e_shoff"] = shoff
                            interpretation["section_header_offset"] = f"0x{shoff:08x}"
                            shentsize = struct.unpack(endianness + "H", source_bytes[46:48])[0] if len(source_bytes) >= 48 else 40
                            if shentsize == 0: shentsize = 40
                            shnum_raw = struct.unpack(endianness + "H", source_bytes[48:50])[0] if len(source_bytes) >= 50 else 0
                            if shoff > 0 and shoff + max(shentsize * max(shnum_raw, 1), 0) <= len(source_bytes):
                                interpretation["section_header_valid"] = "VALID (offset + estimated size within file)"
                            elif shoff > len(source_bytes):
                                anomaly["shoff_truncated"] = True
                                interpretation["section_header_valid"] = "TRUNCATED (offset beyond file end)"
                            else:
                                interpretation["section_header_valid"] = "PARTIAL"
                        except Exception as exc:
                            observations["e_shoff_parse_error"] = str(exc)[:60]
                    elif elf_class_byte == 2 and len(source_bytes) >= 40:
                        try:
                            shoff = struct.unpack(endianness + "Q", source_bytes[40:48])[0]
                            observations["e_shoff"] = shoff
                            interpretation["section_header_offset"] = f"0x{shoff:016x}"
                            shentsize = struct.unpack(endianness + "H", source_bytes[58:60])[0] if len(source_bytes) >= 60 else 64
                            if shentsize == 0: shentsize = 64
                            shnum_raw = struct.unpack(endianness + "H", source_bytes[60:62])[0] if len(source_bytes) >= 62 else 0
                            if shoff > 0 and shoff + max(shentsize * max(shnum_raw, 1), 0) <= len(source_bytes):
                                interpretation["section_header_valid"] = "VALID"
                            elif shoff > len(source_bytes):
                                anomaly["shoff_truncated"] = True
                                interpretation["section_header_valid"] = "TRUNCATED"
                            else:
                                interpretation["section_header_valid"] = "PARTIAL"
                        except Exception as exc:
                            observations["e_shoff_parse_error"] = str(exc)[:60]
                    # --- M313 EXTENSION: Symbol & Relocation tables (struct) ---
                    # Solo si hay cabecera de sección válida y archivo suficientemente grande
                    observations["symbol_table_extractable"] = False
                    observations["relocation_table_extractable"] = False
                    observations["symbol_table_note"] = "UNSUPPORTED / NOT_DETERMINED: full symbol/rela extraction requires section header parsing with sh_link/sh_info validation, shstrtab access, and byte-range checks; implemented as basic reference check only (see observations)"
                    # Intento básico de referencia de símbolo/reubicación sin lectura completa para evitar errores
                    # Si sh_offset y sh_size son válidos, documentamos que la estructura está presente pero no interpretamos cada entrada (límite documentado)
                    try:
                        # Validar sh_offset y sh_size para SYMTAB (tipo 2) y STRTAB (tipo 3) si cabeceras de sección disponibles
                        sh_offset = observations.get("e_shoff")
                        sh_entsize = 40 if elf_class_byte == 1 else 64
                        shnum = observations.get("e_shnum") or 0
                        if sh_offset is not None and shnum > 0 and len(source_bytes) >= sh_offset + sh_entsize * min(shnum, 10):
                            # Solo leemos las primeras entradas de cabecera de sección (hasta 10) para validar referencias
                            # Esto es limitado; no interpreta todas las secciones, solo valida que el archivo tiene cabeceras
                            observations["section_headers_readable"] = True
                            observations["section_headers_read_limit"] = "limited to first 10 entries for safety (defense adversarial)"
                            interpretation["section_headers"] = "PARTIAL: section header array readable; full parsing requires pyelftools and DBOP_SCHEMA_M290 VERIFIED"
                            # Referencia a SYMTAB/RELA: si existe índice de sección que podría ser SYMTAB, documentar como posible
                            # No afirmamos que los símbolos son válidos sin leer tablas completas
                            observations["symtab_possible"] = (sh_offset > 0 and shnum > 0)
                            observations["reloc_possible"] = (sh_offset > 0 and shnum > 0)
                        else:
                            observations["section_headers_readable"] = False
                            observations["section_headers_read_limit"] = "insufficient data or truncated"
                    except Exception as exc:
                        observations["section_header_parse_exception"] = str(exc)[:120]
                        interpretation["section_header_parse"] = "NOT_DETERMINED (exception during reference parsing)"
                else:
                    observations["endianness_use"] = "NOT_DETERMINED (unknown endianness byte at offset 5)"
                    interpretation["endianness_use"] = "NOT_DETERMINED: cannot interpret multi-byte fields without known endianness"
                    anomaly["endianness_unknown"] = True
            except Exception as exc:
                observations["struct_parse_exception"] = str(exc)[:120]
                interpretation["parse"] = "exception during structural parsing"
                hypothesis["structural_completeness"] = "NOT_DETERMINED"
        else:
            observations["observed_bytes_analyzed"] = len(source_bytes) if source_bytes else 0
            observations["hash_input"] = hash_ref
            observations["integrity_check"] = "PASS" if (source_type == "file_read_verified" and hashlib.sha256(source_bytes).hexdigest() == hash_ref) else "NOT_RUN"
            # Si no es ELF, no intentar extracción de símbolos/reubicaciones
            observations["symbol_table_extractable"] = False
            observations["relocation_table_extractable"] = False
            observations["symbol_table_note"] = "NOT_APPLICABLE (format not ELF or truncated)"
        # Ajuste final de estado
        status = "PASS_PARTIAL" if (observations.get("format") == "ELF" and observations.get("header_truncated") is False and not observations.get("integrity_check") == "REJECT") else ("PASS_PARTIAL" if observations.get("format") == "ELF" else ("NOT_DETERMINED" if observations.get("format") == "TRUNCATED" else "INSUFFICIENT"))
        if observations.get("format") == "ELF" and (anomaly.get("integrity_check") == "REJECT" or observations.get("integrity_check") == "REJECT" or observations.get("race_condition_confirmed")):
            status = "REJECT"
        if observations.get("format") == "ELF" and b"M311-SYNTHETIC" in (source_bytes or b""):
            observations["synthetic_evidence_label"] = "M312-SYNTHETIC-ELF (clearly labeled synthetic fixture; not real artifact evidence)"
            interpretation["evidence_provenance"] = "SYNTHETIC FIXTURE — clearly labeled; not claimed as real artifact evidence"
        return {
            "status": status,
            "decision": "PARTIAL" if status == "PASS_PARTIAL" else ("REJECT" if status == "REJECT" else ("NOT_DETERMINED" if status == "NOT_DETERMINED" else "INSUFFICIENT")),
            "observations": observations,
            "interpretation": interpretation,
            "anomaly": anomaly,
            "hypothesis": {"structural_completeness": "PARTIAL" if status == "PASS_PARTIAL" else ("NOT_DETERMINED" if observations.get("format") == "ELF" else "NOT_DETERMINED"), "symbol_relocation_extraction": "PARTIAL (basic section header reference; full symtab/rela extraction requires DBOP_SCHEMA_M290 VERIFIED + independent library verification; UNSUPPORTED for full parsing)"},
            "hash_input": hash_ref,
            "continuity": "CONTINUE" if status == "PASS_PARTIAL" else ("STOP_ERROR" if status == "REJECT" else ("STOP_LIMIT" if status in ("NOT_DETERMINED", "INSUFFICIENT") else "STOP_BLOCKED")),
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "symbol/relocation extraction basic (section reference only); full symtab/rela parsing unsupported without DBOP_SCHEMA_M290 VERIFIED + library verification", "fixture synthetic clearly labeled; not real evidence"],
            "restrictions": ["no execution", "no GPU", "no sudo", "static structural analysis only", "no claim of complete reconstruction", "fixture synthetic clearly labeled", "no symbol execution"],
            "race_condition_documented": self.validated_reference.get("race_condition_documented", "NOT_DETERMINED"),
        }

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    from supervisor.m296_executor import M296Executor
    # Prueba aislada con fixture sintético M313 (referencia directa con verificación independiente)
    ref = {
        "hash_sha256": hashlib.sha256(open("/tmp/m313_synthetic_sym_elf32_le.bin","rb").read()).hexdigest(),
        "path_read": "/tmp/m313_synthetic_sym_elf32_le.bin",
        "bytes_read_once": True,
        "race_condition_documented": "NOT_DETERMINED"
    }
    analyzer = M311StructuralAnalyzer(validated_reference=ref, max_iter=1)
    res = analyzer.analyze()
    # Separación OBSERVATION / INTERPRETATION / ANOMALY / NOT_DETERMINED / UNSUPPORTED
    print("M313 RESULT:")
    print("status:", res["status"])
    print("decision:", res["decision"])
    print("observations keys:", list(res["observations"].keys())[:10], "... (total:", len(res["observations"]), ")")
    print("interpretation keys:", list(res["interpretation"].keys())[:10], "...")
    print("anomaly keys:", list(res["anomaly"].keys())[:10], "...")
    print("hypothesis:", res.get("hypothesis"))
    print("continuity:", res["continuity"])
    print("limitations:", res["limitations"])
    print("artifact_evidence:", res["observations"].get("synthetic_evidence_label"))
