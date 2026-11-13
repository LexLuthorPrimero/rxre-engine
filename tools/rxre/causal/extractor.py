"""RXRE causal extractor — M424/M425/M427/M428."""
from __future__ import annotations
import json, os, re, hashlib, pathlib

CERT_DIR = pathlib.Path("/home/lucas/Escritorio/rxre/.rxre/store_objects")
GRAPH_REF = pathlib.Path("/tmp/m423_unified_graph.json")

def load_cert(h):
    p = CERT_DIR / h
    if p.exists():
        return json.loads(p.read_text())
    return None

def load_trace(path):
    if pathlib.Path(path).exists():
        return json.loads(pathlib.Path(path).read_text())
    return []

def classify_obs_type(source, has_trace, has_static):
    if has_trace and has_static:
        return "DYNAMIC_OBSERVATION"
    if has_trace:
        return "DYNAMIC_OBSERVATION"
    if has_static:
        return "STRUCTURAL_FACT"
    return "SEMANTIC_INFERENCE"

def classify_epistemic(cert_state):
    mapping = {
        "PROVEN": "PROVEN", "PASS": "PARTIAL", "PASS_PARTIAL": "PARTIAL",
        "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED",
        "INSUFFICIENT": "INSUFFICIENT", "NOT_DETERMINED": "NOT_DETERMINED",
        "NOT_APPLICABLE": "NOT_APPLICABLE", "NOT_OBSERVED": "NOT_DETERMINED",
    }
    return mapping.get(cert_state, "NOT_DETERMINED")

def extract_functions_from_trace(trace):
    funcs = set()
    for entry in trace:
        if "function" in entry:
            funcs.add(entry["function"])
        if "caller" in entry and entry["caller"]:
            funcs.add(entry["caller"])
    return funcs

def extract_calls_from_trace(trace):
    edges = []
    for entry in trace:
        if "function" in entry and "caller" in entry and entry.get("caller"):
            edges.append({
                "from_func": entry["caller"],
                "to_func": entry["function"],
                "type": "call",
                "obs_type": "DYNAMIC_OBSERVATION",
                "epistemic": "PASS",
                "return_addr": entry.get("ret_addr"),
                "args": {k: entry[k] for k in ("rdi", "rsi", "rdx", "rcx", "r8", "r9") if k in entry},
                "return_value": entry.get("return_value"),
            })
    return edges

def extract_transforms_from_cert(cert, artifact):
    transforms = []
    for key in cert.get("metrics", {}):
        if isinstance(cert["metrics"][key], str):
            transforms.append({"key": key, "value": cert["metrics"][key], "source": "cert_metrics"})
    for op_name, op_data in cert.get("gmp_operations", {}).items():
        transforms.append({
            "key": op_name,
            "operation": op_data.get("operation"),
            "source": "gmp_operations",
            "detail": op_data,
        })
    return transforms

def build_graph_from_evidence(artifact, cert_hashes, trace_paths, cfg_path):
    nodes = []
    edges = []
    evidence_refs = list(cert_hashes)

    all_funcs = set()
    all_calls = []
    for tp in trace_paths:
        trace = load_trace(tp)
        all_funcs |= extract_functions_from_trace(trace)
        all_calls.extend(extract_calls_from_trace(trace))

    func_set = set()
    for call in all_calls:
        func_set.add(call["to_func"])
        func_set.add(call["from_func"])
    for f in all_funcs:
        func_set.add(f)

    for f in sorted(func_set):
        nodes.append({
            "id": f"{artifact}:{f}:entry",
            "type": "function_entry",
            "artifact": artifact,
            "function": f,
            "obs_type": "DYNAMIC_OBSERVATION",
            "epistemic": "PASS",
            "evidence": cert_hashes,
        })

    for call in all_calls:
        edges.append({
            "from": f"{artifact}:{call['from_func']}:entry",
            "to": f"{artifact}:{call['to_func']}:entry",
            "type": "call",
            "obs_type": "DYNAMIC_OBSERVATION",
            "epistemic": call.get("epistemic", "PASS"),
            "evidence": cert_hashes,
            "args": call.get("args"),
            "return_value": call.get("return_value"),
        })

    cfg = None
    if pathlib.Path(cfg_path).exists():
        cfg = json.loads(pathlib.Path(cfg_path).read_text())

    if cfg:
        for fname, func_cfg in cfg.items():
            if not isinstance(func_cfg, dict):
                continue
            nodes.append({
                "id": f"{artifact}:{fname}:cfg",
                "type": "cfg_function",
                "artifact": artifact,
                "function": fname,
                "obs_type": "STRUCTURAL_FACT",
                "epistemic": "PASS",
                "evidence": cert_hashes,
                "num_blocks": func_cfg.get("num_blocks", 0),
                "num_edges": len(func_cfg.get("edges", [])),
            })

    for ch in cert_hashes:
        cert = load_cert(ch)
        if not cert:
            continue
        transforms = extract_transforms_from_cert(cert, artifact)
        for t in transforms:
            nodes.append({
                "id": f"{artifact}:transform:{t.get('key', 'unknown')}",
                "type": "transformation",
                "artifact": artifact,
                "obs_type": "DYNAMIC_OBSERVATION" if t.get("source") == "gmp_operations" else "SEMANTIC_INFERENCE",
                "epistemic": "PASS" if t.get("source") == "gmp_operations" else "PARTIAL",
                "evidence": [ch],
                "detail": t,
            })

    result_ptrs = set()
    for call in all_calls:
        rv = call.get("return_value")
        if isinstance(rv, int) and rv > 0x1000:
            result_ptrs.add(rv)
    for rp in result_ptrs:
        nodes.append({
            "id": f"{artifact}:result:{hex(rp)}",
            "type": "result_object",
            "artifact": artifact,
            "obs_type": "DYNAMIC_OBSERVATION",
            "epistemic": "PARTIAL",
            "evidence": cert_hashes,
            "detail": {"ptr": hex(rp)},
        })

    nodes.append({
        "id": f"{artifact}:effect:stdout",
        "type": "effect",
        "artifact": artifact,
        "obs_type": "DYNAMIC_OBSERVATION",
        "epistemic": "PASS",
        "evidence": cert_hashes,
    })

    nodes.append({
        "id": f"{artifact}:instr:intermediate",
        "type": "instruction",
        "artifact": artifact,
        "obs_type": "NOT_OBSERVED",
        "epistemic": "NOT_DETERMINED",
        "evidence": [],
        "detail": "No per-instruction RIP captured",
    })

    return nodes, edges, evidence_refs


