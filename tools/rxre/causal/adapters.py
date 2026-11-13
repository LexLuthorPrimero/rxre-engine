"""M426 — Evidence adapters for RXRE.

Each adapter transforms a specific source format into canonical entities.
Adapters know their input formats; the classifier does not.
"""
from __future__ import annotations
import json, hashlib, pathlib, re
from .schema import make_entity, make_relation, SCHEMA_VERSION, ADAPTER_VERSION

def _hash_file(path):
    try:
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except Exception:
        return "UNAVAILABLE"

def _hash_str(s):
    return hashlib.sha256(s.encode()).hexdigest()



def _lift_cert_structured(cert, mission, h, entities, exec_status):
    """M431: lift structurally recoverable cert fields dropped by baseline adapter.
    Evidence-justified (M430/post-M430 analysis): cert_adapter ignored traces,
    discriminant_analysis, separation, hierarchy_derived_from_binary, gmp_operations,
    result_object_flow, static_analysis, comparison_with_expr.
    Rules: no invention; observation/interpretation separated; no epistemic promotion;
    M423-M429 analysis-of-analysis artifacts SKIPPED (circularity risk).
    """
    # 1) traces (M419/M421): mixed observation/interpretation - lift as structured record
    # Observation subfields: calls, token_flow, input, expected, wc_args, write_counts_args,
    # wc_return, write_counts_return, sequence. Interpretive text may be embedded (e.g. "(GMP integer pointer)")
    # -> classify entity as DYNAMIC_OBSERVATION when predominantly observational keys present, else SEMANTIC_INFERENCE; always PARTIAL.
    obs_keys = {"calls","token_flow","input","expected","wc_args","write_counts_args","wc_return","write_counts_return","calls_count","sequence"}
    for sk, sv in (cert.get("traces") or {}).items():
        if not isinstance(sv, dict):
            entities.append(make_entity(
                entity_id=f"cert:{mission}:traces:{sk}", entity_type="RESULT",
                source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
                source_locator=f"traces.{sk}", observation_type="SEMANTIC_INFERENCE",
                epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
                premises=[_safe_prem(sk, sv)], relations=[]))
            continue
        has_obs = any(k in obs_keys for k in sv.keys())
        obs = "DYNAMIC_OBSERVATION" if has_obs else "SEMANTIC_INFERENCE"
        premises = []
        for k, v in sv.items():
            premises.append(_safe_prem(k, v))
        entities.append(make_entity(
            entity_id=f"cert:{mission}:traces:{sk}", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator=f"traces.{sk}", observation_type=obs,
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=premises, relations=[],
            extra={"lift_classification": "mixed_observation_interpretation_separated_by_premise", "source_field": "traces"}))

    # 2) discriminant_analysis (M419): interpretive analysis - SEMANTIC_INFERENCE, no promotion
    da = cert.get("discriminant_analysis")
    if isinstance(da, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:discriminant_analysis", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="discriminant_analysis", observation_type="SEMANTIC_INFERENCE",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in da.items()], relations=[]))

    # 3) separation (M419-M422): meta-classification of evidence types - SEMANTIC_INFERENCE
    sep = cert.get("separation")
    if isinstance(sep, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:separation", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="separation", observation_type="SEMANTIC_INFERENCE",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in sep.items()], relations=[]))

    # 4) hierarchy_derived_from_binary (M419): structural derivation claim - STRUCTURAL_FACT? stated as derived from binary; keep as STRUCTURAL_FACT/PROVEN only for the derivation record? safer: STRUCTURAL_FACT/PARTIAL (derivation, not re-verified here)
    hier = cert.get("hierarchy_derived_from_binary")
    if isinstance(hier, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:hierarchy_derived_from_binary", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="hierarchy_derived_from_binary", observation_type="STRUCTURAL_FACT",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in hier.items()], relations=[]))

    # 5) static_analysis (M421): structural facts + interpretation
    sa = cert.get("static_analysis")
    if isinstance(sa, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:static_analysis", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="static_analysis", observation_type="STRUCTURAL_FACT",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in sa.items()], relations=[]))

    # 6) gmp_operations / result_object_flow (M420): mixed; respect separation if present
    for fname in ("gmp_operations", "result_object_flow", "gmp_struct_layout"):
        fv = cert.get(fname)
        if isinstance(fv, dict):
            entities.append(make_entity(
                entity_id=f"cert:{mission}:{fname}", entity_type="RESULT",
                source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
                source_locator=fname, observation_type="SEMANTIC_INFERENCE",
                epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
                premises=[_safe_prem(k, v) for k, v in fv.items()], relations=[],
                extra={"lift_note": "mixed direct_observation+inference; see cert.separation when present; no promotion"}))

    # 7) comparison_with_expr (M421): interpretive comparison
    cwe = cert.get("comparison_with_expr")
    if isinstance(cwe, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:comparison_with_expr", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="comparison_with_expr", observation_type="SEMANTIC_INFERENCE",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in cwe.items()], relations=[]))

    # 8) causal_chain_complete (M420): causal synthesis - SEMANTIC_INFERENCE/CAUSAL_ATTRIBUTION-acotada context, no promotion
    ccc = cert.get("causal_chain_complete")
    if isinstance(ccc, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:causal_chain_complete", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="causal_chain_complete", observation_type="SEMANTIC_INFERENCE",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in ccc.items()], relations=[],
            extra={"lift_note": "causal chain synthesis; acotada; see cert.separation; no promotion"}))

    # 9) M422 correlation/edge_classification: lift evidenced correlations as entities+relations
    # INTERPROC_EDGE_DYNAMIC entries are dynamically observed (M422) -> DYNAMIC_OBSERVATION/PARTIAL.
    # INTRAPROC_EDGE_DYNAMIC is NOT_DETERMINED in M422 -> never fabricated. EXTERNAL marked as such.
    corr = cert.get("correlation")
    ec = cert.get("edge_classification")
    if isinstance(ec, dict):
        entities.append(make_entity(
            entity_id=f"cert:{mission}:edge_classification", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="edge_classification", observation_type="SEMANTIC_INFERENCE",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[_safe_prem(k, v) for k, v in ec.items()], relations=[],
            extra={"preserves": "INTRAPROC_EDGE_DYNAMIC=NOT_DETERMINED"}))
    if isinstance(corr, dict):
        # summary entity
        entities.append(make_entity(
            entity_id=f"cert:{mission}:correlation", entity_type="RESULT",
            source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
            source_locator="correlation", observation_type="DYNAMIC_OBSERVATION",
            epistemic_state="PARTIAL", execution_status=exec_status, evidence_refs=[h],
            premises=[f"artifact={ak} edges={len(av) if isinstance(av,dict) else 0}" for ak,av in corr.items()],
            relations=[]))
        # evidenced edge relations (explicit in cert, provenance to cert hash)
        for artifact, edges in corr.items():
            if not isinstance(edges, dict): continue
            for edge_name, ed in edges.items():
                if not isinstance(ed, dict): continue
                etype = ed.get("type","")
                if etype == "INTRAPROC_EDGE_DYNAMIC":
                    # explicitly NOT_DETERMINED - do not create as observed edge
                    entities.append(make_entity(
                        entity_id=f"cert:{mission}:corr:{artifact}:{edge_name}",
                        entity_type="RESULT", source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
                        source_locator=f"correlation.{artifact}.{edge_name}", observation_type="NOT_OBSERVED",
                        epistemic_state="NOT_DETERMINED", execution_status=exec_status, evidence_refs=[h],
                        premises=[_safe_prem(k,v) for k,v in ed.items()], relations=[]))
                    continue
                obs_t = "DYNAMIC_OBSERVATION" if "DYNAMIC" in etype else ("STRUCTURAL_FACT" if "EXTERNAL" in etype else "SEMANTIC_INFERENCE")
                ep_t = "PARTIAL" if "DYNAMIC" in etype else "NOT_DETERMINED"
                rels = [make_relation(
                    from_id=f"cert:{mission}:corr:{artifact}:{edge_name}",
                    to_id=f"block_ref:{ed.get('block','unknown')}",
                    relation_type=etype.replace(' ','_'),
                    obs_type=obs_t, epistemic=ep_t, evidence_refs=[h],
                    premises=[f"edge={edge_name} addr={ed.get('addr')} file={ed.get('file')} range={ed.get('range')}"])]
                entities.append(make_entity(
                    entity_id=f"cert:{mission}:corr:{artifact}:{edge_name}",
                    entity_type="RESULT", source_id=f"cert_{mission}", source_format="CERT_JSON", source_hash=h,
                    source_locator=f"correlation.{artifact}.{edge_name}", observation_type=obs_t,
                    epistemic_state=ep_t, execution_status=exec_status, evidence_refs=[h],
                    premises=[_safe_prem(k,v) for k,v in ed.items()], relations=rels))

    # SKIP: M423-M429 unified_graph/adversarial_tests/coverage/comparison/extractor/dependency_audit/source_certificates
    # (analysis-of-analysis; circularity risk; not primary binary semantic evidence)

def cert_adapter(cert_path, cert_hash=None):
    """Transform a certificate JSON into canonical entities."""
    p = pathlib.Path(cert_path)
    if not p.exists():
        return [], f"file not found: {cert_path}"
    try:
        cert = json.loads(p.read_text())
    except Exception as e:
        return [], f"parse error: {e}"
    h = cert_hash or _hash_file(cert_path)
    entities = []
    # Extract metrics as evidence
    mission = cert.get("mission", "unknown")
    dictamen = cert.get("dictamen", "NOT_DETERMINED")
    # Map dictamen to epistemic state
    epistemic_map = {
        "PASS": "PARTIAL",
        "PASS_PARTIAL": "PARTIAL",
        "PROVEN": "PROVEN",
        "BLOCKED": "NOT_DETERMINED",
        "NOT_DETERMINED": "NOT_DETERMINED",
    }
    epistemic = epistemic_map.get(dictamen, "NOT_DETERMINED")
    # Execution status
    exec_map = {"PASS": "PASS", "PASS_PARTIAL": "PASS", "PROVEN": "PASS",
                "BLOCKED": "BLOCKED", "NOT_DETERMINED": "NOT_EXECUTED"}
    exec_status = exec_map.get(dictamen, "NOT_EXECUTED")

    # Extract from metrics
    for key, val in cert.get("metrics", {}).items():
        if isinstance(val, str):
            # Determine obs type from key
            if "behavior" in key.lower() or "match" in key.lower():
                obs = "DYNAMIC_OBSERVATION"
            elif "path" in key.lower() or "correspondence" in key.lower():
                obs = "DYNAMIC_OBSERVATION"
            elif "transform" in key.lower() or "attribution" in key.lower():
                obs = "SEMANTIC_INFERENCE"
            elif "oracle" in key.lower():
                obs = "DYNAMIC_OBSERVATION"
            else:
                obs = "STRUCTURAL_FACT"
            # Determine epistemic from value
            if "PASS" in val.upper():
                ep = "PARTIAL"  # PASS of tests != proven
            elif "PARTIAL" in val.upper():
                ep = "PARTIAL"
            elif "NOT_DETERMINED" in val.upper() or "NOT DETERMINED" in val.upper():
                ep = "NOT_DETERMINED"
            elif "PROVEN" in val.upper():
                ep = "PROVEN"
            elif "BLOCKED" in val.upper():
                ep = "BLOCKED"
            else:
                ep = "NOT_DETERMINED"
            entities.append(make_entity(
                entity_id=f"cert:{mission}:{key}",
                entity_type="RESULT",
                source_id=f"cert_{mission}",
                source_format="CERT_JSON",
                source_hash=h,
                source_locator=f"metrics.{key}",
                observation_type=obs,
                epistemic_state=ep,
                execution_status=exec_status,
                evidence_refs=[h],
                premises=[f"metric {key} = {val}"],
            ))

    # Extract from results
    for key, val in cert.get("results", {}).items():
        if isinstance(val, str):
            if "PASS" in val.upper() and "PARTIAL" not in val.upper():
                ep = "PARTIAL"  # PASS of tests != proven
            elif "PARTIAL" in val.upper():
                ep = "PARTIAL"
            elif "NOT_DETERMINED" in val.upper():
                ep = "NOT_DETERMINED"
            elif "PROVEN" in val.upper():
                ep = "PROVEN"
            elif "BLOCKED" in val.upper():
                ep = "BLOCKED"
            else:
                ep = "NOT_DETERMINED"
            obs = "SEMANTIC_INFERENCE" if "transform" in key.lower() or "causal" in key.lower() else "DYNAMIC_OBSERVATION"
            entities.append(make_entity(
                entity_id=f"cert:{mission}:result:{key}",
                entity_type="RESULT",
                source_id=f"cert_{mission}",
                source_format="CERT_JSON",
                source_hash=h,
                source_locator=f"results.{key}",
                observation_type=obs,
                epistemic_state=ep,
                execution_status=exec_status,
                evidence_refs=[h],
                premises=[f"result {key} = {val}"],
            ))

    # Extract from preserved states
    for key, val in cert.get("preserved", {}).items():
        if isinstance(val, str):
            ep = "PROVEN" if "PROVEN" in val.upper() else ("PARTIAL" if "PARTIAL" in val.upper() else ("NOT_DETERMINED" if "NOT_DETERMINED" in val.upper() else ("BLOCKED" if "BLOCKED" in val.upper() else "NOT_DETERMINED")))
            entities.append(make_entity(
                entity_id=f"cert:{mission}:preserved:{key}",
                entity_type="RESULT",
                source_id=f"cert_{mission}",
                source_format="CERT_JSON",
                source_hash=h,
                source_locator=f"preserved.{key}",
                observation_type="STRUCTURAL_FACT",
                epistemic_state=ep,
                execution_status=exec_status,
                evidence_refs=[h],
                premises=[f"preserved {key} = {val}"],
            ))

    _lift_cert_structured(cert, mission, h, entities, exec_status)
    return entities, f"cert_adapter v{ADAPTER_VERSION}+m431"


def _safe_prem(k, v):
    try:
        if isinstance(v, (dict, list)):
            return f"{k}={json.dumps(v, ensure_ascii=False, sort_keys=True)}"
        return f"{k}={v}"
    except Exception:
        return f"{k}=<unserializable>"

def trace_adapter(trace_path):
    """Transform a GDB trace JSON into canonical entities.
    M431 lifting (evidence-justified): preserves all observed entry fields in premises/extra
    and emits CALLED_BY relations from explicit caller references (direct observation).
    No epistemic promotion; DYNAMIC_OBSERVATION/PARTIAL preserved.
    """
    p = pathlib.Path(trace_path)
    if not p.exists():
        return [], f"file not found: {trace_path}"
    try:
        trace = json.loads(p.read_text())
    except Exception as e:
        return [], f"parse error: {e}"
    h = _hash_file(trace_path)
    entities = []
    stem = pathlib.Path(trace_path).stem
    for i, entry in enumerate(trace):
        func = entry.get("function", "unknown")
        caller = entry.get("caller", "unknown")
        entry_id = f"trace:{stem}:{func}:entry:{i}"
        # Direct observation: all available trace fields lifted (no invention)
        known = ("function", "caller")
        obs_premises = [f"function={func}", f"caller={caller}"]
        for k, v in entry.items():
            if k in known:
                continue
            obs_premises.append(_safe_prem(k, v))
        extra = {"caller": caller}
        for k in ("return_value", "return_value_hex", "call_id", "ret_addr", "rdi", "rsi", "rdx", "rcx", "r8", "r9", "global_token_str", "global_token_ptr", "mem", "returned"):
            if k in entry:
                extra[k] = entry[k]
        # Relation: observed call edge (caller reference explicit in trace) - NOT causal attribution
        relations = []
        if caller and caller != "unknown":
            relations.append(make_relation(
                from_id=entry_id,
                to_id=f"trace_ref:{stem}:caller:{caller}",
                relation_type="CALLED_BY",
                obs_type="DYNAMIC_OBSERVATION",
                epistemic="PARTIAL",
                evidence_refs=[h],
                premises=[f"observed caller={caller} for function={func} in trace entry {i}"],
            ))
        entities.append(make_entity(
            entity_id=entry_id,
            entity_type="FUNCTION",
            source_id=stem,
            source_format="TRACE_JSON",
            source_hash=h,
            source_locator=f"entry[{i}].function={func}",
            observation_type="DYNAMIC_OBSERVATION",
            epistemic_state="PARTIAL",
            execution_status="PASS",
            evidence_refs=[h],
            premises=obs_premises,
            relations=relations,
            extra=extra,
        ))
        rv = entry.get("return_value")
        if rv is not None:
            entities.append(make_entity(
                entity_id=f"trace:{stem}:{func}:return:{i}",
                entity_type="RESULT",
                source_id=stem,
                source_format="TRACE_JSON",
                source_hash=h,
                source_locator=f"entry[{i}].return_value",
                observation_type="DYNAMIC_OBSERVATION",
                epistemic_state="PARTIAL",
                execution_status="PASS",
                evidence_refs=[h],
                premises=[f"return_value={rv}"] + ([f"return_value_hex={entry.get('return_value_hex')}"] if entry.get('return_value_hex') is not None else []),
                relations=[make_relation(
                    from_id=f"trace:{stem}:{func}:return:{i}",
                    to_id=entry_id,
                    relation_type="RETURN_OF",
                    obs_type="DYNAMIC_OBSERVATION",
                    epistemic="PARTIAL",
                    evidence_refs=[h],
                    premises=[f"return observed for entry {i} function={func}"],
                )],
            ))
    return entities, f"trace_adapter v{ADAPTER_VERSION}+m431"


def cfg_adapter(cfg_path):
    """Transform a CFG JSON into canonical entities."""
    p = pathlib.Path(cfg_path)
    if not p.exists():
        return [], f"file not found: {cfg_path}"
    try:
        cfg = json.loads(p.read_text())
    except Exception as e:
        return [], f"parse error: {e}"
    h = _hash_file(cfg_path)
    entities = []
    for func_name, func_cfg in cfg.items():
        if not isinstance(func_cfg, dict):
            continue
        # Function entity
        entities.append(make_entity(
            entity_id=f"cfg:{pathlib.Path(cfg_path).stem}:{func_name}",
            entity_type="FUNCTION",
            source_id=pathlib.Path(cfg_path).stem,
            source_format="CFG_JSON",
            source_hash=h,
            source_locator=f"function={func_name}",
            observation_type="STRUCTURAL_FACT",
            epistemic_state="PROVEN",
            execution_status="PASS",
            evidence_refs=[h],
            premises=[f"blocks={func_cfg.get('num_blocks', 0)}, edges={len(func_cfg.get('edges', []))}"],
            extra={"num_blocks": func_cfg.get("num_blocks", 0), "num_edges": len(func_cfg.get("edges", []))},
        ))
        # Block entities
        for blk in func_cfg.get("blocks", []):
            entities.append(make_entity(
                entity_id=f"cfg:{pathlib.Path(cfg_path).stem}:{func_name}:block:{blk['id']}",
                entity_type="BLOCK",
                source_id=pathlib.Path(cfg_path).stem,
                source_format="CFG_JSON",
                source_hash=h,
                source_locator=f"function={func_name}, block={blk['id']}, range={blk['start']}-{blk['end']}",
                observation_type="STRUCTURAL_FACT",
                epistemic_state="PROVEN",
                execution_status="PASS",
                evidence_refs=[h],
                premises=[f"block {blk['id']}: {blk['num_instrs']} instrs, range {blk['start']}-{blk['end']}"],
            ))
    return entities, f"cfg_adapter v{ADAPTER_VERSION}"


def disasm_adapter(disasm_path, func_name=None):
    """Transform a disassembly TXT into canonical entities (function-level)."""
    p = pathlib.Path(disasm_path)
    if not p.exists():
        return [], f"file not found: {disasm_path}"
    text = p.read_text()
    h = _hash_file(disasm_path)
    entities = []
    # Extract function headers: lines like "0000... <name>:"
    import re
    funcs = re.findall(r'^([0-9a-f]+) <([^>]+)>:', text, re.M)
    seen = set()
    for addr, name in funcs:
        if name in seen:
            continue
        seen.add(name)
        # Clean name (remove @plt, @@Base, etc.)
        clean = name.split("@")[0]
        entities.append(make_entity(
            entity_id=f"disasm:{pathlib.Path(disasm_path).stem}:{clean}",
            entity_type="FUNCTION",
            source_id=pathlib.Path(disasm_path).stem,
            source_format="DISASM_TXT",
            source_hash=h,
            source_locator=f"function={name} at 0x{addr}",
            observation_type="STRUCTURAL_FACT",
            epistemic_state="PROVEN",
            execution_status="PASS",
            evidence_refs=[h],
            premises=[f"function {name} at address 0x{addr}"],
        ))
    return entities, f"disasm_adapter v{ADAPTER_VERSION}"

def typed_event_adapter(typed_event_path, source_id=None, source_cert_hash=None):
    """Transform a TYPED_EVENT_JSON payload into canonical entities/relations (M433 contract).
    Additive adapter; evidence-justified (no prior ingestion path for TYPED_EVENT_JSON).
    Preserves epistemic separation: candidates remain SEMANTIC_INFERENCE/PARTIAL, no promotion.
    """
    import json, pathlib
    from .typed_event_ingest import ingest_typed_events, INGEST_VERSION
    p = pathlib.Path(typed_event_path)
    if not p.exists():
        return [], f"file not found: {typed_event_path}"
    payload = json.loads(p.read_text(encoding="utf-8"))
    sid = source_id or p.stem
    res = ingest_typed_events(payload, source_id=sid, source_cert_hash=source_cert_hash)
    return res.get("entities", []), f"typed_event_adapter v{ADAPTER_VERSION}+m433 ({INGEST_VERSION}, {res.get('valid',0)}/{res.get('total',0)} valid)"
