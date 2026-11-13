"""RXRE-MISSION-392 — Análisis de flujo genérico para ACCESS_LENGTH efectiva y ALIAS.

Reutiliza el adaptador Capstone (cs_disasm) y el patrón de propagación de
registros de M320 (intrabloque). No ejecuta binarios. No crea heurísticas
específicas de libtiff. Clasifica todo como candidato/parcial; no afirma
ejecución ni alias dinámico sin traza real.
"""
from __future__ import annotations
import sys, re
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.backends.adapters import cs_disasm

SIZE_FROM_MNEM = {
    "movb": 1, "movw": 2, "movl": 4, "movq": 8,
    "cmpb": 1, "cmpw": 2, "cmpl": 4, "cmpq": 8,
    "testb": 1, "testw": 2, "testl": 4, "testq": 8,
    "addb": 1, "addw": 2, "addl": 4, "addq": 8,
    "subb": 1, "subw": 2, "subl": 4, "subq": 8,
    "pushq": 8, "popq": 8, "leaq": 8, "leal": 4,
}
SIZE_PREFIX = {"byte ptr": 1, "word ptr": 2, "dword ptr": 4,
               "qword ptr": 8, "xmmword ptr": 16, "ymmword ptr": 32}


def _size(mnem, op_str):
    low = mnem.lower()
    if low in SIZE_FROM_MNEM and SIZE_FROM_MNEM[low] is not None:
        return SIZE_FROM_MNEM[low]
    s = op_str.lower()
    for pref, sz in SIZE_PREFIX.items():
        if pref in s:
            return sz
    return None


def _track_registers(instrs):
    """Simple intrablock register tracking: maps reg -> base expression (reg or 'param')."""
    state = {}  # reg -> {kind, base, offset}
    # x86_64 argument registers
    PARAM_REGS = {"rdi", "rsi", "rdx", "rcx", "r8", "r9"}
    for ins in instrs:
        mnem = ins.get("mnemonico", "").lower()
        ops = ins.get("operandos", [])
        # mov reg, reg  -> copy
        if mnem in ("mov", "movq", "movl", "movw", "movb") and len(ops) == 2:
            if ops[0].get("tipo") == "reg" and ops[1].get("tipo") == "reg":
                dst = ops[0]["reg"]; src = ops[1]["reg"]
                if src in state:
                    state[dst] = dict(state[src])
                elif src in PARAM_REGS:
                    state[dst] = {"kind": "param", "base": src, "offset": 0}
                else:
                    state[dst] = {"kind": "unknown", "base": src, "offset": 0}
            elif ops[0].get("tipo") == "reg" and ops[1].get("tipo") == "imm":
                # mov reg, imm -> constant (not a pointer)
                dst = ops[0]["reg"]
                state[dst] = {"kind": "const", "value": ops[1]["valor"], "offset": 0}
        # lea reg, [base + disp]
        if mnem.startswith("lea") and len(ops) == 2 and ops[0].get("tipo") == "reg" and ops[1].get("tipo") == "mem":
            dst = ops[0]["reg"]
            mem = ops[1]
            base = mem.get("base", "")
            disp = mem.get("desplazamiento", 0)
            idx = mem.get("indice", "")
            scale = mem.get("escala", 1)
            if base in state and state[base].get("kind") in ("param", "derived"):
                state[dst] = {"kind": "derived", "base": state[base].get("base", base),
                              "offset": state[base].get("offset", 0) + disp,
                              "index": idx, "scale": scale}
            elif base in ("rbp", "rsp"):
                state[dst] = {"kind": "stack", "base": base, "offset": disp}
            else:
                state[dst] = {"kind": "derived", "base": base, "offset": disp,
                              "index": idx, "scale": scale}
        # mov reg, [mem] doesn't change base tracking for dst (dst becomes loaded value, unknown)
        if mnem.startswith("mov") and len(ops) == 2 and ops[0].get("tipo") == "reg" and ops[1].get("tipo") == "mem":
            dst = ops[0]["reg"]
            # dst no longer a pointer (loaded value) -> mark unknown unless we track
            if dst in state:
                del state[dst]
    return state