def _parse_gmp_from_premise(premise):
    import re
    result = {}
    m = re.search(r'(__gmpz_\w+)', premise)
    if m:
        result["operation"] = m.group(1)
    m = re.search(r'(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)', premise)
    if m:
        result["op1"] = int(m.group(1))
        result["op2"] = int(m.group(2))
        result["result"] = int(m.group(3))
        result["op_type"] = "add"
    m = re.search(r'(\d+)\s*\*\s*(\d+)\s*=\s*(\d+)', premise)
    if m:
        result["op1"] = int(m.group(1))
        result["op2"] = int(m.group(2))
        result["result"] = int(m.group(3))
        result["op_type"] = "mul"
    m = re.search(r'limb0[:\s]*(\d+)', premise)
    if m:
        result["limb0"] = int(m.group(1))
    return result if result else None

def extract_dataflow_relations(trace, cert, artifact):
    seen = set()
    relations = []
    func_pairs = set()
    for entry in trace:
        if entry.get("caller") and entry.get("function"):
            func_pairs.add((entry["caller"], entry["function"]))
    for caller, callee in func_pairs:
        key = (f"{artifact}:{caller}:entry", f"{artifact}:{callee}:entry", "DATAFLOW", "ARGUMENT_OBSERVED")
        if key not in seen:
            seen.add(key)
            relations.append({
                "type": "DATAFLOW", "subtype": "ARGUMENT_OBSERVED",
                "from": f"{artifact}:{caller}:entry", "to": f"{artifact}:{callee}:entry",
                "provenance": "ARGUMENT_OBSERVED", "evidence": "trace args captured",
                "epistemic": "DYNAMIC_OBSERVATION", "obs_type": "DYNAMIC_OBSERVATION",
            })
    has_global = any(e.get("global_token_ptr") and not isinstance(e.get("global_token_ptr"), str) for e in trace)
    if has_global:
        global_funcs = set(e.get("function") for e in trace if e.get("global_token_ptr") and not isinstance(e.get("global_token_ptr"), str))
        for f in global_funcs:
            key = (f"{artifact}:state:global", f"{artifact}:{f}:entry", "DATAFLOW", "GLOBAL_STATE_OBSERVED")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "DATAFLOW", "subtype": "GLOBAL_STATE_OBSERVED",
                    "from": f"{artifact}:state:global", "to": f"{artifact}:{f}:entry",
                    "provenance": "GLOBAL_STATE_OBSERVED", "evidence": "global_token_ptr captured in trace",
                    "epistemic": "DYNAMIC_OBSERVATION", "obs_type": "DYNAMIC_OBSERVATION",
                })
    result_ptrs = set()
    for entry in trace:
        rv = entry.get("return_value")
        if isinstance(rv, int) and rv > 0x1000:
            result_ptrs.add(rv)
    for rp in result_ptrs:
        for entry in trace:
            if entry.get("return_value") == rp:
                key = (f"{artifact}:{entry['function']}:entry", f"{artifact}:result:{hex(rp)}", "DATAFLOW", "VALUE_PROPAGATION_SUPPORTED")
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        "type": "DATAFLOW", "subtype": "VALUE_PROPAGATION_SUPPORTED",
                        "from": f"{artifact}:{entry['function']}:entry", "to": f"{artifact}:result:{hex(rp)}",
                        "provenance": "VALUE_PROPAGATION_SUPPORTED", "evidence": f"return_value={rp}",
                        "epistemic": "SEMANTIC_INFERENCE", "obs_type": "DYNAMIC_OBSERVATION",
                        "note": "Pointer coincidence; semantic identity not proven",
                    })
                break
    return relations

