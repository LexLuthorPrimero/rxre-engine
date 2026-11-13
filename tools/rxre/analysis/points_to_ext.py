"""M595 Points-to extendido: field-sensitivity acotada (offset) + heap summary.
Extiende M581 sin romperlo; over-approx conservador.
"""
from tools.rxre.analysis.points_to import anderson_subset, may_alias

def anderson_field(alloc_sites, constraints):
    # constraints con "store_field" y "assign_field"
    # alloc key: "base.off"
    pts = anderson_subset(alloc_sites, [])
    # store_field: base*(off) = val  => pts["base.off*"] |= pts[val]
    for c in constraints:
        if c[0] == "store_field":
            _, base, off, val = c
            key = f"{base}.{off}*"
            pts.setdefault(key, set())
            pts[key] |= pts.get(val, set())
        elif c[0] == "assign":
            _, var, rhs = c
            if rhs in pts:
                pts.setdefault(var, set())
                pts[var] |= pts[rhs]
        elif c[0] == "assign_field":
            _, var, base, off = c
            pts.setdefault(var, set())
            pts[var] |= pts.get(f"{base}.{off}*", set())
    return pts

def heap_summary(n_allocs, k=2):
    # summariza: si >k allocs heap, colapsa a heap_alloc[*]
    return {"heap_alloc[*]"} if n_allocs > k else {f"heap_alloc({i})" for i in range(n_allocs)}
