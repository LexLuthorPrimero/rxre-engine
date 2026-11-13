"""M583 ACRE generador acotado (síntesis bytes desde diagnóstico causal mínimo).
Alcance: defectos de constante (1-byte) + propiedades orículo triviales.
Genera parche candidato reversible; validación separada.
"""
from __future__ import annotations

def synthesize_const_patch(observed: bytes, offset: int, expected: bytes) -> dict:
    if len(observed) != len(expected):
        return {"ok": False, "reason": "len mismatch"}
    diffs = []
    for i in range(len(observed)):
        if observed[i] != expected[i]:
            diffs.append({"off": offset+i, "old": observed[i], "new": expected[i]})
    # Acotado: solo parches 1..4 bytes (documentado)
    if len(diffs) == 0:
        return {"ok": True, "diffs": [], "note": "sin cambio"}
    if len(diffs) > 4:
        return {"ok": False, "reason": f"diffs={len(diffs)}>{4} fuera de alcance acotado"}
    return {"ok": True, "diffs": diffs, "note": f"{len(diffs)}-byte patch acotado"}

def oracle_trivial(patch, oracle_fn):
    if not patch.get("ok") or not patch.get("diffs"):
        return patch.get("ok", False)
    return oracle_fn(patch["diffs"])