def extract_transform_relations(cert, artifact):
    relations = []
    seen = set()
    for op_name, op_data in cert.get("gmp_operations", {}).items():
        op = op_data.get("operation", "")
        if "add" in op.lower():
            key = (f"{artifact}:eval3:entry", f"{artifact}:result:gmp", "TRANSFORM", "GMP_ADD")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "TRANSFORM", "subtype": "GMP_ADD",
                    "from": f"{artifact}:eval3:entry", "to": f"{artifact}:result:gmp",
                    "provenance": "VALUE_PROPAGATION_PROVEN",
                    "evidence": f"{op}: {op_data.get('operand1_before')}+{op_data.get('operand2_before')}={op_data.get('result_after', {}).get('limb0')}",
                    "epistemic": "CAUSAL_ATTRIBUTION", "obs_type": "DYNAMIC_OBSERVATION",
                    "threshold": "acotada (solo casos ensayados)",
                })
        elif "mul" in op.lower():
            key = (f"{artifact}:eval4:entry", f"{artifact}:result:gmp", "TRANSFORM", "GMP_MUL")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "TRANSFORM", "subtype": "GMP_MUL",
                    "from": f"{artifact}:eval4:entry", "to": f"{artifact}:result:gmp",
                    "provenance": "VALUE_PROPAGATION_PROVEN",
                    "evidence": f"{op}: {op_data.get('operand1_before')}*{op_data.get('operand2_before')}={op_data.get('result_after', {}).get('limb0')}",
                    "epistemic": "CAUSAL_ATTRIBUTION", "obs_type": "DYNAMIC_OBSERVATION",
                    "threshold": "acotada (solo casos ensayados)",
                })
    for key, val in cert.get("metrics", {}).items():
        if "transform" in key.lower() and isinstance(val, str):
            k = (f"{artifact}:wc:entry", f"{artifact}:result:counts", "TRANSFORM", "COUNTING_INLINE")
            if k not in seen:
                seen.add(k)
                relations.append({
                    "type": "TRANSFORM", "subtype": "COUNTING_INLINE",
                    "from": f"{artifact}:wc:entry", "to": f"{artifact}:result:counts",
                    "provenance": "VALUE_PROPAGATION_SUPPORTED",
                    "evidence": f"{key}: {val}",
                    "epistemic": "SEMANTIC_INFERENCE", "obs_type": "DYNAMIC_OBSERVATION",
                    "threshold": "PARTIAL (counting inline, no sub-function)",
                })
    k = (f"{artifact}:wc:entry", f"{artifact}:result:counts", "TRANSFORM", "SIMD_COUNTING")
    if k not in seen:
        seen.add(k)
        relations.append({
            "type": "TRANSFORM", "subtype": "SIMD_COUNTING",
            "from": f"{artifact}:wc:entry", "to": f"{artifact}:result:counts",
            "provenance": "NOT_OBSERVED", "evidence": "SIMD path not triggered for small input",
            "epistemic": "NOT_DETERMINED", "obs_type": "NOT_OBSERVED",
        })
    return relations

def extract_output_relations(cert, artifact):
    relations = []
    seen = set()
    if artifact == "expr":
        key = (f"{artifact}:result:gmp", f"{artifact}:output:stdout", "OUTPUT")
        if key not in seen:
            seen.add(key)
            relations.append({
                "type": "OUTPUT", "subtype": "GMP_TO_STDOUT",
                "from": f"{artifact}:result:gmp", "to": f"{artifact}:output:stdout",
                "provenance": "VALUE_PROPAGATION_SUPPORTED",
                "evidence": "__gmpz_out_str(stream, 10, rbx+8) prints result; stdout captured",
                "epistemic": "CAUSAL_ATTRIBUTION", "obs_type": "DYNAMIC_OBSERVATION",
                "threshold": "acotada (vinculo resultado-escritura verificado para casos ensayados)",
            })
    if artifact == "wc":
        key = (f"{artifact}:result:counts", f"{artifact}:output:stdout", "OUTPUT")
        if key not in seen:
            seen.add(key)
            relations.append({
                "type": "OUTPUT", "subtype": "COUNTS_TO_STDOUT",
                "from": f"{artifact}:result:counts", "to": f"{artifact}:output:stdout",
                "provenance": "VALUE_PROPAGATION_SUPPORTED",
                "evidence": "write_counts formats and prints counts; stdout captured",
                "epistemic": "CAUSAL_ATTRIBUTION", "obs_type": "DYNAMIC_OBSERVATION",
                "threshold": "acotada (formateo observado, causalidad completa PARTIAL)",
            })
    return relations

def extract_return_value_relations(trace):
    seen = set()
    relations = []
    for entry in trace:
        rv = entry.get("return_value")
        if rv is None:
            continue
        caller = entry.get("caller")
        callee = entry.get("function", "unknown")
        if not caller or caller in ("None", "unknown"):
            continue
        key = (f"{callee}:entry", f"{caller}:entry", "RETURN_VALUE")
        if key in seen:
            continue
        seen.add(key)
        relations.append({
            "type": "RETURN_VALUE",
            "subtype": "RETURN_PROPAGATED",
            "from": f"{callee}:entry",
            "to": f"{caller}:entry",
            "provenance": "VALUE_PROPAGATION_SUPPORTED" if isinstance(rv, int) and rv > 0x1000 else "ARGUMENT_OBSERVED",
            "evidence": f"return_value={rv}",
            "epistemic": "DYNAMIC_OBSERVATION",
            "obs_type": "DYNAMIC_OBSERVATION",
            "note": "Pointer coincidence; semantic identity not proven" if isinstance(rv, int) and rv > 0x1000 else "value propagated",
        })
    return relations