def analyze_flow(cs_result, target):
    """Return flow analysis result dict."""
    res = (cs_result.get("results") or [{}])[0]
    instrs = res.get("value", {}).get("instrucciones", []) if isinstance(res.get("value"), dict) else []
    artifact = cs_result.get("precheck", {}).get("input_hash", "")
    inp = res.get("input", {}) if isinstance(res.get("input"), dict) else {}
    artifact_path = inp.get("artefacto") or inp.get("path")

    accesses = []
    # track register state per instruction index
    state = {}
    PARAM_REGS = {"rdi", "rsi", "rdx", "rcx", "r8", "r9"}
    for i, ins in enumerate(instrs):
        # update state before processing access? process mem operands using current state
        mnem = ins.get("mnemonico", "")
        ops = ins.get("operandos", [])
        # First, handle register-tracking updates for this instruction's operands
        # (lea/mov) after recording accesses? Memory access uses base reg current state.
        # Record memory accesses
        for o in ops:
            if o.get("tipo") != "mem":
                continue
            base = o.get("base") or ""
            idx = o.get("indice") or ""
            scale = o.get("escala", 1)
            disp = o.get("desplazamiento", 0)
            base_info = state.get(base, {})
            is_param = base in PARAM_REGS or base_info.get("kind") == "param"
            sz = _size(mnem, ins.get("op_str", ""))
            accesses.append({
                "address": ins.get("direccion"),
                "mnemonic": mnem,
                "op_str": ins.get("op_str"),
                "base_reg": base,
                "index_reg": idx,
                "scale": scale,
                "displacement": disp,
                "access_size": sz,
                "base_kind": base_info.get("kind", "unknown"),
                "base_origin": base_info.get("base", base),
                "base_offset": base_info.get("offset", 0),
                "is_param_base": is_param,
                "tam_bytes": ins.get("tam"),
            })
        # update state
        # mov reg, reg/imm
        if mnem.lower().startswith("mov") and len(ops) == 2 and ops[0].get("tipo") == "reg":
            if ops[1].get("tipo") == "reg":
                src = ops[1]["reg"]; dst = ops[0]["reg"]
                if src in state:
                    state[dst] = dict(state[src])
                elif src in PARAM_REGS:
                    state[dst] = {"kind": "param", "base": src, "offset": 0}
                else:
                    state[dst] = {"kind": "unknown", "base": src, "offset": 0}
            elif ops[1].get("tipo") == "imm":
                state[ops[0]["reg"]] = {"kind": "const", "value": ops[1]["valor"], "offset": 0}
        if mnem.lower().startswith("lea") and len(ops) == 2 and ops[0].get("tipo") == "reg" and ops[1].get("tipo") == "mem":
            dst = ops[0]["reg"]; mem = ops[1]
            base = mem.get("base", ""); disp = mem.get("desplazamiento", 0)
            idx = mem.get("indice", ""); scale = mem.get("escala", 1)
            if base in state and state[base].get("kind") in ("param", "derived"):
                state[dst] = {"kind": "derived", "base": state[base].get("base", base),
                              "offset": state[base].get("offset", 0) + disp,
                              "index": idx, "scale": scale}
            elif base in ("rbp", "rsp"):
                state[dst] = {"kind": "stack", "base": base, "offset": disp, "index": idx, "scale": scale}
            else:
                state[dst] = {"kind": "derived", "base": base, "offset": disp, "index": idx, "scale": scale}

    # alias groups: accesses sharing same (base_origin, displacement) after tracking
    groups = {}
    for a in accesses:
        key = (a["base_origin"], a["displacement"], a["index_reg"], a["scale"])
        groups.setdefault(key, []).append(a)
    alias_groups = [g for g in groups.values() if len(g) > 1]

    # effective access lengths: distinct sizes per base
    sizes_by_base = {}
    for a in accesses:
        sizes_by_base.setdefault(a["base_origin"], set()).add(a["access_size"])

    result = {
        "target": target,
        "n_instructions": len(instrs),
        "n_memory_accesses": len(accesses),
        "accesses": accesses,
        "alias_groups": [{"base_origin": g[0]["base_origin"],
                         "displacement": g[0]["displacement"],
                         "addresses": [a["address"] for a in g],
                         "count": len(g)} for g in alias_groups],
        "n_alias_groups": len(alias_groups),
        "sizes_by_base": {k: sorted(v) for k, v in sizes_by_base.items() if None not in v},
        "dynamic_trace_available": False,
        "artifact_hash": artifact,
        "provenance": {"method": "intrablock_flow_analysis", "no_execution": True,
                       "limitations": "intrablock only; interprocedural not resolved; no dynamic trace"},
    }
    return result


