"""M590 PATCH SCOUT: ciclo acotado bytes sintéticos (aplica+revierte+oráculo)."""
from tools.rxre.analysis.acre import synthesize_const_patch

def scout_cycle(observed: bytes, expected: bytes, offset=0, oracle_fn=None):
    patch = synthesize_const_patch(observed, offset, expected)
    if not patch.get("ok"):
        return {"applied": False, "reason": patch.get("reason", "synth fail")}
    if not patch["diffs"]:
        return {"applied": True, "diffs": [], "oracle": True, "reverted": True}
    mutated = bytearray(observed)
    for d in patch["diffs"]:
        mutated[d["off"]-offset] = d["new"]
    ok = oracle_fn(patch["diffs"]) if oracle_fn else True
    # revert
    for d in patch["diffs"]:
        mutated[d["off"]-offset] = d["old"]
    reverted = bytes(mutated) == observed
    return {"applied": True, "diffs": patch["diffs"], "oracle": ok, "reverted": reverted}