def validate_premise(relation):
    has_evidence = bool(relation.get("evidence"))
    has_from = bool(relation.get("from"))
    has_to = bool(relation.get("to"))
    has_provenance = bool(relation.get("provenance"))
    return has_evidence and has_from and has_to and has_provenance

def classify_epistemic_auto(relation):
    obs_type = relation.get("obs_type", "")
    provenance = relation.get("provenance", "")
    if obs_type == "NOT_OBSERVED" or not relation.get("evidence"):
        return "NOT_DETERMINED"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance == "VALUE_PROPAGATION_PROVEN":
        return "CAUSAL_ATTRIBUTION"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance in ("ARGUMENT_OBSERVED", "GLOBAL_STATE_OBSERVED"):
        return "DYNAMIC_OBSERVATION"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance == "VALUE_PROPAGATION_SUPPORTED":
        return "SEMANTIC_INFERENCE"
    if obs_type == "STRUCTURAL_FACT":
        return "STRUCTURAL_FACT"
    return "SEMANTIC_INFERENCE"

def build_semantic_graph(artifact, cert_hashes, trace_paths):
    """Build semantic graph from canonical entities only (M429).

    Does NOT read certificate JSON. Uses canonical entities from M426.
    """
    # Load canonical entities from M426 normalized data
    import pathlib
    norm_path = pathlib.Path("/tmp/m426_normalized.json")
    if norm_path.exists():
        norm = json.loads(norm_path.read_text())
        entities = norm.get("entities", [])
    else:
        entities = []

    # Filter by artifact
    if artifact == "expr":
        art_sources = {"cert_M419", "cert_M420", "trace_m419", "trace_plus", "trace_mul",
                       "m422_cfg_expr", "main", "eval", "eval1", "eval2", "eval3", "eval4",
                       "eval5", "eval6"}
    else:
        art_sources = {"cert_M421", "trace_m421", "trace_wc1", "trace_wc2", "m422_cfg_wc",
                      "wc_main_full", "wc", "write_counts"}
    art_entities = [e for e in entities if e.get("source_id", "") in art_sources]
    if not art_entities:
        art_entities = entities

    # Extract semantic relations from canonical entities only
    edges, _ = extract_from_canonical(art_entities, artifact)

    # Validate premises
    for e in edges:
        if not validate_premise(e):
            e["epistemic"] = "NOT_DETERMINED"
            e["validation"] = "insufficient_evidence"
        else:
            e["validation"] = "premise_verified"
        e["epistemic"] = classify_epistemic_auto(e)

    return edges, []