def to_observations(flow_result, target_buffer_id, source_artifact, method="flow_access"):
    obs = []
    # ACCESS_LENGTH: each distinct access size -> derived observation (not proven effective)
    for a in flow_result.get("accesses", []):
        if a.get("access_size") is not None:
            obs.append({
                "obs_id": f"flow_len_{a['address']}",
                "source_artifact": source_artifact,
                "kind": "flow_access",
                "property_hint": "BUFFER_ACCESS_LENGTH",
                "value": a["access_size"],
                "value_kind": "DERIVED",
                "location": {"function": target_buffer_id, "offset": a["address"]},
                "method": method,
                "proven": False,
                "flow_provenance": {
                    "mnemonic": a["mnemonic"],
                    "op_str": a["op_str"],
                    "base_reg": a["base_reg"],
                    "base_kind": a["base_kind"],
                    "artifact_hash": flow_result.get("artifact_hash"),
                },
                "limitations": "size from mnemonic; not confirmed as effective access length",
                "quantity": "flow_instruction",
            })
    # ALIAS: alias groups -> candidate
    for g in flow_result.get("alias_groups", []):
        obs.append({
            "obs_id": f"flow_alias_{g['addresses'][0]}",
            "source_artifact": source_artifact,
            "kind": "flow_alias",
            "property_hint": "BUFFER_ALIAS_SET",
            "value": "CANDIDATE",
            "value_kind": "CANDIDATE",
            "location": {"function": target_buffer_id, "offset": g["addresses"][0]},
            "method": method,
            "proven": False,
            "flow_provenance": {
                "shared_expression": {"base_origin": g["base_origin"], "displacement": g["displacement"]},
                "instruction_addresses": g["addresses"],
                "artifact_hash": flow_result.get("artifact_hash"),
            },
            "limitations": "candidate alias by shared flow expression; not dynamically confirmed",
            "quantity": "flow_alias",
        })
    # OFFSET: register-relative displacements (not proven buffer offset)
    seen = set()
    for a in flow_result.get("accesses", []):
        key = (a["base_origin"], a["displacement"])
        if key in seen:
            continue
        seen.add(key)
        obs.append({
            "obs_id": f"flow_off_{a['address']}_{a['displacement']}",
            "source_artifact": source_artifact,
            "kind": "flow_offset",
            "property_hint": "BUFFER_OFFSET",
            "value": a["displacement"],
            "value_kind": "CONSTANT" if isinstance(a["displacement"], int) else "UNKNOWN",
            "location": {"function": target_buffer_id, "offset": a["address"]},
            "method": method,
            "proven": False,
            "flow_provenance": {
                "base_reg": a["base_reg"],
                "base_kind": a["base_kind"],
                "artifact_hash": flow_result.get("artifact_hash"),
            },
            "limitations": "register-relative displacement; base may not be buffer",
            "quantity": "flow_register_relative",
        })
    return obs


def run(artifact, start, length, target, arch="x86_64"):
    cs_res = cs_disasm.desensamblar(artifact, inicio=start, longitud=length, arquitectura=arch)
    if cs_res.get("status") not in ("ok", "OK", 2):
        # status may be 2? check
        pass
    if not cs_res.get("results"):
        return None, [], cs_res
    flow = analyze_flow(cs_res, target)
    obs = to_observations(flow, target, artifact)
    return flow, obs, cs_res


__all__ = ["analyze_flow", "to_observations", "run", "SIZE_FROM_MNEM", "SIZE_PREFIX"]
