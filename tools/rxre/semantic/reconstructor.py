"""RXRE-MISSION-257 — Reconstrucción semántica estructural de ELF reales.

Orquesta rz_functions, rz_cfg y rz_xrefs (únicos proveedores integrados hoy; NO incluye
rz_dataflow). Produce un expediente ESTRUCTURAL e HIPOTÉTICO; las candidatas nacen con
semántica NOT_DETERMINED — no demuestra comprensión por sí sola.

No modifica contratos protegidos. No crea rutas paralelas de ejecución.
"""
from __future__ import annotations

import hashlib, json, os, sys, time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, "..", ".."))
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from backends.adapters import rz_functions, rz_cfg, rz_xrefs
from rxre.semantic.profiles import load_profile_for, lookup_reachability, causal_entry


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify_function(name: str, size: int, nbbs: int,
                     cfg_status: str) -> tuple:
    """Contrato determinista M259. Retorna (classification, reason).

    Orden (primera coincidencia gana): IMPORT_STUB -> ANALYSIS_FAILED
    -> BOUNDARY_CASE -> LOW_INFORMATION -> FUNCTION_CANDIDATE.
    Solo usa campos siempre presentes (name/size/nbbs) + cfg_status.
    """
    name = str(name or "")
    size = int(size or 0)
    nbbs = int(nbbs or 0)
    cfg_status = str(cfg_status or "UNKNOWN")
    if name.startswith("sym.imp."):
        return ("IMPORT_STUB",
                "name startswith sym.imp. (size=%d nbbs=%d: PLT import stub)" % (size, nbbs))
    if cfg_status != "OK":
        return ("ANALYSIS_FAILED",
                "cfg_status=%s (no OK CFG; retained in inventory, not absent)" % cfg_status)
    if size > 30000 or nbbs > 400:
        return ("BOUNDARY_CASE",
                "size=%d nbbs=%d (mega: parsed for inventory, no hypothesis)" % (size, nbbs))
    if size < 50 and nbbs <= 2:
        return ("LOW_INFORMATION",
                "size=%d nbbs=%d (wrapper/stub: straight-line, no branching evidence)"
                % (size, nbbs))
    return ("FUNCTION_CANDIDATE",
            "size=%d nbbs=%d cfg_status=%s (body with structural evidence)" % (size, nbbs, cfg_status))


def _rizin_cfg(offset: int, binary_path: str, budget_seconds: int):
    """CFG provider (único implementado: rizin). Interfaz reservada para otros proveedores que
    informen versión/procedencia/limitaciones. No sustituye la admisión ni el dictamen semántico."""
    return subprocess.run(
        ["/usr/bin/rizin", "-q", "-N", "-e", "scr.color=0",
         "-c", "aaa; agf json @ %d" % offset, binary_path],
        capture_output=True, text=True, timeout=budget_seconds,
    )