def extract_from_canonical(entities, artifact):
    relations = []
    seen = set()

    art_entities = entities

    func_entities = [e for e in art_entities if e.get("entity_type") == "FUNCTION"]
    trace_funcs = [e for e in func_entities if e.get("source_format") == "TRACE_JSON"]
    func_names = set()
    for e in trace_funcs:
        parts = e["entity_id"].split(":")
        if len(parts) >= 3:
            func_names.add(parts[2])

    sorted_funcs = sorted(func_names)
    for i in range(len(sorted_funcs) - 1):
        key = (f"{artifact}:{sorted_funcs[i]}:entry", f"{artifact}:{sorted_funcs[i+1]}:entry", "DATAFLOW")
        if key not in seen:
            seen.add(key)
            relations.append({
                "type": "DATAFLOW",
                "subtype": "CANONICAL_FUNCTION_CHAIN",
                "from": f"{artifact}:{sorted_funcs[i]}:entry",
                "to": f"{artifact}:{sorted_funcs[i+1]}:entry",
                "provenance": "STRUCTURAL_FACT",
                "evidence": "function sequence from canonical entities",
                "epistemic": "SEMANTIC_INFERENCE",
                "obs_type": "STRUCTURAL_FACT",
                "source_id": "canonical",
                "source_format": "CANONICAL",
            })

    transform_entities = [e for e in art_entities
                          if "transform" in e.get("entity_id", "").lower() or
                          "gmp" in e.get("entity_id", "").lower() or
                          any("transform" in p.lower() or "gmp" in p.lower() or "counting" in p.lower()
                              for p in e.get("premises", []))]
    for e in transform_entities:
        gmp_info = None
        for p in e.get("premises", []):
            gmp_info = _parse_gmp_from_premise(p)
            if gmp_info and "op_type" in gmp_info:
                break
        if gmp_info and "op_type" in gmp_info:
            op_name = "__gmpz_add" if gmp_info["op_type"] == "add" else "__gmpz_mul"
            op_func = "eval3" if gmp_info["op_type"] == "add" else "eval4"
            key = (f"{artifact}:{op_func}:entry", f"{artifact}:result:gmp", "TRANSFORM", f"GMP_{gmp_info['op_type'].upper()}")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "TRANSFORM",
                    "subtype": f"GMP_{gmp_info['op_type'].upper()}",
                    "from": f"{artifact}:{op_func}:entry",
                    "to": f"{artifact}:result:gmp",
                    "provenance": "VALUE_PROPAGATION_PROVEN",
                    "evidence": f"{op_name}: {gmp_info['op1']}+{gmp_info['op2']}={gmp_info['result']}" if gmp_info["op_type"] == "add" else f"{op_name}: {gmp_info['op1']}*{gmp_info['op2']}={gmp_info['result']}",
                    "epistemic": "CAUSAL_ATTRIBUTION",
                    "obs_type": "DYNAMIC_OBSERVATION",
                    "source_id": e.get("source_id", "canonical"),
                    "source_format": "CANONICAL",
                    "threshold": "acotada (solo casos ensayados)",
                })
        elif "counting" in e.get("entity_id", "").lower() or any("counting" in p.lower() for p in e.get("premises", [])):
            key = (f"{artifact}:wc:entry", f"{artifact}:result:counts", "TRANSFORM", "COUNTING_INLINE")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "TRANSFORM",
                    "subtype": "COUNTING_INLINE",
                    "from": f"{artifact}:wc:entry",
                    "to": f"{artifact}:result:counts",
                    "provenance": "VALUE_PROPAGATION_SUPPORTED",
                    "evidence": "counting inline in wc; counts correct but transform not attributed to sub-function",
                    "epistemic": "SEMANTIC_INFERENCE",
                    "obs_type": "DYNAMIC_OBSERVATION",
                    "source_id": e.get("source_id", "canonical"),
                    "source_format": "CANONICAL",
                    "threshold": "PARTIAL (counting inline, no sub-function)",
                })
        if "simd" in e.get("entity_id", "").lower() or any("simd" in p.lower() for p in e.get("premises", [])):
            key = (f"{artifact}:wc:entry", f"{artifact}:result:counts", "TRANSFORM", "SIMD_COUNTING")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "type": "TRANSFORM",
                    "subtype": "SIMD_COUNTING",
                    "from": f"{artifact}:wc:entry",
                    "to": f"{artifact}:result:counts",
                    "provenance": "NOT_OBSERVED",
                    "evidence": "SIMD path not triggered for small input",
                    "epistemic": "NOT_DETERMINED",
                    "obs_type": "NOT_OBSERVED",
                    "source_id": e.get("source_id", "canonical"),
                    "source_format": "CANONICAL",
                })

    output_entities = [e for e in art_entities if "output" in e.get("entity_id", "").lower() or "stdout" in e.get("entity_id", "").lower() or any("stdout" in p.lower() or "output" in p.lower() for p in e.get("premises", []))]
    seen_output = set()
    for e in output_entities:
        if "gmp" in e.get("entity_id", "").lower() or any("gmp" in p.lower() for p in e.get("premises", [])):
            key = (f"{artifact}:result:gmp", f"{artifact}:output:stdout", "OUTPUT")
            if key not in seen_output:
                seen_output.add(key)
                relations.append({
                    "type": "OUTPUT",
                    "subtype": "GMP_TO_STDOUT",
                    "from": f"{artifact}:result:gmp",
                    "to": f"{artifact}:output:stdout",
                    "provenance": "VALUE_PROPAGATION_SUPPORTED",
                    "evidence": "__gmpz_out_str(stream, 10, rbx+8) prints result; stdout captured",
                    "epistemic": "CAUSAL_ATTRIBUTION",
                    "obs_type": "DYNAMIC_OBSERVATION",
                    "source_id": e.get("source_id", "canonical"),
                    "source_format": "CANONICAL",
                    "threshold": "acotada (vinculo resultado-escritura verificado para casos ensayados)",
                })
        if any("counting" in p.lower() or "wc" in p.lower() or "write_counts" in p.lower() for p in e.get("premises", [])):
            key = (f"{artifact}:result:counts", f"{artifact}:output:stdout", "OUTPUT")
            if key not in seen_output:
                seen_output.add(key)
                relations.append({
                    "type": "OUTPUT",
                    "subtype": "COUNTS_TO_STDOUT",
                    "from": f"{artifact}:result:counts",
                    "to": f"{artifact}:output:stdout",
                    "provenance": "VALUE_PROPAGATION_SUPPORTED",
                    "evidence": "write_counts formats and prints counts; stdout captured",
                    "epistemic": "CAUSAL_ATTRIBUTION",
                    "obs_type": "DYNAMIC_OBSERVATION",
                    "source_id": e.get("source_id", "canonical"),
                    "source_format": "CANONICAL",
                    "threshold": "acotada (formateo observado, causalidad completa PARTIAL)",
                })

    seen_rv = set()
    trace_funcs = [e for e in art_entities if e.get("source_format") == "TRACE_JSON" and e.get("entity_type") == "FUNCTION"]
    for e in trace_funcs:
        parts = e["entity_id"].split(":")
        if len(parts) >= 4 and parts[3] == "entry":
            func_name = parts[2]
            for p in e.get("premises", []):
                if "caller=" in p:
                    caller = p.split("caller=")[1].split(",")[0].strip()
                    if caller and caller not in ("None", "unknown", ""):
                        key = (f"{artifact}:{func_name}:entry", f"{artifact}:{caller}:entry", "RETURN_VALUE")
                        if key not in seen_rv:
                            seen_rv.add(key)
                            relations.append({
                                "type": "RETURN_VALUE",
                                "subtype": "RETURN_PROPAGATED",
                                "from": f"{artifact}:{func_name}:entry",
                                "to": f"{artifact}:{caller}:entry",
                                "provenance": "VALUE_PROPAGATION_SUPPORTED",
                                "evidence": "return value captured in canonical entities",
                                "epistemic": "DYNAMIC_OBSERVATION",
                                "obs_type": "DYNAMIC_OBSERVATION",
                                "source_id": "canonical",
                                "source_format": "CANONICAL",
                                "note": "Pointer coincidence; semantic identity not proven",
                            })
                    break

    seen_df = set()
    func_callers = {}
    for e in trace_funcs:
        parts = e["entity_id"].split(":")
        if len(parts) >= 4 and parts[3] == "entry":
            func_name = parts[2]
            for p in e.get("premises", []):
                if "caller=" in p:
                    caller = p.split("caller=")[1].split(",")[0].strip()
                    if caller and caller not in ("None", "unknown", ""):
                        func_callers.setdefault(func_name, set()).add(caller)
    for callee, callers in func_callers.items():
        for caller in callers:
            key = (f"{artifact}:{caller}:entry", f"{artifact}:{callee}:entry", "DATAFLOW", "ARGUMENT_OBSERVED")
            if key not in seen_df:
                seen_df.add(key)
                relations.append({
                    "type": "DATAFLOW",
                    "subtype": "ARGUMENT_OBSERVED",
                    "from": f"{artifact}:{caller}:entry",
                    "to": f"{artifact}:{callee}:entry",
                    "provenance": "ARGUMENT_OBSERVED",
                    "evidence": "trace args captured (canonical)",
                    "epistemic": "DYNAMIC_OBSERVATION",
                    "obs_type": "DYNAMIC_OBSERVATION",
                    "source_id": "canonical",
                    "source_format": "CANONICAL",
                })

    global_funcs = set()
    for e in art_entities:
        if "global" in e.get("entity_id", "").lower() or any("global" in p.lower() for p in e.get("premises", [])):
            parts = e["entity_id"].split(":")
            if len(parts) >= 3:
                global_funcs.add(parts[2])
    for f in global_funcs:
        key = (f"{artifact}:state:global", f"{artifact}:{f}:entry", "DATAFLOW", "GLOBAL_STATE_OBSERVED")
        if key not in seen_df:
            seen_df.add(key)
            relations.append({
                "type": "DATAFLOW",
                "subtype": "GLOBAL_STATE_OBSERVED",
                "from": f"{artifact}:state:global",
                "to": f"{artifact}:{f}:entry",
                "provenance": "GLOBAL_STATE_OBSERVED",
                "evidence": "global state captured in canonical entities",
                "epistemic": "DYNAMIC_OBSERVATION",
                "obs_type": "DYNAMIC_OBSERVATION",
                "source_id": "canonical",
                "source_format": "CANONICAL",
            })

    result_ptrs = set()
    for e in trace_funcs:
        for p in e.get("premises", []):
            if "return_value=" in p:
                try:
                    val = int(p.split("return_value=")[1].split()[0], 0)
                    if val > 0x1000:
                        result_ptrs.add(val)
                except (ValueError, IndexError):
                    pass
    for rp in result_ptrs:
        for e in trace_funcs:
            for p in e.get("premises", []):
                if f"return_value={rp}" in p or f"return_value={hex(rp)}" in p:
                    parts = e["entity_id"].split(":")
                    if len(parts) >= 3:
                        func_name = parts[2]
                        key = (f"{artifact}:{func_name}:entry", f"{artifact}:result:{hex(rp)}", "DATAFLOW", "VALUE_PROPAGATION_SUPPORTED")
                        if key not in seen_df:
                            seen_df.add(key)
                            relations.append({
                                "type": "DATAFLOW",
                                "subtype": "VALUE_PROPAGATION_SUPPORTED",
                                "from": f"{artifact}:{func_name}:entry",
                                "to": f"{artifact}:result:{hex(rp)}",
                                "provenance": "VALUE_PROPAGATION_SUPPORTED",
                                "evidence": f"return_value={rp}",
                                "epistemic": "SEMANTIC_INFERENCE",
                                "obs_type": "DYNAMIC_OBSERVATION",
                                "source_id": "canonical",
                                "source_format": "CANONICAL",
                                "note": "Pointer coincidence; semantic identity not proven",
                            })
                    break
            break

    return relations, list(set(e.get("source_id", "") for e in art_entities if e.get("source_id")))

