"""M665 CARDINALITY BOUNDS acotado: intervalos y unicidad por guard demostrado.
Separación: estático demostrado / condicionado / observado / desconocido."""
from __future__ import annotations

def card_of(lo, hi, dests):
    n_idx = hi-lo+1 if lo<=hi else 0
    uniq = len(set(dests))
    cls = "PROVEN" if lo<=hi and uniq<=n_idx else "NOT_DETERMINED"
    return {"lo": lo, "hi": hi, "idx_card": n_idx, "uniq": uniq, "class": cls}

def check_guard(lo, hi, guard_hi):
    return lo<=hi and hi==guard_hi

def outside(idx, lo, hi):
    return idx<lo or idx>hi