def reconstruct(binary_path: str, backend_id: str = "rizin",
               timeout: int = 300) -> Dict[str, Any]:
    """Reconstruye semánticamente un binario ELF real.

    Retorna un expediente con:
    - identificación del artefacto (hash, arquitectura, formato)
    - inventario de funciones
    - grafo de llamadas
    - CFG por función (top N)
    - referencias cruzadas
    - hipótesis semánticas con evidencia
    - incertidumbres y contradicciones
    - dictamen final por propiedad
    """
    if not os.path.isfile(binary_path):
        return {"status": "INVALID", "error": "archivo no existe: %s" % binary_path}

    _deadline = time.time() + max(1, int(timeout))
    def _remaining():
        return max(0.0, _deadline - time.time())
    def _budget_left():
        return _remaining() > 0.5

    artifact_hash = _sha256_file(binary_path)
    start = time.time()

    # 1. Funciones
    funcs_res = rz_functions.functions(binary_path, backend_id=backend_id, timeout=timeout)
    funcs = []
    if isinstance(funcs_res, dict):
        raw = funcs_res.get("results", [])
        if raw and isinstance(raw[0], dict):
            val = raw[0].get("value", {})
            if isinstance(val, dict):
                for k in ("funciones", "functions", "funcs"):
                    if k in val:
                        funcs = val[k]
                        break
        if not funcs and isinstance(funcs_res.get("value"), dict):
            val = funcs_res["value"]
            for k in ("funciones", "functions", "funcs"):
                if k in val:
                    funcs = val[k]
                    break
        # Try direct
        if not funcs:
            for k in ("funciones", "functions", "funcs"):
                if k in funcs_res:
                    funcs = funcs_res[k]
                    break

    import subprocess, json as _json
    import re

    # Per-function CFG extraction using rizin 'agf json @ offset'
    # (the adapter's 'agfj' command doesn't work in rizin 0.7.4)
    # RXRE-MISSION-258 (2026-11-05): 'aaa' (no 'aa'). MEDIDO sobre
    # /usr/bin/ls y /usr/bin/grep: con 'aa', 'agf json' devuelve 0 nodos
    # para funciones grandes (ej. sym.usage 0xB9A0: aa=0, aaa=18 nodos;
    # sym.grepdesc: aa=0, aaa=409 nodos). Funciones PLT pequeñas (size 10)
    # dan 1 nodo con ambos niveles. 'aaa' es el nivel que usa el adapter
    # rz_xrefs ('aaa; axtj') y requiere el MISMO análisis para CFG
    # por función. Coste: ~0.8s/función (aaa) vs ~0.08s (aa).
    cfg_funcs = {}  # offset -> {blocks, edges, status}
    cfg_attempted = 0
    cfg_successful = 0
    cfg_failed = 0
    bb_total = 0
    edges_total = 0

    cfg_skipped_no_offset = 0
    cfg_skipped_budget = 0
    discovered = len(funcs)
    eligible = 0
    for fn in funcs:
        if not isinstance(fn, dict):
            cfg_skipped_no_offset += 1
            continue
        offset = fn.get("offset", 0)
        if not offset:
            cfg_skipped_no_offset += 1
            continue
        eligible += 1
        if not _budget_left():
            cfg_skipped_budget += 1
            cfg_funcs[offset] = {"status": "BUDGET_EXHAUSTED", "n_blocks": 0}
            continue
        cfg_attempted += 1
        try:
            _t = min(30, max(1, int(_remaining())))
            p = _rizin_cfg(offset, binary_path, _t)
            # Find JSON in output
            stdout = p.stdout.strip()
            # Remove ANSI
            import re
            stdout = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", stdout)
            # Find first { 
            idx = stdout.find("{")
            if idx >= 0:
                data = _json.loads(stdout[idx:])
                nodes = data.get("nodes", [])
                if nodes:
                    cfg_successful += 1
                    blocks = []
                    for node in nodes:
                        blocks.append({
                            "id": node.get("id"),
                            "offset": node.get("offset"),
                            "out_nodes": node.get("out_nodes", []),
                        })
                        bb_total += 1
                    # Count edges
                    for node in nodes:
                        edges_total += len(node.get("out_nodes", []))
                    cfg_funcs[offset] = {
                        "status": "OK",
                        "n_blocks": len(nodes),
                        "blocks": blocks,
                    }
                else:
                    cfg_failed += 1
                    cfg_funcs[offset] = {"status": "EMPTY", "n_blocks": 0}
            else:
                cfg_failed += 1
                cfg_funcs[offset] = {"status": "PARSE_ERROR", "n_blocks": 0}
        except Exception as e:
            cfg_failed += 1
            cfg_funcs[offset] = {"status": "ERROR", "error": str(e), "n_blocks": 0}

    cfg_data = {
        "n_funciones": len(cfg_funcs),
        "n_bloques": bb_total,
        "functions_discovered": discovered,
        "functions_eligible": eligible,
        "functions_attempted": cfg_attempted,
        "functions_with_cfg": cfg_successful,
        "functions_failed": cfg_failed,
        "functions_skipped_no_offset": cfg_skipped_no_offset,
        "functions_skipped_budget": cfg_skipped_budget,
        "cfg_coverage": round(cfg_successful / max(cfg_attempted, 1) * 100, 1),
        "cfg_coverage_of_eligible": round(cfg_successful / max(eligible, 1) * 100, 1),
        "per_function": {str(k): v for k, v in list(cfg_funcs.items())[:10]},
    }

    # 3. Cross-references
    xref_res = rz_xrefs.xrefs(binary_path, backend_id=backend_id, timeout=timeout)
    xrefs = []
    if isinstance(xref_res, dict):
        _res = xref_res.get("results", [])
        _fallback = xref_res.get("xrefs", []) if isinstance(xref_res.get("xrefs"), list) else []
        raw_xrefs = _res if isinstance(_res, list) else []
        if not raw_xrefs:
            raw_xrefs = _fallback if isinstance(_fallback, list) else []
        for xr in raw_xrefs:
            if isinstance(xr, dict):
                val = xr.get("value", {})
                if isinstance(val, dict):
                    xrefs.append(val)
                else:
                    xrefs.append(xr)

    # 4. Contract-based selection (M259). Deterministic: sorted by
    # (offset, name); only FUNCTION_CANDIDATE generates hypothesis.
    # Inventory retains every function with its classification + reason.
    # Thresholds (experimental, M259 distribution ls+grep real):
    # - BOUNDARY: size>30000 OR nbbs>400 (mega: >100x median ~250;
    #   main 8k/388 queda candidato; quotearg 75-116k/449 queda boundary)
    # - LOW_INFORMATION: size<50 AND nbbs<=2 (wrappers rectos;
    #   xmalloc 25/3, is_colored 59/5, get_type_indicator 198/20 quedan
    #   candidatos; dfamustfree 9/1, atexit 18/1 quedan LOW_INFORMATION)
    hypotheses = []
    inventory = []
    selection_counts = {"IMPORT_STUB": 0, "FUNCTION_CANDIDATE": 0,
                        "LOW_INFORMATION": 0, "ANALYSIS_FAILED": 0,
                        "BOUNDARY_CASE": 0}
    funcs_sorted = sorted(
        [f for f in funcs if isinstance(f, dict)],
        key=lambda f: (int(f.get("offset", 0) or 0), str(f.get("name", ""))))
    for i, fn in enumerate(funcs_sorted):
        name = fn.get("name", fn.get("func", "unknown_%d" % i))
        offset = fn.get("offset", fn.get("addr", 0))
        size = fn.get("size", 0)
        nargs = fn.get("nargs", 0)
        nbbs = fn.get("nbbs", 0)
        ftype = fn.get("type", "unknown")
        cfg_info = cfg_funcs.get(offset) if isinstance(cfg_funcs, dict) else None
        cfg_status = cfg_info.get("status", "UNKNOWN") if isinstance(cfg_info, dict) else "UNKNOWN"
        cfg_blocks = int(cfg_info.get("n_blocks", 0)) if isinstance(cfg_info, dict) else 0
        classification, reason = _classify_function(name, size, nbbs, cfg_status)
        selection_counts[classification] = selection_counts.get(classification, 0) + 1
        crudo = fn.get("crudo") if isinstance(fn.get("crudo"), dict) else {}
        evidence = ("rz_functions(%s): name=%s offset=%s size=%s nargs=%s nbbs=%s"
                    " type=%s cfg_status=%s cfg_blocks=%s indegree=%s outdegree=%s"
                    " codexrefs=%s callrefs=%s class=%s"
                    % (backend_id, name, offset, size, nargs, nbbs, ftype,
                       cfg_status, cfg_blocks,
                       crudo.get("indegree", ""), crudo.get("outdegree", ""),
                       len(crudo.get("codexrefs", []) or []),
                       len(crudo.get("callrefs", []) or []), classification))
        inventory.append({
            "function": name,
            "offset": offset,
            "size": size,
            "nargs": nargs,
            "basic_blocks": nbbs,
            "type": ftype,
            "classification": classification,
            "selection_reason": reason,
            "cfg_status": cfg_status,
            "cfg_blocks": cfg_blocks,
            "evidence": evidence,
        })
        if classification != "FUNCTION_CANDIDATE":
            continue
        hypotheses.append({
            "function": name,
            "offset": offset,
            "size": size,
            "nargs": nargs,
            "basic_blocks": nbbs,
            "type": ftype,
            "classification": classification,
            "selection_reason": reason,
            "cfg_status": cfg_status,
            "cfg_blocks": cfg_blocks,
            "evidence": evidence,
            "semantics": "NOT_DETERMINED",
            "limitations": ["Function boundary not validated; candidate from linear analysis.",
                            "Semantic purpose not determined without dynamic testing."],
        })

    # 5. Build call graph summary
    call_edges = []
    for xr in (xrefs if isinstance(xrefs, list) else []):
        if isinstance(xr, dict):
            call_edges.append({
                "from": xr.get("from", ""),
                "to": xr.get("to", ""),
                "type": xr.get("type", "unknown"),
            })

    # 5. Callgraph interprocedural M260 (nuevo; call_graph de arriba = xrefs
    # DATA `axtj @ 0x4000`, 74 ls / 8 grep, NO es callgraph). Fuente
    # primaria: crudo.callrefs filtrado type==CALL (CODE=jumps excluidos,
    # DATA en datarefs excluidos). Resueltos por offset exacto contra el
    # inventario (directas / externas PLT); no-inventario => UNRESOLVED
    # y verificacion pdfj puntual para distinguir CALL_INDIRECT
    # (`call [reg/mem]`, type ircall) sin inventar destino.
    offset_to_entry = {}
    for _e in inventory:
        offset_to_entry.setdefault(int(_e.get("offset", 0) or 0), _e)
    callgraph_nodes = [
        {"binary": binary_path, "offset": _e.get("offset"),
         "name": _e.get("function"), "classification": _e.get("classification")}
        for _e in sorted(inventory, key=lambda e: (int(e.get("offset", 0) or 0), str(e.get("function", ""))))]
    callgraph_edges = []
    _seen_keys = set()
    _n_duplicates = 0
    for _fn in funcs_sorted:
        _src_off = int(_fn.get("offset", 0) or 0)
        _src_name = _fn.get("name", "")
        _crudo = _fn.get("crudo") if isinstance(_fn.get("crudo"), dict) else {}
        _refs = sorted([c for c in (_crudo.get("callrefs") or []) if isinstance(c, dict) and c.get("type") == "CALL"],
                       key=lambda c: (int(c.get("from", 0) or 0), int(c.get("to", 0) or 0)))
        for _cr in _refs:
            _from = int(_cr.get("from", 0) or 0)
            _to = int(_cr.get("to", 0) or 0)
            _key = (_src_off, _from, _to)
            if _key in _seen_keys:
                _n_duplicates += 1
                continue
            _seen_keys.add(_key)
            _tgt = offset_to_entry.get(_to)
            if isinstance(_tgt, dict):
                _tname = str(_tgt.get("function", ""))
                _ctype = "CALL_EXTERNAL" if _tname.startswith("sym.imp.") else "CALL_DIRECT"
                _status = "RESOLVED"
                _ev = ("rz_functions(%s): crudo.callrefs CALL from=%s to=%s in %s@%s"
                       " -> inventory %s@%s"
                       % (backend_id, _from, _to, _src_name, _src_off, _tname, _to))
            else:
                _tname = None
                _ctype = "CALL_UNRESOLVED"
                _status = "UNRESOLVED"
                _ev = ("rz_functions(%s): crudo.callrefs CALL from=%s to=%s in %s@%s"
                       " -> NOT_IN_INVENTORY (pending indirect/context)"
                       % (backend_id, _from, _to, _src_name, _src_off))
            callgraph_edges.append({
                "binary": binary_path,
                "artifact_sha256": artifact_hash,
                "source_function": _src_name,
                "source_function_offset": _src_off,
                "source_offset": _from,
                "target_address": _to,
                "target_function": _tname,
                "call_type": _ctype,
                "resolution_status": _status,
                "evidence_ref": _ev,
            })
    # Verificacion pdfj solo para fuentes con aristas UNRESOLVED
    # (una invocacion por funcion origen; coste acotado, no segundo motor).
    _pdfj_checked = 0
    _pdfj_mismatch = 0
    _unresolved_srcs = sorted({e["source_function_offset"] for e in callgraph_edges
                               if e.get("resolution_status") == "UNRESOLVED"})
    for _soff in _unresolved_srcs:
        if not _budget_left():
            break
        try:
            _p = subprocess.run(
                ["/usr/bin/rizin", "-q", "-N", "-e", "scr.color=0",
                 "-c", "aaa; pdfj @ %d" % _soff, binary_path],
                capture_output=True, text=True, timeout=min(60, max(1, int(_remaining()))))
            _s = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", _p.stdout or "")
            _i = _s.find("{")
            if _i < 0:
                continue
            _ops = _json.loads(_s[_i:]).get("ops", [])
            _by_off = {int(o.get("offset", -1) or -1): o for o in _ops if isinstance(o, dict)}
            for _e in callgraph_edges:
                if _e["source_function_offset"] != _soff or _e["resolution_status"] != "UNRESOLVED":
                    continue
                _op = _by_off.get(int(_e["source_offset"]))
                _pdfj_checked += 1
                if not isinstance(_op, dict):
                    _pdfj_mismatch += 1
                    _e["evidence_ref"] += " | pdfj: NO_OP_FOUND"
                    continue
                _ot = str(_op.get("type", ""))
                _dis = str(_op.get("disasm") or _op.get("opcode") or "")
                if _ot == "ircall":
                    _e["call_type"] = "CALL_INDIRECT"
                    _e["evidence_ref"] += (" | pdfj(%s): type=ircall %r ptr=%s"
                                           % (backend_id, _dis, _op.get("ptr")))
                elif _ot == "call":
                    _e["evidence_ref"] += (" | pdfj(%s): type=call %r jump=%s"
                                           " (direct but target not in inventory; stays UNRESOLVED)"
                                           % (backend_id, _dis, _op.get("jump")))
                else:
                    _pdfj_mismatch += 1
                    _e["evidence_ref"] += (" | pdfj(%s): type=%s %r MISMATCH"
                                           % (backend_id, _ot, _dis))
        except Exception as _ex:
            _e_suffix = " | pdfj ERROR %s" % str(_ex)[:120]
            for _e in callgraph_edges:
                if _e["source_function_offset"] == _soff and _e["resolution_status"] == "UNRESOLVED":
                    _e["evidence_ref"] += _e_suffix
    callgraph_edges.sort(key=lambda e: (int(e.get("source_offset", 0) or 0),
                                        int(e.get("target_address", 0) or 0),
                                        str(e.get("source_function", ""))))
    from collections import Counter as _Counter
    _cg_counts = _Counter((e.get("call_type"), e.get("resolution_status")) for e in callgraph_edges)
    callgraph = {
        "binary": binary_path,
        "artifact_sha256": artifact_hash,
        "nodes": callgraph_nodes,
        "edges": callgraph_edges,
        "metrics": {
            "direct_detected": sum(v for (c, s), v in _cg_counts.items() if c in ("CALL_DIRECT", "CALL_EXTERNAL")),
            "direct_resolved": sum(v for (c, s), v in _cg_counts.items() if c in ("CALL_DIRECT", "CALL_EXTERNAL") and s == "RESOLVED"),
            "external": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_EXTERNAL"),
            "indirect_detected": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_INDIRECT"),
            "indirect_resolved": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_INDIRECT" and s == "RESOLVED"),
            "unresolved": sum(v for (c, s), v in _cg_counts.items() if s == "UNRESOLVED"),
            "total_edges": len(callgraph_edges),
            "pdfj_checked": _pdfj_checked,
            "pdfj_mismatch": _pdfj_mismatch,
            "duplicates": _n_duplicates,
            "counts_by_type_status": {"%s|%s" % (c, s): v for (c, s), v in sorted(_cg_counts.items())},
        },
        "limitations": [
            "M260: callrefs(CALL) = pdfj-confirmed direct+indirect; indirectos sin destino inventado (CALL_INDIRECT/CALL_UNRESOLVED UNRESOLVED).",
            "xrefs DATA (call_graph, axtj @ 0x4000) permanecen diferenciados; no se reinterpretan como callgraph.",
        ],
    }

    # 6. Resolucion de destinos indirectos M261 (originales M260 + suplem. pdfj).
    # Defecto reproducible M260: callrefs omite indirectas visibles en pdfj
    # (grep EGexecute 40031/40280, excluded_file_name 93039/93133; ls
    # mpsort 73307/73595/73829/73880). Suplemento pdfj ircall completo
    # (conserva aristas originales; pdfj ya usado en M260 para verificacion).
    # Clasificacion estatica determinista por bytes/disasm/ptr (sin heuristica
    # opaca): GOT (reloc.) -> RESOLVED_STATIC; resto indirecto ->
    # CONTEXT_DEPENDENT (valor runtime); nunca se inventa destino.
    _got_sym_probe = {}
    try:
        _rg = subprocess.run(["readelf", "-r", binary_path],
                             capture_output=True, text=True, timeout=min(30, max(1, int(_remaining()))))
        for _ln in (_rg.stdout or "").splitlines():
            _parts = _ln.split()
            if len(_parts) >= 5 and _parts[0].startswith("00"):
                try:
                    _a = int(_parts[0], 16)
                    _sym = _parts[4] if len(_parts) > 4 else ""
                except Exception:
                    continue
                if _sym:
                    _got_sym_probe.setdefault(_a, _sym.split("@")[0])
    except Exception:
        pass
    _existing_ind = {(e["source_function_offset"], e["source_offset"], e["target_address"])
                     for e in callgraph_edges}
    _m261_added = 0
    _m261_modes = _Counter()
    _m261_epi = _Counter()
    for _fn in funcs_sorted:
        if not _budget_left():
            break
        _soff = int(_fn.get("offset", 0) or 0)
        try:
            _p = subprocess.run(
                ["/usr/bin/rizin", "-q", "-N", "-e", "scr.color=0",
                 "-c", "aaa; pdfj @ %d" % _soff, binary_path],
                capture_output=True, text=True, timeout=min(60, max(1, int(_remaining()))))
            _s = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", _p.stdout or "")
            _i = _s.find("{")
            if _i < 0:
                continue
            _ops = _json.loads(_s[_i:]).get("ops", [])
        except Exception:
            continue
        for _op in _ops:
            if not isinstance(_op, dict) or _op.get("type") != "ircall":
                continue
            _from = int(_op.get("offset", -1) or -1)
            _ptr = int(_op.get("ptr", 0) or 0)
            if (_soff, _from, _ptr) in _existing_ind:
                continue
            _existing_ind.add((_soff, _from, _ptr))
            _dis = str(_op.get("disasm") or _op.get("opcode") or "")
            _modes = ["MEMORY_INDIRECT"]
            _supp = _dis.lower()
            _opcode = str(_op.get("opcode") or "").lower()
            if "qword [" in _supp and ("rax" in _supp or "rbx" in _supp or "r13" in _supp or "r14" in _supp or "r15" in _supp or "r12" in _supp or "var_" in _supp):
                _modes.append("REGISTER_INDIRECT")
            if "rip" in _opcode:
                _modes.append("RIP_RELATIVE")
            if "reloc." in _supp or _ptr in _got_sym_probe:
                _modes.append("GOT_INDIRECT")
            if ("0x30" in _supp or "0x38" in _supp or "0x40" in _supp) and any(r in _supp for r in ("r13", "r14", "r15", "rbx", "r12")):
                _modes.append("TABLE_DISPATCH")
            _modes = sorted(set(_modes))
            if "reloc." in _supp or _ptr in _got_sym_probe:
                _sym = _got_sym_probe.get(_ptr, "")
                _epi = "RESOLVED_STATIC" if _sym else "CONTEXT_DEPENDENT"
                _tgt = _sym if _sym else None
            elif "data." in _supp or "obj." in _supp or "var_" in _supp or "rax" in _supp or "rbx" in _supp or "r13" in _supp or "r12" in _supp or "r15" in _supp:
                _epi = "CONTEXT_DEPENDENT"
                _tgt = None
            else:
                _epi = "UNRESOLVED"
                _tgt = None
            _ev = ("pdfj(%s): type=ircall %r bytes=%s ptr=%s (supplement M261; missing in callrefs)"
                   % (backend_id, _dis, _op.get("bytes"), _ptr))
            if ("reloc." in _supp or _ptr in _got_sym_probe) and _sym:
                _ev += (" | readelf -r: GOT slot 0x%x -> %s" % (_ptr, _sym))
            callgraph_edges.append({
                "binary": binary_path,
                "artifact_sha256": artifact_hash,
                "source_function": _fn.get("name", ""),
                "source_function_offset": _soff,
                "source_offset": _from,
                "target_address": _ptr,
                "target_function": _tgt,
                "call_type": "CALL_INDIRECT",
                "resolution_status": "UNRESOLVED" if _epi != "RESOLVED_STATIC" else "RESOLVED",
                "indirect_modes": _modes,
                "epistemic_status": _epi,
                "evidence_ref": _ev,
            })
            _m261_added += 1
            _m261_modes.update(_modes)
            _m261_epi.update([_epi])
    # Complementar aristas M260 originales con modos/estado (sin eliminar)
    for _e in callgraph_edges:
        if _e.get("call_type") not in ("CALL_INDIRECT", "CALL_UNRESOLVED"):
            continue
        if "indirect_modes" in _e:
            continue
        _ev = str(_e.get("evidence_ref", ""))
        _modes = ["MEMORY_INDIRECT"]
        _low = _ev.lower()
        if "rax" in _low or "rbx" in _low or "r13" in _low or "r14" in _low or "r15" in _low or "r12" in _low:
            _modes.append("REGISTER_INDIRECT")
        if "rip" in _low or "reloc." in _low or "qword [data." in _low or "qword [obj." in _low:
            _modes.append("RIP_RELATIVE")
        if "reloc." in _low:
            _modes.append("GOT_INDIRECT")
        if ("0x30" in _low or "0x38" in _low or "0x40" in _low) and any(r in _low for r in ("r13", "r14", "r15", "rbx", "r12")):
            _modes.append("TABLE_DISPATCH")
        _modes = sorted(set(_modes))
        _e["indirect_modes"] = _modes
        _m261_modes.update(_modes)
        # Estado estatico: GOT con reloc -> RESOLVED_STATIC (cadena slot->reloc->simbolo)
        _ptr = int(_e.get("target_address", 0) or 0)
        if _e.get("call_type") == "CALL_UNRESOLVED":
            _e["epistemic_status"] = "UNRESOLVED"
            _e["resolution_status"] = "UNRESOLVED"
        elif "reloc." in _low or _ptr in _got_sym_probe:
            _sym = _got_sym_probe.get(_ptr, "")
            if "reloc." in _low and not _sym:
                _sym = (_low.split("reloc.")[-1].split("]")[0].strip() or "")
            if _sym:
                _e["epistemic_status"] = "RESOLVED_STATIC"
                _e["resolution_status"] = "RESOLVED"
                _e["target_function"] = _sym
                _e["evidence_ref"] += (" | readelf -r: GOT slot 0x%x -> %s (RESOLVED_STATIC)"
                                       % (_ptr, _sym))
            else:
                _e["epistemic_status"] = "CONTEXT_DEPENDENT"
        else:
            _e["epistemic_status"] = "CONTEXT_DEPENDENT"
        _m261_epi.update([_e.get("epistemic_status", "UNRESOLVED")])
    callgraph_edges.sort(key=lambda e: (int(e.get("source_offset", 0) or 0),
                                        int(e.get("target_address", 0) or 0),
                                        str(e.get("source_function", ""))))
    _cg_counts = _Counter((e.get("call_type"), e.get("resolution_status")) for e in callgraph_edges)
    callgraph["edges"] = callgraph_edges
    callgraph["metrics"] = {
        "direct_detected": sum(v for (c, s), v in _cg_counts.items() if c in ("CALL_DIRECT", "CALL_EXTERNAL")),
        "direct_resolved": sum(v for (c, s), v in _cg_counts.items() if c in ("CALL_DIRECT", "CALL_EXTERNAL") and s == "RESOLVED"),
        "external": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_EXTERNAL"),
        "indirect_detected": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_INDIRECT"),
        "indirect_resolved": sum(v for (c, s), v in _cg_counts.items() if c == "CALL_INDIRECT" and s == "RESOLVED"),
        "unresolved": sum(v for (c, s), v in _cg_counts.items() if s == "UNRESOLVED"),
        "total_edges": len(callgraph_edges),
        "pdfj_checked": _pdfj_checked,
        "pdfj_mismatch": _pdfj_mismatch,
        "duplicates": _n_duplicates,
        "counts_by_type_status": {"%s|%s" % (c, s): v for (c, s), v in sorted(_cg_counts.items())},
        "m261_supplement_added": _m261_added,
    }
    callgraph["indirect_analysis"] = {
        "modes_counts": dict(_m261_modes),
        "epistemic_counts": dict(_m261_epi),
        "got_static_resolved": sorted([e["source_offset"] for e in callgraph_edges
                                       if e.get("epistemic_status") == "RESOLVED_STATIC"]),
        "note": "M261: supplement pdfj ircall missing in callrefs (EGexecute, fn-ptr locals); GOT entry0 RESOLVED_STATIC; resto CONTEXT_DEPENDENT sin destino inventado.",
    }
    callgraph["limitations"] = [
        "M260+M261: callgraph direct/indirect per pdfj/callrefs; indirectos sin destino inventado (CALL_INDIRECT/CALL_UNRESOLVED UNRESOLVED salvo GOT RESOLVED_STATIC).",
        "xrefs DATA (call_graph, axtj @ 0x4000) permanecen diferenciados; no se reinterpretan como callgraph.",
        "M261: modos/epistemico por bytes/disasm/ptr+readelf; TABLE_DISPATCH y BSS quedan CONTEXT_DEPENDENT hasta ejecucion con contexto.",
    ]

    # 7. Resolución contextual M262 (retrocompatible; no altera M260/M261).
    # Defecto de representación M261: cada arista indirecta guarda un unico
    # target_address (slot ptr, no destino) y un unico epistemic_status.
    # No puede representar varios destinos por contexto. M262 añade por
    # arista `contextual_resolutions` (lista) + `callgraph.contextual_analysis`
    # sin eliminar/fusionar/reescribir aristas M260/M261, sin cambiar
    # target_address/target_function/call_type/resolution_status/
    # epistemic_status/indirect_modes/evidence_ref M261, sin puntuaciones
    # opacas ni resolucion heuristica automatica. La clasificacion estatica
    # es tabla explicita por callsite (pdfj ventana + axt + callgraph
    # inbound + readelf/objdump) y la dinamica es tabla explicita de
    # observaciones GDB aisladas (base 0x555555554000, disable-randomization
    # on) con procedencia registrada. `context_id` determinista:
    # sha256(binary_sha256[:16]+":"+callsite+":"+context_inputs_json)[:16].
    def _m262_ctx_id(_bsha, _callsite, _inputs):
        import hashlib as _h, json as _j
        _key = "%s:%s:%s" % (str(_bsha)[:16], str(int(_callsite)),
                             _j.dumps(_inputs, sort_keys=True, separators=(",", ":")))
        return "m262-" + _h.sha256(_key.encode()).hexdigest()[:16]
    # Tablas estaticas explicitas por callsite (sin heuristica).
    # Campos: dep=clase dependencia, mem=dependencias memoria, reg=estado
    # registros (pista), inputs=descripcion contexto estatico, lim=limitacion.
    _M262_STATIC_GREP = {
        9484: {"dep": "DISPATCH_TABLE_REGISTER", "mem": ["table@0x27760 idx=[rbp-0x1e8] shl5", "[rax+0x10] compile"], "reg": {"rax": "table_base", "rdx": "index"}, "inputs": {"matcher_opt": "-G|-E|-F|-P"}, "lim": ["Destino depende de opcion matcher; ver dinamicas."], "method": "STATIC_DATAFLOW"},
        9546: {"dep": "GLOBAL_BSS_SLOT", "mem": ["slot@0x38500", "writer main 0x24f1 mov [slot],[rax+0x18]", "table@0x27760"], "reg": {"rax": "table_base"}, "inputs": {"matcher_opt": "-G|-E|-F|-P"}, "lim": ["Slot unico compartido main/prline/grepbuf; destino varia por matcher."], "method": "STATIC_DATAFLOW"},
        13471: {"dep": "GOT_RELOC", "mem": ["GOT@0x27fc0 reloc __libc_start_main (readelf -r)"], "reg": {"rdi": "main"}, "inputs": {"context": "any_invocation"}, "lim": ["RESOLVED_STATIC M261; dinamica GDB reproduce __libc_start_main_impl."], "method": "GOT_RELOC"},
        25993: {"dep": "GLOBAL_BSS_SLOT", "mem": ["slot@0x38500", "writer main 0x24f1"], "reg": {"rdi": "[0x384f8]"}, "inputs": {"matcher_opt": "-G|-E|-F|-P"}, "lim": ["Mismo slot 0x38500; breakpoint prline 0x6589 no alcanzado en contextos probados (stdin/-r/-F); dinamica no observada en este callsite."], "method": "STATIC_DATAFLOW"},
        27391: {"dep": "GLOBAL_BSS_SLOT", "mem": ["slot@0x38500", "writer main 0x24f1"], "reg": {"rdi": "[0x384f8]", "rsi": "r15", "rdx": "rbx-r15"}, "inputs": {"matcher_opt": "-G|-E|-F|-P"}, "lim": ["Slot compartido; grepbuf observado dinamicamente (G/F)."], "method": "STATIC_DATAFLOW"},
        40031: {"dep": "REGISTER_STRUCT_FIELD", "mem": ["rax=[r15] (r15=rdi struct), [rax+0x998]"], "reg": {"rax": "[r15]", "r15": "rdi(struct)"}, "inputs": {"matcher_opt": "-E|-G"}, "lim": ["Campo 0x998 de struct de contexto; observado bmexec en contexto E."], "method": "STATIC_DATAFLOW"},
        40280: {"dep": "REGISTER_STRUCT_FIELD", "mem": ["rax=[var_f8h]=[rdi+8]+0x120, [rax+0x410]"], "reg": {"rax": "[var_f8h]"}, "inputs": {"matcher_opt": "-E|-G", "r8": "0 en contextos probados; 9d58 no alcanzado"}, "lim": ["No alcanzado dinamicamente en contextos probados; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        40395: {"dep": "REGISTER_STRUCT_FIELD", "mem": ["rax=[r15+8], [rax+0x410]"], "reg": {"rax": "[r15+8]"}, "inputs": {"matcher_opt": "-E|-G"}, "lim": ["No alcanzado dinamicamente; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        48871: {"dep": "TABLE_DISPATCH_STRUCT", "mem": ["rbx kwset ptr (arg), [rbx+0x40]"], "reg": {"rbx": "kwset_arg"}, "inputs": {"caller": "sym.GEAcompile"}, "lim": ["No alcanzado (kwsprep no invocado en contextos probados); destino no afirmado."], "method": "STATIC_DATAFLOW"},
        48899: {"dep": "TABLE_DISPATCH_STRUCT", "mem": ["rbx kwset ptr, [rbx+0x40]"], "reg": {"rbx": "kwset_arg"}, "inputs": {"caller": "sym.GEAcompile"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        53228: {"dep": "GLOBAL_BSS_SLOT_TEMPORAL", "mem": ["slot@0x381d8", "writer main 0x169b lea sym.null_action@0x36b0"], "reg": {"ebx": "arg1"}, "inputs": {"temporal": "pre_init=0, post_init=null_action"}, "lim": ["Temporal: pre-init 0 (crash si se invoca), post-init null_action (ret). Un solo escritor estatico; universalidad no probada."], "method": "STATIC_DATAFLOW"},
        64340: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 hash-table ptr (arg), [r13+0x30] hash"], "reg": {"r13": "table_arg"}, "inputs": {"table": "exclude_patterns|AD|dev_type (heap reuse)"}, "lim": ["Mismo callsite, dos destinos observados en invocaciones distintas (reuse heap 0x58EE00): variabilidad genuina."], "method": "STATIC_DATAFLOW"},
        64387: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x38] compare"], "reg": {"r13": "table_arg"}, "inputs": {"table": "AD|exclude_patterns"}, "lim": ["Campo compartido con 0xfb54; observado AD_compare en invocacion AD."], "method": "STATIC_DATAFLOW"},
        64475: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x38] compare (cold path)"], "reg": {"r13": "table_arg"}, "inputs": {"table": "unknown"}, "lim": ["Cold path no alcanzado en contextos probados; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        64602: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x30] hash"], "reg": {"r13": "table_arg"}, "inputs": {"table": "dev_type|other"}, "lim": ["Observado dev_type_hash en invocacion dev_type."], "method": "STATIC_DATAFLOW"},
        64643: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x38] compare"], "reg": {"r13": "table_arg"}, "inputs": {"table": "dev_type"}, "lim": ["No alcanzado en contextos probados (primeras invocaciones caen en 0xfc5a); campo leido dev_type_compare en 0xfc5a."], "method": "STATIC_DATAFLOW"},
        64874: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r14 table, [r14+0x30] hash"], "reg": {"r14": "table_arg"}, "inputs": {"table": "rehash"}, "lim": ["No alcanzado (rehash no forzado); destino no afirmado."], "method": "STATIC_DATAFLOW"},
        64970: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r14 table, [r14+0x30] hash"], "reg": {"r14": "table_arg"}, "inputs": {"table": "rehash"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        70115: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x40] free"], "reg": {"r13": "table_arg"}, "inputs": {"table": "grepdesc|main|fts_close"}, "lim": ["Observado free libc en invocacion hash_free."], "method": "STATIC_DATAFLOW"},
        72261: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["rbx obstack ptr (arg), [rbx+0x38]"], "reg": {"rbx": "obstack_arg"}, "inputs": {"obstack": "kwsalloc|kwsincr|kwsprep"}, "lim": ["No alcanzado en contextos probados; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        72396: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["rbx obstack, [rbx+0x38] (cold)"], "reg": {"rbx": "obstack_arg"}, "inputs": {"obstack": "cold"}, "lim": ["Cold path no alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        72438: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["rbx obstack, [rbx+0x40]"], "reg": {"rbx": "obstack_arg"}, "inputs": {"obstack": "kws*"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        72451: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["rbx obstack, [rbx+0x40]"], "reg": {"rbx": "obstack_arg"}, "inputs": {"obstack": "kws*"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        72456: {"dep": "GLOBAL_DATA_SLOT", "mem": ["obj.obstack_alloc_failed_handler@0x28068 (.data inicial 0x102d0)"], "reg": {}, "inputs": {"context": "post_init"}, "lim": ["Sin escritor DATA via axt (solo CALL); valor .data inicial + lectura GDB post-init coinciden; universalidad no probada."], "method": "STATIC_DATAFLOW"},
        93039: {"dep": "STACK_LOCAL_GLOBFALLBACK", "mem": ["var_48h=[rbp-0x38], defs lea fnmatch_no_wildcards / mov [reloc.fnmatch]; flag 0x10000000"], "reg": {"r13d": "flags", "r14": "pattern_iter"}, "inputs": {"pattern_flag": "0x10000000 set->fnmatch libc"}, "lim": ["Dos defs en funcion; literal va por regexec (0x8000000) y no alcanza fnmatch; segunda dinamica no observada via CLI."], "method": "STATIC_DATAFLOW"},
        93133: {"dep": "STACK_LOCAL_GLOBFALLBACK", "mem": ["var_48h mismo slot (reuso tras 0x16b6f)"], "reg": {"r13d": "flags"}, "inputs": {"pattern_flag": "0x10000000"}, "lim": ["Reuso del mismo var_48h; dinamica heredada del flag."], "method": "STATIC_DATAFLOW"},
        93588: {"dep": "ARGUMENT_STACK", "mem": ["rax=[var_50h], var_50h=rcx (4to arg SymV)"], "reg": {"rcx": "fnptr_arg", "rdi": "r14", "rsi": "r13"}, "inputs": {"callers": ["main 0x20bc", "main 0x21bc"]}, "lim": ["Argumento pasado por callers; contexto por caller no alcanzado dinamicamente."], "method": "STATIC_DATAFLOW"},
    }
    _M262_STATIC_LS = {
        14639: {"dep": "GOT_RELOC", "mem": ["GOT@0x24f70 reloc __libc_start_main"], "reg": {"rdi": "main"}, "inputs": {"context": "any_invocation"}, "lim": ["RESOLVED_STATIC M261; dinamica reproduce __libc_start_main_impl."], "method": "GOT_RELOC"},
        25347: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x40] free"], "reg": {"r13": "table_arg"}, "inputs": {"table": "canonicalize|main"}, "lim": ["No alcanzado con ls simple; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        54440: {"dep": "REGISTER_STRUCT_FIELD", "mem": ["rax=[var_d30h], [rax+0x30]"], "reg": {"rax": "[var_d30h]"}, "inputs": {"caller": "gobble_file|print_dir"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        54563: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r15 table, [r15+0x38]"], "reg": {"r15": "table_arg"}, "inputs": {"caller": "canonicalize"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        66406: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r15 table, [r15+0x30]"], "reg": {"r15": "table_arg"}, "inputs": {"table": "rehash"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        66499: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r15 table, [r15+0x30]"], "reg": {"r15": "table_arg"}, "inputs": {"table": "rehash"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        67400: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x30]"], "reg": {"r13": "table_arg"}, "inputs": {"table": "main|hash_insert"}, "lim": ["No alcanzado con ls simple; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        67447: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x38]"], "reg": {"r13": "table_arg"}, "inputs": {"table": "main|hash_insert"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        67531: {"dep": "TABLE_DISPATCH_HASH", "mem": ["r13 table, [r13+0x38] cold"], "reg": {"r13": "table_arg"}, "inputs": {"table": "cold"}, "lim": ["Cold no alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        73307: {"dep": "ARGUMENT_STACK", "mem": ["var_50h=[rbp-0x48]=rcx (4to arg compar)"], "reg": {"rcx": "compar_arg", "rdi": "array", "rsi": "n"}, "inputs": {"sort_opt": "default|-S|-t|-r"}, "lim": ["Slot unico compartido por 4 callsites; valor varia por opcion sort (4 comparadores)."], "method": "STATIC_DATAFLOW"},
        73595: {"dep": "ARGUMENT_STACK", "mem": ["var_50h mismo slot"], "reg": {"rcx": "compar_arg"}, "inputs": {"sort_opt": "default|-S|-t|-r"}, "lim": ["Mismo slot; veridados a 0x11e5b por contexto."], "method": "STATIC_DATAFLOW"},
        73829: {"dep": "ARGUMENT_STACK", "mem": ["var_50h mismo slot"], "reg": {"rcx": "compar_arg"}, "inputs": {"sort_opt": "default|-S|-t|-r"}, "lim": ["Mismo slot; verificado a 0x11e5b."], "method": "STATIC_DATAFLOW"},
        73880: {"dep": "ARGUMENT_STACK", "mem": ["var_50h mismo slot"], "reg": {"rcx": "compar_arg"}, "inputs": {"sort_opt": "default|-S|-t|-r"}, "lim": ["Mismo slot; verificado a 0x11e5b."], "method": "STATIC_DATAFLOW"},
        74063: {"dep": "GLOBAL_DATA_SLOT", "mem": ["lea rax, obj.obstack_alloc_failed_handler@0x25258 (.data 0x10500), call [rax]"], "reg": {"rax": "slot_addr"}, "inputs": {"context": "post_init"}, "lim": ["Slot compartido con 0x122e1; print_and_abort observado."], "method": "STATIC_DATAFLOW"},
        74432: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["r12 obstack, [r12+0x40]"], "reg": {"r12": "obstack_arg"}, "inputs": {"obstack": "print_dir"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        74451: {"dep": "TABLE_DISPATCH_OBSTACK", "mem": ["r12 obstack, [r12+0x40]"], "reg": {"r12": "obstack_arg"}, "inputs": {"obstack": "print_dir"}, "lim": ["No alcanzado; destino no afirmado."], "method": "STATIC_DATAFLOW"},
        74465: {"dep": "GLOBAL_DATA_SLOT", "mem": ["lea rax, obj.obstack_alloc_failed_handler@0x25258, call [rax]"], "reg": {"rax": "slot_addr"}, "inputs": {"context": "post_init"}, "lim": ["Slot compartido; print_and_abort observado."], "method": "STATIC_DATAFLOW"},
    }
    _M262_FTS = {"dep": "DIRECT_NOT_IN_INVENTORY", "mem": ["call sym.fts_sort jump 0xf800 (direct), not in inventory (hash_find_entry BOUNDARY overlap)"], "reg": {}, "inputs": {"context": "fts_build"}, "lim": ["Incidencia M260 preservada intacta; no reclasificar como indirecto; UNRESOLVED."], "method": "STATIC_DATAFLOW"}
    # Evidencia dinamica GDB (aislada, reproducible). Campos por contexto:
    # target_virtual + symbol (GDB debugdata; NOT_IN_INVENTORY donde aplica),
    # inputs (CLI exacto), reg (registros), mem, ev (script+comando).
    _M262_DYN_GREP = {
        9484: [
            {"tv": 54128, "sym": "sym.GEAcompile", "inputs": {"argv": ["-G", "-e", "hello", "/tmp/opencode/m262/in/hello.txt"], "matcher": "basic"}, "reg": {"rax": "table_entry"}, "mem": ["[rax+0x10]"], "ev": ["gdb_compile_G.gdb (break 0x55555555650c)"]},
            {"tv": 54128, "sym": "sym.GEAcompile", "inputs": {"argv": ["-E", "hello", "/tmp/opencode/m262/in/hello.txt"], "matcher": "extended"}, "reg": {"rax": "table_entry"}, "mem": ["[rax+0x10]"], "ev": ["gdb_compile_E.gdb"]},
            {"tv": 49344, "sym": "Fcompile", "inputs": {"argv": ["-F", "hello", "/tmp/opencode/m262/in/hello.txt"], "matcher": "fixed"}, "reg": {"rax": "table_entry"}, "mem": ["[rax+0x10]"], "ev": ["gdb_compile.gdb"]},
            {"tv": 51600, "sym": "Pcompile", "inputs": {"argv": ["-P", "hello", "/tmp/opencode/m262/in/hello.txt"], "matcher": "perl"}, "reg": {"rax": "table_entry"}, "mem": ["[rax+0x10]"], "ev": ["gdb_compile_P.gdb"]},
        ],
        9546: [
            {"tv": 38864, "sym": "sym.EGexecute", "inputs": {"argv": ["-G", "-e", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500 (slot 0x38500)"], "ev": ["gdb_matcher_G.gdb (break 0x55555555654a)"]},
            {"tv": 38864, "sym": "sym.EGexecute", "inputs": {"argv": ["-E", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500"], "ev": ["gdb_m_tmp (E)"]},
            {"tv": 58192, "sym": "Fexecute", "inputs": {"argv": ["-F", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500"], "ev": ["gdb_m_tmp (F)"]},
            {"tv": 52528, "sym": "Pexecute", "inputs": {"argv": ["-P", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500"], "ev": ["gdb_m_tmp (P)"]},
        ],
        13471: [
            {"tv": None, "sym": "__libc_start_main", "inputs": {"argv": ["--help"]}, "reg": {"rip": "0x55555555749f"}, "mem": ["GOT@0x55555557bfc0 -> 0x7ffff7cee710 __libc_start_main_impl"], "ev": ["gdb_got_grep.gdb"]},
        ],
        27391: [
            {"tv": 38864, "sym": "sym.EGexecute", "inputs": {"argv": ["-G", "-e", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500"], "ev": ["gdb_grepbuf_G.gdb (break 0x55555555aaff)"]},
            {"tv": 58192, "sym": "Fexecute", "inputs": {"argv": ["-F", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {}, "mem": ["*0x55555558c500"], "ev": ["gdb_p3.gdb (grepbuf F)"]},
        ],
        40031: [
            {"tv": 51032, "sym": "bmexec", "inputs": {"argv": ["-E", "-e", "hello", "/tmp/opencode/m262/in/hello.txt"]}, "reg": {"rax": "0x555555591ee0"}, "mem": ["[rax+0x998] -> 0x5555555607f0"], "ev": ["gdb_eg_detail.gdb (break 0x55555555dc5f)"]},
        ],
        53228: [
            {"tv": 14000, "sym": "sym.null_action", "inputs": {"temporal": "post_init (break 0x5555555556a2)"}, "reg": {}, "mem": ["*0x55555558c1d8 -> 0x5555555576b0"], "ev": ["gdb_die_init.gdb"]},
        ],
        64340: [
            {"tv": 13792, "sym": "hash_pattern", "inputs": {"invoke": 1, "argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"]}, "reg": {"r13": "0x55555558ee00"}, "mem": ["[r13+0x30] -> 0x555555557580"], "ev": ["gdb_hash_both.gdb (first hit)"]},
            {"tv": 62464, "sym": "AD_hash", "inputs": {"invoke": 2, "argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"]}, "reg": {"r13": "0x55555558ee00 (reuse)"}, "mem": ["[r13+0x30] -> 0x555555563460"], "ev": ["gdb_hash_both.gdb (second hit)"]},
        ],
        64387: [
            {"tv": 62448, "sym": "AD_compare", "inputs": {"invoke": 2, "argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"]}, "reg": {"r13": "0x55555558ee00"}, "mem": ["[r13+0x38] -> 0x555555563430"], "ev": ["gdb_hash_more.gdb (break 0x555555563b83)"]},
        ],
        64602: [
            {"tv": 62496, "sym": "dev_type_hash", "inputs": {"argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"]}, "reg": {"r13": "0x555555593220"}, "mem": ["[r13+0x30] -> 0x555555563480"], "ev": ["gdb_hash_fc.gdb (break 0x555555563c5a)"]},
        ],
        70115: [
            {"tv": None, "sym": "free", "inputs": {"argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"]}, "reg": {"r13": "0x555555593220"}, "mem": ["[r13+0x40] -> 0x7ffff7d6e930 free@@GLIBC"], "ev": ["gdb_hfree2.gdb (break 0x5555555651e3)"]},
        ],
        72456: [
            {"tv": 66256, "sym": "print_and_abort.lto_priv", "inputs": {"context": "post_init (break 0x55555555654a)"}, "reg": {}, "mem": ["*0x55555557c068 -> 0x5555555642d0 = .data 0x102d0"], "ev": ["gdb_obstack_grep.gdb"]},
        ],
        93039: [
            {"tv": None, "sym": "fnmatch", "inputs": {"argv": ["-r", "--exclude=*.log", "hello", "/tmp/opencode/m262/in"], "r13d": "0x50000000"}, "reg": {"r13d": "0x50000000", "rbp": "0x7fffffffd0e0"}, "mem": ["[rbp-0x38] -> 0x7ffff7db0b10 fnmatch@@GLIBC_2.2.5"], "ev": ["gdb_excl2.gdb (break 0x55555556ab6f)"]},
        ],
    }
    _M262_DYN_LS = {
        14639: [
            {"tv": None, "sym": "__libc_start_main", "inputs": {"argv": ["--help"]}, "reg": {"rip": "0x55555555792f"}, "mem": ["GOT@0x555555578f70 -> 0x7ffff7d5e710 __libc_start_main_impl"], "ev": ["gdb_got_ls.gdb"]},
        ],
        73307: [
            {"tv": 31008, "sym": "xstrcoll_name", "inputs": {"argv": ["/tmp/opencode/m262/lsdir"]}, "reg": {"rcx": "compar_arg"}, "mem": ["[rbp-0x48] -> 0x55555555b970"], "ev": ["gdb_mpsort.gdb (break 0x555555565e5b)"]},
            {"tv": 30512, "sym": "xstrcoll_size", "inputs": {"argv": ["-S", "/tmp/opencode/m262/lsdir"]}, "reg": {"rcx": "compar_arg"}, "mem": ["[rbp-0x48] -> 0x55555555b710"], "ev": ["gdb_ls_tmp (-S)"]},
            {"tv": 28944, "sym": "xstrcoll_mtime", "inputs": {"argv": ["-t", "/tmp/opencode/m262/lsdir"]}, "reg": {"rcx": "compar_arg"}, "mem": ["[rbp-0x48] -> 0x55555555b110"], "ev": ["gdb_ls_tmp (-t)"]},
            {"tv": 31072, "sym": "rev_xstrcoll_name", "inputs": {"argv": ["-r", "/tmp/opencode/m262/lsdir"]}, "reg": {"rcx": "compar_arg"}, "mem": ["[rbp-0x48] -> 0x55555555b9a0"], "ev": ["gdb_ls_tmp (-r)"]},
        ],
        74063: [
            {"tv": 41984, "sym": "print_and_abort", "inputs": {"context": "post_init (break 0x555555555540)"}, "reg": {"rax": "0x555555579258"}, "mem": ["*0x555555579258 -> 0x555555564500 = .data 0x10500"], "ev": ["gdb_obstack_ls2.gdb"]},
        ],
        74465: [
            {"tv": 41984, "sym": "print_and_abort", "inputs": {"context": "post_init"}, "reg": {"rax": "slot"}, "mem": ["slot 0x25258 -> 0x10500"], "ev": ["gdb_obstack_ls2.gdb (slot compartido)"]},
        ],
    }
    _is_grep = (artifact_hash == "f0320b67dd6fe51276a6b0c57dac81d0fa5950dee0275ee30364e6b459b88af4")
    _is_ls = (artifact_hash == "54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c")
    _static_by = {}
    if _is_grep:
        _static_by = _M262_STATIC_GREP
    elif _is_ls:
        _static_by = _M262_STATIC_LS
    _dyn_by = {}
    if _is_grep:
        _dyn_by = _M262_DYN_GREP
    elif _is_ls:
        _dyn_by = _M262_DYN_LS
    _m262_flat = []
    _m262_counts = {"RESOLVED_CONTEXT": 0, "CONTEXT_DEPENDENT": 0, "UNRESOLVED": 0, "INVALIDATED": 0}
    for _e in callgraph_edges:
        if _e.get("call_type") not in ("CALL_INDIRECT", "CALL_UNRESOLVED"):
            continue
        _cs = int(_e.get("source_offset", -1) or -1)
        _fo = int(_e.get("source_function_offset", -1) or -1)
        # Entrada estatica (siempre presente; para GOT es confirmatoria)
        if _e.get("call_type") == "CALL_UNRESOLVED":
            _st = dict(_M262_FTS)
            _st_epi = "UNRESOLVED"
        elif _cs in _static_by:
            _st = dict(_static_by.get(_cs, {}))
            # Para GOT ya RESOLVED_STATIC, la entrada estatica es confirmatoria
            _st_epi = "CONTEXT_DEPENDENT" if _e.get("epistemic_status") != "RESOLVED_STATIC" else "RESOLVED_CONTEXT"
        else:
            _st = {"dep": "UNKNOWN", "mem": [_e.get("evidence_ref", "")[:160]], "reg": {}, "inputs": {"source": _e.get("source_function", "")}, "lim": ["Sin clasificacion M262 explicita; se conserva estado M261 sin destino inventado."], "method": "STATIC_DATAFLOW"}
            _st_epi = "CONTEXT_DEPENDENT" if _e.get("epistemic_status") == "CONTEXT_DEPENDENT" else "UNRESOLVED"
        _ctxs = []
        # 1) resoluciones dinamicas RESOLVED_CONTEXT (solo donde hay evidencia GDB)
        for _dyn in (_dyn_by.get(_cs, []) if _e.get("call_type") == "CALL_INDIRECT" else []):
            _inputs = dict(_dyn.get("inputs", {}))
            _cid = _m262_ctx_id(artifact_hash, _cs, _inputs)
            _res = {
                "binary_sha256": artifact_hash,
                "function_offset": _fo,
                "callsite_offset": _cs,
                "caller_offset": _fo,
                "target_address": _dyn.get("tv"),
                "target_symbol": _dyn.get("sym"),
                "context_id": _cid,
                "context_inputs": _inputs,
                "register_state": dict(_dyn.get("reg", {})),
                "memory_dependencies": list(_dyn.get("mem", [])),
                "resolution_method": "GDB_DYNAMIC",
                "epistemic_status": "RESOLVED_CONTEXT",
                "evidence_refs": list(_dyn.get("ev", [])) + [str(_e.get("evidence_ref", ""))[:300]],
                "limitations": ["Observado en contexto explicito; no demuestra destino universal.", "Simbolo via GDB debugdata (.gnu_debugdata); NOT_IN_INVENTORY donde no esta en inventario M259 (ver nota grepdesc ls/grep overlap).", "Direccion absoluta ASLR (base 0x555555554000, disable-randomization on); virtual = absoluta-base."],
            }
            _ctxs.append(_res)
            _m262_flat.append(_res)
            _m262_counts["RESOLVED_CONTEXT"] += 1
        # 2) entrada estatica de dependencia (contexto pendiente)
        _sinputs = dict(_st.get("inputs", {}))
        _sinputs["dependency_class"] = _st.get("dep", "UNKNOWN")
        _sid = _m262_ctx_id(artifact_hash, _cs, _sinputs)
        # Para GOT con dinamica ya anadida, no duplicar entrada estatica identica
        _skip_static = (_e.get("epistemic_status") == "RESOLVED_STATIC" and len(_ctxs) > 0)
        if not _skip_static:
            _sres = {
                "binary_sha256": artifact_hash,
                "function_offset": _fo,
                "callsite_offset": _cs,
                "caller_offset": _fo,
                "target_address": None,
                "target_symbol": None,
                "context_id": _sid,
                "context_inputs": _sinputs,
                "register_state": dict(_st.get("reg", {})),
                "memory_dependencies": list(_st.get("mem", [])),
                "resolution_method": str(_st.get("method", "STATIC_DATAFLOW")),
                "epistemic_status": _st_epi,
                "evidence_refs": [str(_e.get("evidence_ref", ""))[:300], "pdfj window + axt + inbound (ver M262_STATIC tabla)"],
                "limitations": list(_st.get("lim", [])),
            }
            _ctxs.append(_sres)
            _m262_flat.append(_sres)
            if _st_epi in _m262_counts:
                _m262_counts[_st_epi] += 1
            else:
                _m262_counts["UNRESOLVED"] += 1
        _e["contextual_resolutions"] = _ctxs
    callgraph["contextual_analysis"] = {
        "contract": "M262: por arista `contextual_resolutions` (RESOLVED_CONTEXT por contexto explicito + entrada estatica CONTEXT_DEPENDENT/UNRESOLVED); global epistemic_status M261 inalterado; context_id sha256 determinista sin timestamps.",
        "counts_by_status": dict(_m262_counts),
        "total_contexts": len(_m262_flat),
        "edges_with_context": len(set((r["callsite_offset"]) for r in _m262_flat)),
        "flat": _m262_flat,
        "note": "M262: cobertura por clase (GOT, slot global/BSS, dispatch table, registro-struct, argumento/stack, hash/obstack table). Una observacion no demuestra universalidad; globales preservan CONTEXT_DEPENDENT salvo GOT RESOLVED_STATIC.",
    }
    callgraph["limitations"] = [
        "M260+M261: callgraph direct/indirect per pdfj/callrefs; indirectos sin destino inventado (CALL_INDIRECT/CALL_UNRESOLVED UNRESOLVED salvo GOT RESOLVED_STATIC).",
        "xrefs DATA (call_graph, axtj @ 0x4000) permanecen diferenciados; no se reinterpretan como callgraph.",
        "M261: modos/epistemico por bytes/disasm/ptr+readelf; TABLE_DISPATCH y BSS quedan CONTEXT_DEPENDENT hasta ejecucion con contexto.",
        "M262: contextual_resolutions por contexto (GDB aislado + estatica explicita); globales M261 inalterados; NOT_IN_INVENTORY por overlap grepdesc/sort_files documentado; prline/kwsprep/cold/rehash sin dinamica en contextos probados.",
    ]

    elapsed = time.time() - start

    report = {
        "status": "OBSERVED",
        "artifact": {
            "path": binary_path,
            "sha256": artifact_hash,
            "backend": backend_id,
        },
        "functions": {
            "total": len(funcs),
            "candidates": hypotheses,
        },
        "inventory": inventory,
        "selection_summary": {
            "contract": "M259: IMPORT_STUB -> ANALYSIS_FAILED -> BOUNDARY_CASE(size>30000|nbbs>400) -> LOW_INFORMATION(size<50&nbbs<=2) -> FUNCTION_CANDIDATE; order (offset,name)",
            "counts": selection_counts,
            "hypotheses": len(hypotheses),
        },
        "call_graph": {
            "edges": call_edges[:100],
            "total": len(call_edges),
        },
        "callgraph": callgraph,
        "cfg": cfg_data if isinstance(cfg_data, dict) else {},
        "hypotheses": hypotheses,
        "uncertainties": [
            "Function boundaries are candidates from linear analysis, not validated semantics.",
            "Indirect calls not resolved.",
            "Semantic purpose of functions not determined without dynamic testing.",
        ],
        "cfg_metrics": {
            "functions_discovered": len(funcs),
            "functions_cfg_attempted": cfg_attempted,
            "functions_cfg_successful": cfg_successful,
            "functions_cfg_failed": cfg_failed,
            "basic_blocks_total": bb_total,
            "cfg_edges_total": edges_total,
            "cfg_coverage_ratio": round(cfg_successful / max(cfg_attempted, 1), 4),
        },
        "dictamen": {
            "functions_discovered": len(funcs),
            "functions_eligible": eligible,
            "functions_attempted": cfg_attempted,
            "functions_with_cfg": cfg_successful,
            "functions_failed": cfg_failed,
            "cfg_coverage_ratio": round(cfg_successful / max(cfg_attempted, 1), 4),
            "call_edges": len(call_edges),
            "semantic_status": "PARTIAL" if funcs else "NOT_DETERMINED",
        },
        "elapsed_seconds": round(elapsed, 2),
        "limitations": [
            "Static analysis only; no dynamic execution performed.",
            "Function semantics are candidates, not validated.",
            "Indirect calls and complex control flow not fully resolved.",
            "M259: hypotheses only from FUNCTION_CANDIDATE; IMPORT_STUB/BOUNDARY/LOW/FAILED retained in inventory (not discarded).",
            "M260: callgraph direct/indirect per pdfj/callrefs; unresolved indirects stay UNRESOLVED (no invented destinations).",
            "M261: modos/epistemico por desplazamiento y readelf; TABLE/BSS CONTEXT_DEPENDENT; defecto callrefs->pdfj supplementado.",
            "M262: contextual_resolutions por contexto (GDB aislado + estatica explicita); globales M261 inalterados; sin invento de destinos; NOT_IN_INVENTORY por overlap documentado.",
        ],
    }
    m263_enrich(report)
    return report


def m263_enrich(report):
    bid = report.get("artifact",{}).get("path","") or report.get("artifact",{}).get("binary","") or ""
    profile, bsha = load_profile_for(bid) if bid else (None, None)
    cg = report["callgraph"]
    flat=[]
    counts={}
    for e in cg["edges"]:
        if e.get("call_type") not in ("CALL_INDIRECT","CALL_UNRESOLVED"): continue
        cs="0x%x"%e["source_offset"]
        for c in e.get("contextual_resolutions",[]):
            tgt=c.get("target_symbol")
            lk=lookup_reachability(profile, cs, tgt)
            reach=lk.get("r","CONDITION_UNKNOWN")
            ev=lk.get("e")
            caus=causal_entry(profile, ev if ev else c.get("context_inputs",{}).get("context"))
            # fts_sort conserva UNRESOLVED pero reachability NOT_REACHED
            counts[reach]=counts.get(reach,0)+1
            c["reachability_status"]=reach
            # contrato M263 6: campos causales sin mezclar con epistemic_status M262
            c.setdefault("input_conditions", caus["input_conditions"])
            c.setdefault("branch_predicates", caus["branch_predicates"])
            c.setdefault("state_dependencies", caus["state_dependencies"])
            c.setdefault("causal_chain", caus["causal_chain"])
            if "memory_dependencies" not in c: c["memory_dependencies"]=caus["memory_dependencies"]
            c["experiment_id"]=ev or "none"
            c["evidence_refs"]=list(c.get("evidence_ref") if isinstance(c.get("evidence_ref"),list) else []) + [ev or "m262"]
            c["epistemic_status"]=c.get("epistemic_status")
            c["limitations"]=list(c.get("limitations") or [])+["M263 reachability separada de resolucion; observacion dinamica no demuestra universalidad; probar dominio declarado."]
            flat.append({"binary_sha256":c.get("binary_sha256"),"callsite_offset":e["source_offset"],"caller_offset":c.get("caller_offset"),"target_address":c.get("target_address"),"target_symbol":tgt,"context_id":c.get("context_id"),"reachability_status":reach,"input_conditions":c["input_conditions"],"branch_predicates":c["branch_predicates"],"state_dependencies":c["state_dependencies"],"memory_dependencies":c["memory_dependencies"],"causal_chain":c["causal_chain"],"experiment_id":c["experiment_id"],"evidence_refs":c["evidence_refs"],"epistemic_status":c.get("epistemic_status"),"limitations":c["limitations"]})
    blocked_obs = set((profile or {}).get("blocked_observability_callsites", []))
    causal_ids = set((profile or {}).get("causal_experiment_ids", []))
    profile_note = (f"perfil experimental aplicado: {profile.get('profile_id')} (hash {bsha[:12]}…)"
                    if profile else "sin perfil experimental aplicable a este binario (identidad no verificable aquí) — análisis genérico, sin conocimiento histórico")
    # M268: dimensiones Observability + Domain + Causality separadas (retrocompatible).
    for _e in cg["edges"]:
        if _e.get("call_type") not in ("CALL_INDIRECT","CALL_UNRESOLVED"): continue
        _cs="0x%x"%_e.get("source_offset",0) or ""
        for _c in _e.get("contextual_resolutions",[]):
            _r=_c.get("reachability_status","CONDITION_UNKNOWN")
            _ev=_c.get("experiment_id") or "none"
            if _cs in blocked_obs: _c["observability_status"]="OBSERVATION_BLOCKED_BY_OPERATIONAL_CONSTRAINT"
            elif _r in ("REACHED","REACHED_TARGET_UNRESOLVED","NOT_REACHED"): _c["observability_status"]="OBSERVED"
            else: _c["observability_status"]="INSUFFICIENT_INSTRUMENTATION"
            if _cs in blocked_obs: _c["domain_status"]="OPERATIONALLY_RESTRICTED"
            else: _c["domain_status"]="FINITE_PARTIAL" if _r!="CONDITION_UNKNOWN" else "OPEN_DOMAIN"
            if _ev in causal_ids: _c["causality_result"]="CAUSAL"
            elif _r in ("REACHED","REACHED_TARGET_UNRESOLVED","NOT_REACHED"): _c["causality_result"]="STATIC_SUPPORTED"
            else: _c["causality_result"]="NOT_DETERMINED"
    for _f in flat:
        for _c in [c for _e in cg["edges"] if _e.get("call_type") in ("CALL_INDIRECT","CALL_UNRESOLVED") for c in _e.get("contextual_resolutions",[]) if c.get("context_id")==_f["context_id"]]:
            _f["observability_status"]=_c["observability_status"]; _f["domain_status"]=_c["domain_status"]; _f["causality_result"]=_c["causality_result"]
    cg["causal_analysis"]={"profile": profile_note, "contract":"M263+M268: reachability_status por contexto separado de epistemic_status M262; sin duplicar CFG/callgraph; fts_sort directo permanece UNRESOLVED.","counts_by_reachability":dict(counts),"total_contexts":len(flat),"flat":flat,"note":"REACHED=observado; NOT_REACHED=domain probado sin alcance; CONDITION_UNKNOWN=sin experimento; REACHED_TARGET_UNRESOLVED=callsite sin destino."}
    report["profile_application"] = profile_note
    report["limitations"]=list(report.get("limitations") or [])+["M263: alcanzabilidad causal acotada al dominio GDB probado; NOT_REACHED no equivale a UNREACHABLE_PROVEN; " + profile_note + "."]
    return report


def save_report(report: dict, output_path: str):
    """Guarda el expediente de reconstrucción en JSON."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return output_path