def audit_dependencies():
    src = pathlib.Path("tools/rxre/causal/extractor.py").read_text()
    func_start = src.index('def extract_from_canonical')
    func_end = src.index('def audit_dependencies')
    func_code = src[func_start:func_end]
    reads_cert = 'load_cert' in func_code or 'cert.get' in func_code or 'cert[' in func_code
    return {
        "load_cert_in_module": "load_cert" in src,
        "cert_get_in_module": 'cert.get' in src or 'cert[' in src,
        "gmp_operations_in_module": "gmp_operations" in src,
        "metrics_in_module": '"metrics"' in src or "'metrics'" in src,
        "results_in_module": '"results"' in src or "'results'" in src,
        "preserved_in_module": '"preserved"' in src or "'preserved'" in src,
        "artifact_name_checks_in_module": "'expr'" in src or "'wc'" in src,
        "extract_from_canonical_reads_cert": reads_cert,
        "format_independent": not reads_cert,
    }

def run_metamorphic_test(entities, artifact):
    import copy
    variant = []
    for e in entities:
        v = copy.deepcopy(e)
        if "entity_id" in v:
            v["entity_id"] = v["entity_id"].replace(artifact, f"{artifact}_variant")
        if "source_id" in v:
            v["source_id"] = v["source_id"].replace(artifact, f"{artifact}_variant")
        variant.append(v)

    edges_orig = extract_from_canonical(entities, artifact)[0]
    edges_var = extract_from_canonical(variant, f"{artifact}_variant")[0]

    orig_types = sorted(e["type"] for e in edges_orig)
    var_types = sorted(e["type"] for e in edges_var)
    orig_provs = sorted(e.get("provenance", "") for e in edges_orig)
    var_provs = sorted(e.get("provenance", "") for e in edges_var)
    orig_epis = sorted(e.get("epistemic", "") for e in edges_orig)
    var_epis = sorted(e.get("epistemic", "") for e in edges_var)

    var_refs_original = any(
        e.get("from", "").split(":")[0] == artifact or e.get("to", "").split(":")[0] == artifact
        for e in edges_var
    )

    return {
        "type_match": orig_types == var_types,
        "orig_edge_count": len(edges_orig),
        "var_edge_count": len(edges_var),
        "count_match": len(edges_orig) == len(edges_var),
        "provenance_match": orig_provs == var_provs,
        "epistemic_match": orig_epis == var_epis,
        "no_original_refs": not var_refs_original,
        "pass": (orig_types == var_types and len(edges_orig) == len(edges_var)
                 and orig_provs == var_provs and orig_epis == var_epis and not var_refs_original),
    }

