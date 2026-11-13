"""M581 points-to minimal (a nivel registro/stack, Andersen subset).
No es Andersen completo (sin field-sensitivity); inclusivo conservador:
p -> {alloc} si var apunta a alloc site abstracto.
"""
from __future__ import annotations
from typing import Dict, Set

# Nodos abstractos: "stack_arg(n)" "stack_local(n)" "func(name)" "heap_alloc(n)" "undef"
def anderson_subset(alloc_sites, constraints):
    # constraints: list of ("assign", var, rhs) | ("load", var, ptr) | ("store", ptr, val)
    # alloc_sites: dict var -> set(abstract)
    pts: Dict[str, Set[str]] = {v: set(s) for v, s in alloc_sites.items()}
    # init worklist propagation for direct assigns
    changed = True
    while changed:
        changed = False
        for c in constraints:
            kind = c[0]
            if kind == "assign":
                _, var, rhs = c
                # rhs node: either alloc var or literal
                if rhs in pts:
                    before = len(pts.setdefault(var, set()))
                    pts[var] |= pts[rhs]
                    if len(pts[var]) != before:
                        changed = True
            elif kind == "load":
                _, var, ptr = c
                for alloc in list(pts.get(ptr, set())):
                    # load var <- *alloc : points-to = targets stored to alloc (approx: same var set)
                    before = len(pts.setdefault(var, set()))
                    pts[var] |= {alloc}
                    if len(pts[var]) != before:
                        changed = True
            elif kind == "store":
                _, ptr, val = c
                # *ptr = val : add val's pts to each alloc pointee (conservative union)
                targets = pts.get(val, set())
                for alloc in list(pts.get(ptr, set())):
                    # model alloc as container: store targets into pts[alloc+"*"] fallback
                    key = alloc + "*"
                    before = len(pts.setdefault(key, set()))
                    pts[key] |= targets
                    if len(pts[key]) != before:
                        changed = True
    return pts

def may_alias(pts: Dict[str, Set[str]], a: str, b: str) -> bool:
    return bool(pts.get(a, set()) & pts.get(b, set()))
