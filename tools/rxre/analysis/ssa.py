"""M569 SSA minimal: dominators (Cooper-Harvey-Kennedy) + iterated DF.
Input CFG blocks as in reconstructor: [{"id":..,"offset":..,"out_nodes":[..]}].
"""
from __future__ import annotations
from typing import Dict, List, Set

def build_graph(blocks):
    succ: Dict[str, List[str]] = {}
    pred: Dict[str, List[str]] = {}
    ids: List[str] = []
    for b in blocks:
        bid = str(b["id"])
        ids.append(bid)
        succ[bid] = []
    for b in blocks:
        bid = str(b["id"])
        for o in b.get("out_nodes", []):
            oid = str(o)
            if oid not in succ:  # external/unknown target: keep as node
                succ[oid] = []
                if oid not in ids: ids.append(oid)
                pred.setdefault(oid, [])
            succ[bid].append(oid)
            pred.setdefault(oid, []).append(bid)
    for n in ids: pred.setdefault(n, [])
    return succ, pred, ids

def postorder(succ, entry, ids):
    visited=set(); order=[]
    stack=[(entry, iter(succ.get(entry, [])))]
    visited.add(entry)
    while stack:
        node, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            order.append(node); stack.pop()
        elif nxt not in visited:
            visited.add(nxt); stack.append((nxt, iter(succ.get(nxt, []))))
    # nodes unreachable from entry appended
    for n in ids:
        if n not in visited: order.append(n)
    return order  # postorder (leaves first)

def dominators(succ, pred, entry, ids):
    # Reverse postorder for iteration (Cooper et al.)
    po = postorder(succ, entry, ids)
    rpo = list(reversed(po))
    # Initialize: Dom[entry]={entry}, others=all
    Dom: Dict[str, Set[str]] = {n: set(ids) for n in ids}
    Dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for n in rpo:
            if n == entry: continue
            ps = [p for p in pred.get(n, []) if p in Dom]
            if not ps: continue
            new = set(ids)
            for p in ps: new &= Dom[p]
            new.add(n)
            if new != Dom[n]:
                Dom[n] = new; changed = True
    return Dom

def dominance_frontier(succ, pred, entry, ids, Dom):
    """Cytron DF (iterated via standard algorithm on dominator tree)."""
    # Build dominator tree (immediate dominator = deepest strict dominator)
    idom: Dict[str, str] = {}
    for n in ids:
        if n == entry: continue
        strict = Dom[n] - {n}
        if not strict: continue
        # deepest = max by Dom size
        idom[n] = max(strict, key=lambda d: len(Dom[d]))
    children: Dict[str, List[str]] = {n: [] for n in ids}
    for n, p in idom.items():
        children.setdefault(p, []).append(n)
    DF: Dict[str, Set[str]] = {n: set() for n in ids}
    # Process nodes in reverse postorder lower bounds (standard: for each node, walk up)
    for n in rpo_safe(succ, entry, ids):
        for p in pred.get(n, []):
            runner = p
            while runner != idom.get(n):
                DF[runner].add(n)
                if runner == entry or runner not in idom: break
                runner = idom[runner]
                if runner == n: break  # safety
    return DF

def rpo_safe(succ, entry, ids):
    return list(reversed(postorder(succ, entry, ids)))

def phi_placement(DF, var_defs: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """Iterated DF: phi nodes per variable."""
    result: Dict[str, Set[str]] = {}
    for var, defs in var_defs.items():
        has_phi: Set[str] = set()
        work = set(defs)
        placed: Set[str] = set()
        while work:
            n = work.pop()
            for d in DF.get(n, set()):
                if d not in placed and d not in defs:
                    placed.add(d)
                    work.add(d)
                elif d not in placed:
                    placed.add(d)
        result[var] = placed
    return result