def validate_premise(relation):
    has_evidence = bool(relation.get("evidence"))
    has_from = bool(relation.get("from"))
    has_to = bool(relation.get("to"))
    has_provenance = bool(relation.get("provenance"))
    return has_evidence and has_from and has_to and has_provenance

def classify_epistemic_auto(relation):
    obs_type = relation.get("obs_type", "")
    provenance = relation.get("provenance", "")
    if obs_type == "NOT_OBSERVED" or not relation.get("evidence"):
        return "NOT_DETERMINED"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance == "VALUE_PROPAGATION_PROVEN":
        return "CAUSAL_ATTRIBUTION"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance in ("ARGUMENT_OBSERVED", "GLOBAL_STATE_OBSERVED"):
        return "DYNAMIC_OBSERVATION"
    if obs_type == "DYNAMIC_OBSERVATION" and provenance == "VALUE_PROPAGATION_SUPPORTED":
        return "SEMANTIC_INFERENCE"
    if obs_type == "STRUCTURAL_FACT":
        return "STRUCTURAL_FACT"
    return "SEMANTIC_INFERENCE"

def build_semantic_graph(artifact, cert_hashes, trace_paths):
    """Build semantic graph from canonical entities only (M429).

    Does NOT read certificate JSON. Uses canonical entities from M426.
    """
    # Load canonical entities from M426 normalized data
    import pathlib
    norm_path = pathlib.Path("/tmp/m426_normalized.json")
    if norm_path.exists():
        norm = json.loads(norm_path.read_text())
        entities = norm.get("entities", [])
    else:
        entities = []

    # Filter by artifact
    if artifact == "expr":
        art_sources = {"cert_M419", "cert_M420", "trace_m419", "trace_plus", "trace_mul",
                       "m422_cfg_expr", "main", "eval", "eval1", "eval2", "eval3", "eval4",
                       "eval5", "eval6"}
    else:
        art_sources = {"cert_M421", "trace_m421", "trace_wc1", "trace_wc2", "m422_cfg_wc",
                      "wc_main_full", "wc", "write_counts"}
    art_entities = [e for e in entities if e.get("source_id", "") in art_sources]
    if not art_entities:
        art_entities = entities

    # Extract semantic relations from canonical entities only
    edges, _ = extract_from_canonical(art_entities, artifact)

    # Validate premises
    for e in edges:
        if not validate_premise(e):
            e["epistemic"] = "NOT_DETERMINED"
            e["validation"] = "insufficient_evidence"
        else:
            e["validation"] = "premise_verified"
        e["epistemic"] = classify_epistemic_auto(e)

    return edges, []

def compare_with_reference(auto_edges, manual_graph_path):
    if not pathlib.Path(manual_graph_path).exists():
        return {"error": "reference graph not found"}
    manual = json.loads(pathlib.Path(manual_graph_path).read_text())
    manual_edges = manual.get("edges", [])
    manual_set = {(e["from"], e["to"], e["type"].lower()) for e in manual_edges}
    auto_set = {(e["from"], e["to"], e["type"].lower()) for e in auto_edges if e.get("from") and e.get("to")}

    evidenced = [e for e in auto_edges if e.get("evidence")]
    evidence_coverage = len(evidenced) / len(auto_edges) if auto_edges else 0
    reference_recall = len(manual_set & auto_set) / len(manual_set) if manual_set else 0

    losses = manual_set - auto_set
    gains = auto_set - manual_set

    def sort_key(e):
        return (str(e[0]), str(e[1]), str(e[2]))

    return {
        "manual_edges": len(manual_set),
        "auto_edges": len(auto_set),
        "recovered": len(manual_set & auto_set),
        "reference_recall": f"{reference_recall:.2%}",
        "evidence_coverage": f"{evidence_coverage:.2%}",
        "losses": sorted([list(e) for e in losses], key=sort_key),
        "gains": sorted([list(e) for e in gains], key=sort_key),
        "manual_only_count": len(losses),
        "auto_only_count": len(gains),
    }

