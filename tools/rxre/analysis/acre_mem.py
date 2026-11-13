"""M596 ACRE memory subset: overflow-checked (M533 IN_RANGE) + size check.
Solo modelo u64 con OFF/R/D; no es síntesis heap completa.
"""
def in_range(off, size, dsize) -> bool:
    # M533: IN_RANGE <=> OFF<=D && R<D-OFF (u64, sin wrap)
    if off > dsize: return False
    if size >= dsize - off: return False
    return True

def synthesize_mem_check(off, size, dsize):
    if in_range(off, size, dsize):
        return {"ok": True, "verdict": "IN_RANGE"}
    return {"ok": True, "verdict": "OOB", "need_patch": "overflow-checked M533"}
