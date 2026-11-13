"""RXRE-MISSION-413 — Propagación interprocedimental genérica de capacidad.

Reutiliza el call graph M318 (si está disponible) y los resultados de análisis
de funciones. No crea un motor paralelo; opera sobre aristas y parámetros
proporcionados. Marca toda capacidad propagada como PARTIAL (inferencia), nunca
PROVEN, salvo evidencia independiente.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

def propagate(call_edges, func_params, capacity_evidence, target_func=None):
    """Propagate capacity evidence across call edges.

    call_edges: list of {caller, callee, arg_index, param_index, ...}
    func_params: dict func -> list of param names/types
    capacity_evidence: dict func -> {param_name: {capacity, proven, source, ...}}
    Returns: dict with propagated capacities and observations.
    """
    propagated = {}  # (func, param) -> {capacity, proven, source, method, ...}
    observations = []
    # seed from direct evidence
    for func, params in capacity_evidence.items():
        for pname, ev in params.items():
            propagated[(func, pname)] = dict(ev)
            propagated[(func, pname)]["method"] = "direct_evidence"

    # propagate along call edges
    # arg_index in caller's args -> param_index in callee's params
    changed = True
    iterations = 0
    max_iter = 10  # bounded, no infinite loops
    while changed and iterations < max_iter:
        changed = False
        iterations += 1
        for edge in call_edges:
            caller = edge.get("caller")
            callee = edge.get("callee")
            arg_idx = edge.get("arg_index", 0)
            param_idx = edge.get("param_index", 0)
            # get caller param name at arg_idx
            caller_params = func_params.get(caller, [])
            callee_params = func_params.get(callee, [])
            if arg_idx >= len(caller_params) or param_idx >= len(callee_params):
                continue
            caller_pname = caller_params[arg_idx]
            callee_pname = callee_params[param_idx]
            key_caller = (caller, caller_pname)
            key_callee = (callee, callee_pname)
            if key_caller in propagated and key_callee not in propagated:
                ev = dict(propagated[key_caller])
                ev["method"] = "propagated_from_call"
                ev["proven"] = False  # propagated capacity is inference, not proven
                ev["source"] = f"propagated from {caller}.{caller_pname}"
                propagated[key_callee] = ev
                changed = True
                observations.append({
                    "obs_id": f"prop_{caller}_{callee}_{arg_idx}_{param_idx}",
                    "source_artifact": edge.get("source_artifact", "unknown"),
                    "kind": "interproc_propagation",
                    "property_hint": "BUFFER_CAPACITY",
                    "value": ev.get("capacity"),
                    "location": {"function": callee},
                    "method": "interproc_capacity_propagation",
                    "proven": False,
                    "limitations": "propagated capacity is inference; not proven; aliasing/unknown paths may invalidate",
                    "quantity": "propagated",
                })
    return {
        "propagated": {f"{f}.{p}": v for (f, p), v in propagated.items()},
        "observations": observations,
        "iterations": iterations,
        "max_iter": max_iter,
    }


def analyze_call_edges(call_edges):
    """Analyze call edges for completeness and ambiguity."""
    issues = []
    # detect multiple callers for same callee param
    by_callee_param = {}
    for e in call_edges:
        key = (e.get("callee"), e.get("param_index", 0))
        by_callee_param.setdefault(key, []).append(e)
    for key, edges in by_callee_param.items():
        if len(edges) > 1:
            issues.append({"type": "multiple_callers", "callee_param": key,
                           "n_callers": len(edges), "note": "capacity may be ambiguous"})
    return {"issues": issues, "n_edges": len(call_edges)}


__all__ = ["propagate", "analyze_call_edges"]