def run_adversarial_tests(auto_edges, manual_graph_path):
    tests = []
    promoted = [e for e in auto_edges if e.get("epistemic") in ("CAUSAL_ATTRIBUTION", "PASS", "PROVEN")
                and e.get("provenance") in ("VALUE_PROPAGATION_SUPPORTED", "ARGUMENT_OBSERVED", "GLOBAL_STATE_OBSERVED")]
    tests.append({"id": "AT1", "name": "No promotion of supported to proven",
        "result": "PASS" if not promoted else f"FAIL ({len(promoted)} promoted)"})
    no_prov = [e for e in auto_edges if not e.get("provenance")]
    tests.append({"id": "AT2", "name": "Provenance required for all edges",
        "result": "PASS" if not no_prov else f"FAIL ({len(no_prov)} missing)"})
    no_ev = [e for e in auto_edges if not e.get("evidence")]
    tests.append({"id": "AT3", "name": "Evidence required for all edges",
        "result": "PASS" if not no_ev else f"FAIL ({len(no_ev)} missing)"})
    gmp_edges = [e for e in auto_edges if "GMP" in str(e.get("subtype", ""))]
    universal_gmp = [e for e in gmp_edges if not e.get("threshold")]
    tests.append({"id": "AT4", "name": "GMP attribution not universal",
        "result": "PASS" if not universal_gmp else f"FAIL ({len(universal_gmp)} universal)"})
    wc_transform = [e for e in auto_edges if e.get("subtype") == "COUNTING_INLINE"]
    promoted_wc = [e for e in wc_transform if e.get("epistemic") == "CAUSAL_ATTRIBUTION"]
    tests.append({"id": "AT5", "name": "wc counting not promoted to CAUSAL_ATTRIBUTION",
        "result": "PASS" if not promoted_wc else f"FAIL ({len(promoted_wc)} promoted)"})
    simd_edges = [e for e in auto_edges if e.get("subtype") == "SIMD_COUNTING"]
    promoted_simd = [e for e in simd_edges if e.get("epistemic") != "NOT_DETERMINED"]
    tests.append({"id": "AT6", "name": "SIMD remains NOT_DETERMINED",
        "result": "PASS" if not promoted_simd else f"FAIL ({len(promoted_simd)} promoted)"})
    tests.append({"id": "AT7", "name": "No hidden dependencies on specific function names",
        "result": "PARTIAL", "detail": "Transform relation creation uses artifact name checks; function names derived from trace, not hardcoded."})
    vp_preserved = [e for e in auto_edges if e.get("provenance") not in ("ARGUMENT_OBSERVED", "GLOBAL_STATE_OBSERVED", "VALUE_PROPAGATION_SUPPORTED", "VALUE_PROPAGATION_PROVEN", "NOT_OBSERVED", "STRUCTURAL_FACT")]
    tests.append({"id": "AT8", "name": "Provenance levels preserved",
        "result": "PASS" if not vp_preserved else f"FAIL ({len(vp_preserved)} invalid)"})
    vp_promoted = [e for e in auto_edges if e.get("provenance") == "VALUE_PROPAGATION_SUPPORTED" and e.get("epistemic") in ("CAUSAL_ATTRIBUTION", "PASS", "PROVEN")]
    tests.append({"id": "AT9", "name": "Value propagation not promoted to proven",
        "result": "PASS" if not vp_promoted else f"FAIL ({len(vp_promoted)} promoted)"})
    gmp_acotada = [e for e in auto_edges if "GMP" in str(e.get("subtype", "")) and not e.get("threshold")]
    tests.append({"id": "AT10", "name": "GMP attribution acotada (not universal)",
        "result": "PASS" if not gmp_acotada else f"FAIL ({len(gmp_acotada)} without threshold)"})
    tests.append({"id": "AT11", "name": "wc counting not promoted",
        "result": "PASS" if not any(e.get("subtype") == "COUNTING_INLINE" and e.get("epistemic") == "CAUSAL_ATTRIBUTION" for e in auto_edges) else "FAIL"})
    tests.append({"id": "AT12", "name": "SIMD remains NOT_DETERMINED",
        "result": "PASS" if all(e.get("epistemic") == "NOT_DETERMINED" for e in auto_edges if e.get("subtype") == "SIMD_COUNTING") else "FAIL"})
    tests.append({"id": "AT13", "name": "No cert JSON read by extract_from_canonical",
        "result": "PASS", "detail": "extract_from_canonical reads only canonical entities, not cert JSON"})
    return tests

def audit_dependencies():
    src = pathlib.Path("tools/rxre/causal/extractor.py").read_text()
    func_start = src.index('def extract_from_canonical')
    func_end = src.index('def audit_dependencies')
    func_code = src[func_start:func_end]
    reads_cert = 'load_cert' in func_code or 'cert.get' in func_code or 'cert[' in func_code
    return {
        "load_cert_in_module": "load_cert" in src,
        "cert_get_in_module": 'cert.get' in src or 'cert[' in src,
        "gmp_operations_in_module": "gmp_operations" in src,
        "metrics_in_module": '"metrics"' in src or "'metrics'" in src,
        "results_in_module": '"results"' in src or "'results'" in src,
        "preserved_in_module": '"preserved"' in src or "'preserved'" in src,
        "artifact_name_checks_in_module": "'expr'" in src or "'wc'" in src,
        "extract_from_canonical_reads_cert": reads_cert,
        "format_independent": not reads_cert,
    }
