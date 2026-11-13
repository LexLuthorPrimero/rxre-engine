"""M632 INDIRECT TARGETS acotado: backward slice de registro destino.
Estados: SINGLE_TARGET_PROVEN, FINITE_TARGET_SET, MAY_TARGET, UNKNOWN. Nunca inventa destinos.
"""
from __future__ import annotations

SINGLE_TARGET_PROVEN="SINGLE_TARGET_PROVEN"
FINITE_TARGET_SET="FINITE_TARGET_SET"
MAY_TARGET="MAY_TARGET"
UNKNOWN="UNKNOWN"

def resolve(defs, max_iter=3):
    """defs: lista secuencial; phi: ("phi", [branch_defs])."""
    if max_iter<=0:
        return (UNKNOWN, set())
    if not defs:
        return (UNKNOWN, set())
    tail = defs[-1]
    kind = tail[0]
    if kind=="call":
        return (UNKNOWN, set())
    if kind=="const":
        return (SINGLE_TARGET_PROVEN, {tail[1]})
    if kind=="phi":
        branches = tail[1]
        outs=[]; ok=True
        for b in branches:
            st, vs = resolve(list(b) if isinstance(b, list) else [b], max_iter-1)
            if st in (SINGLE_TARGET_PROVEN, FINITE_TARGET_SET):
                outs.extend(vs)
            else:
                ok=False; break
        if not ok:
            return (MAY_TARGET, set())
        uniq=set(outs)
        return (SINGLE_TARGET_PROVEN, uniq) if len(uniq)==1 else (FINITE_TARGET_SET, uniq)
    if kind=="load_got":
        _, loc, gotkind = tail
        if gotkind=="local":
            # destino único local demostrado (offset en loc): conjunto completo singleton
            return (FINITE_TARGET_SET, {loc})
        return (MAY_TARGET, set())
    if kind=="unknown":
        return (UNKNOWN, set())
    if kind=="overwrite_const":
        # truncamiento/extensión que cambia destino: conservador unknown
        return (UNKNOWN, set())
    return (UNKNOWN, set())

def finites_to_cfg(targets_set, status):
    """Solo destinos admisibles actualizan CFG: SINGLE/FINITE extienden, MAY/UNKNOWN no."""
    if status in (SINGLE_TARGET_PROVEN, FINITE_TARGET_SET):
        return set(targets_set)
    return set()
