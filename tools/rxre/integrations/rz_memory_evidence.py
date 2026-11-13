"""RXRE-MISSION-391 — Integración genérica Rz/Capstone para evidencia de
OFFSET, ALIAS y ACCESS_LENGTH.

Reutiliza el adaptador existente `cs_disasm` (Capstone) para desensamblar un
rango y extraer operandos de memoria (base, índice, escala, desplazamiento) y
tamaños implícitos por mnemónico. Convierte esos hechos en observaciones
genéricas para el recolector M389. No contiene reglas específicas de libtiff
ni decide demostración (eso es M388/contrato).
"""
from __future__ import annotations
import sys, re
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.backends.adapters import cs_disasm

MNEMONIC_SIZES = {
    "movb": 1, "movw": 2, "movl": 4, "movq": 8, "movabs": 8,
    "mov": None,  # unknown without suffix; infer from operand? keep None
    "leaq": 8, "leal": 4, "lea": None,
    "cmpb": 1, "cmpw": 2, "cmpl": 4, "cmpq": 8,
    "addq": 8, "addl": 4, "addw": 2, "addb": 1,
    "subq": 8, "subl": 4,
    "pushq": 8, "popq": 8,
    "testb": 1, "testw": 2, "testl": 4, "testq": 8,
}

SIZE_PREFIX = {
    "byte ptr": 1, "word ptr": 2, "dword ptr": 4, "qword ptr": 8,
    "xmmword ptr": 16, "ymmword ptr": 32,
}


def _access_size(mnem, op_str):
    """Derive a candidate access size from mnemonic/op_str. Returns int or None."""
    low = mnem.lower()
    if low in MNEMONIC_SIZES and MNEMONIC_SIZES[low] is not None:
        return MNEMONIC_SIZES[low]
    # try size prefix in op_str
    s = op_str.lower()
    for pref, sz in SIZE_PREFIX.items():
        if pref in s:
            return sz
    return None


def extract_memory_operands(cs_result):
    """Given a cs_disasm result dict, return list of operand records with provenance."""
    records = []
    res = (cs_result.get("results") or [{}])[0]
    instrs = res.get("value", {}).get("instrucciones", []) if isinstance(res.get("value"), dict) else []
    artifact = cs_result.get("precheck", {}).get("input_hash", "")
    artifact_path = None
    # try to get path from input
    inp = res.get("input", {})
    if isinstance(inp, dict):
        artifact_path = inp.get("artefacto") or inp.get("path")
    for ins in instrs:
        addr = ins.get("direccion")
        mnem = ins.get("mnemonico", "")
        op_str = ins.get("op_str", "")
        for o in ins.get("operandos", []):
            if o.get("tipo") != "mem":
                continue
            base = o.get("base") or ""
            idx = o.get("indice") or ""
            scale = o.get("escala", 1)
            disp = o.get("desplazamiento", 0)
            rec = {
                "instruction_address": addr,
                "mnemonic": mnem,
                "op_str": op_str,
                "base": base,
                "index": idx,
                "scale": scale,
                "displacement": disp,
                "access_size_candidate": _access_size(mnem, op_str),
                "artifact": artifact_path,
                "artifact_hash": artifact,
            }
            records.append(rec)
    return records


def to_observations(records, target_buffer_id, source_artifact, method="rz_memory_evidence"):
    """Convert memory-operand records into generic observations for collector."""
    obs = []
    # alias groups: same (base,index,scale,displacement)
    groups = {}
    for r in records:
        key = (r["base"], r["index"], r["scale"], r["displacement"])
        groups.setdefault(key, []).append(r)

    for r in records:
        addr = r["instruction_address"]
        # OFFSET observation (displacement relative to base register)
        obs.append({
            "obs_id": f"rz_off_{addr}_{r['displacement']}",
            "source_artifact": source_artifact,
            "kind": "memory_operand",
            "property_hint": "BUFFER_OFFSET",
            "value": r["displacement"],
            "value_kind": "CONSTANT" if isinstance(r["displacement"], int) else "UNKNOWN",
            "location": {"function": target_buffer_id, "offset": addr},
            "method": method,
            "proven": False,  # base register may not point to buffer
            "quantity": "register_relative",
            "rz_provenance": {
                "mnemonic": r["mnemonic"],
                "op_str": r["op_str"],
                "base": r["base"],
                "index": r["index"],
                "scale": r["scale"],
                "artifact_hash": r["artifact_hash"],
            },
            "limitations": "displacement is relative to base register; base may not be buffer; not proven offset",
        })
        # ACCESS_LENGTH observation if size derivable
        if r["access_size_candidate"] is not None:
            obs.append({
                "obs_id": f"rz_len_{addr}",
                "source_artifact": source_artifact,
                "kind": "memory_operand",
                "property_hint": "BUFFER_ACCESS_LENGTH",
                "value": r["access_size_candidate"],
                "value_kind": "DERIVED",
                "location": {"function": target_buffer_id, "offset": addr},
                "method": method,
                "proven": False,
                "quantity": "register_relative",
                "rz_provenance": {
                    "mnemonic": r["mnemonic"],
                    "op_str": r["op_str"],
                    "artifact_hash": r["artifact_hash"],
                },
                "limitations": "size derived from mnemonic/op_str; not confirmed as effective access length",
            })
    # ALIAS candidates: groups with >1 instruction sharing same memory expression
    for key, grp in groups.items():
        if len(grp) > 1:
            obs.append({
                "obs_id": f"rz_alias_{grp[0]['instruction_address']}",
                "source_artifact": source_artifact,
                "kind": "memory_alias_candidate",
                "property_hint": "BUFFER_ALIAS_SET",
                "value": "CANDIDATE",
                "value_kind": "CANDIDATE",
                "location": {"function": target_buffer_id, "offset": grp[0]["instruction_address"]},
                "method": method,
                "proven": False,
                "quantity": "register_relative",
                "rz_provenance": {
                    "shared_expression": {"base": key[0], "index": key[1],
                                         "scale": key[2], "displacement": key[3]},
                    "instruction_addresses": [g["instruction_address"] for g in grp],
                    "artifact_hash": grp[0]["artifact_hash"],
                },
                "limitations": "candidate alias by shared memory expression; not dynamically confirmed",
            })
    return obs


def run(artifact, start, length, target_buffer_id, arch="x86_64"):
    """Run capstone on range and return (records, observations, cs_result)."""
    cs_res = cs_disasm.desensamblar(artifact, inicio=start, longitud=length, arquitectura=arch)
    if cs_res.get("status") not in ("ok", "OK"):
        return [], [], cs_res
    records = extract_memory_operands(cs_res)
    # artifact hash from precheck
    ah = cs_res.get("precheck", {}).get("input_hash", "")
    for r in records:
        if not r.get("artifact"):
            r["artifact"] = artifact
        if not r.get("artifact_hash"):
            r["artifact_hash"] = ah
    obs = to_observations(records, target_buffer_id, artifact)
    return records, obs, cs_res


__all__ = ["extract_memory_operands", "to_observations", "run", "MNEMONIC_SIZES", "SIZE_PREFIX"]
