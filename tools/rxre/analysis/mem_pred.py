"""M629 MEM_PRED acotado: predicados de memoria globales (byte flag + qword ptr).
Identidad de ubicación = VA ELF absoluta (no base aparente). Invalida por escritura aliasante.
Nunca PROVEN si alias no resuelto (conservador).
"""
from __future__ import annotations
from typing import Dict, Set, Tuple, List

# Location identity: (va, width) where va=int ELF VA
Loc = Tuple[int, int]

def loc_of(rip_pc, size, disp):
    # RIP-relative: va = pc+size+disp
    return (rip_pc + size + disp, 1)  # caller must pass width separately

def loc(va: int, width: int) -> Loc:
    return (va, width)

def overlap(a: Loc, b: Loc) -> bool:
    return not (a[0]+a[1] <= b[0] or b[0]+b[1] <= a[0])

def same(a: Loc, b: Loc) -> bool:
    return a == b

# Predicado: (loc, op, val) donde op in {"EQ","NE"} ; EQ val means load==val, NE means load!=val
Pred = Tuple[Loc, str, int]

def prop_predicate(succ, pred, entry, ids, block_events):
    """
    block_events: {bid: [("load",loc,op,val) | ("store",loc,val) | ("call",)]}
    Propaga IN/OUT de predicados. Store a misma loc lo invalida (salvo val demostrado igual -> se crea nuevo pred).
    Store solapada con anchura distinta -> invalida (conservador).
    CALL sin prueba de no-alias -> invalida todos (conservador).
    Join: intersect preds (solo sobrevive si en todas ramas).
    """
    IN: Dict[str, Set[Pred]] = {n: set() for n in ids}
    OUT: Dict[str, Set[Pred]] = {n: set() for n in ids}
    changed=True
    while changed:
        changed=False
        for n in ids:
            new_in: Set[Pred] = set()
            preds = [OUT.get(p, set()) for p in pred.get(n, [])]
            if preds:
                # join = intersect (conservador)
                new_in = set(preds[0])
                for s in preds[1:]:
                    new_in &= set(s)
            elif n == entry:
                new_in=set()
            cur = set(new_in)
            for ev in block_events.get(n, []):
                if ev[0]=="load":
                    _, l, op, val = ev
                    cur.add((l, op, val))
                elif ev[0]=="store":
                    _, l, val = ev
                    # invalida preds solapadas
                    cur = {p for p in cur if not overlap(p[0], l)}
                    # nuevo pred estabilizado si val == 0/1 preciso
                    if val in (0,1):
                        cur.add((l, "EQ", val))
                elif ev[0]=="call":
                    # conservador: invalida todo (sin summary de callees)
                    cur=set()
            if cur != OUT[n] or new_in != IN[n]:
                IN[n]=new_in; OUT[n]=cur; changed=True
    return IN, OUT

def holds(preds, loc, op, val):
    return (loc, op, val) in preds
