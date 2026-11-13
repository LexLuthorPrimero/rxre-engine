"""M630 CALL SUMMARY mínimo verificable (M630). Derivado del cuerpo, nunca por nombre/ABI.
Resumen: reads/writes (VA+width), unknown flag, procedencia (funcion, coverage, subj_hash).
Unknown => invalidación conservadora (nunca se interpreta como ausencia de efectos).
Recursión: iteración acotada (max_iter_default=3), si ciclo no resuelto => unknown (terminación).
"""
from __future__ import annotations
from typing import Dict, Set
from tools.rxre.analysis.mem_pred import Loc, Pred, overlap

def summarize(name, func_blocks_events, subj_hash=""):
    """
    func_blocks_events: {bid: [("load",loc,op,val) | ("store",loc,val) | ("call",callee_name) | ("indcall",)]}
    o None (sin cuerpo) -> unknown True.
    """
    if func_blocks_events is None:
        return {"name": name, "reads": set(), "writes": set(), "unknown": True,
                "coverage": 0.0, "subj_hash": subj_hash,
                "provenance": f"{name}: sin cuerpo (externa/indirecta)"}
    reads: Set[Loc] = set(); writes: Set[Loc] = set()
    unknown = False; seen=0; total=len(func_blocks_events)
    for bid, evs in func_blocks_events.items():
        seen+=1
        for ev in evs:
            if ev[0]=="load":
                reads.add(ev[1])
            elif ev[0]=="store":
                writes.add(ev[1])
            elif ev[0]=="call":
                # llamada anidada sin summary resuelto: unknown conservador
                unknown = True
            elif ev[0]=="indcall":
                unknown = True
    coverage = seen/total if total else 0.0
    # si hay call anidada sin summary, forzamos unknown (no asumir)
    return {"name": name, "reads": reads, "writes": writes, "unknown": unknown,
            "coverage": coverage, "subj_hash": subj_hash,
            "provenance": f"{name}: {seen}/{total} bloques, subj_hash={subj_hash}"}

def apply_summary(preds: Set[Pred], summary) -> Set[Pred]:
    """Transfiere preds a través de CALL según summary. Justificación trazable."""
    if summary is None or summary.get("unknown"):
        return set()  # conservador
    # hash check lo hace el caller (invalidated summary -> unknown)
    out=set()
    for p in preds:
        loc = p[0]
        if any(overlap(loc, w) for w in summary.get("writes", set())):
            continue  # invalidado por escritura aliasante
        out.add(p)  # conserva (reads sin escritura + disjuntas)
    return out

def summarize_fixedpoint(callgraph, bodies, subj_hash="", max_iter=3):
    """callgraph: {f: [callees]} ; bodies: {f: events or None}. Itera acotado; ciclo no resuelto => unknown."""
    summaries={}
    # init: sin cuerpo -> unknown; con cuerpo provisional sin calls internas -> conocido
    for f, ev in bodies.items():
        summaries[f]=summarize(f, ev, subj_hash)
    for _ in range(max_iter):
        changed=False
        for f, callees in callgraph.items():
            if f not in summaries or summaries[f]["unknown"]:
                continue  # ya unknown, no se optimiza
            # si algún callee unknown, f se vuelve unknown (conservador)
            for c in callees:
                if c not in summaries or summaries[c]["unknown"]:
                    if not summaries[f]["unknown"]:
                        summaries[f]=dict(summaries[f]); summaries[f]["unknown"]=True; changed=True
                    break
        if not changed:
            break
    # ciclos residuales no resueltos: marcar unknown conservador (ya hecho arriba)
    return summaries

def prop_with_summaries(succ, pred, entry, ids, block_events):
    """
    block_events: {bid: [("load",loc,op,val) | ("store",loc,val) | ("call_summary",summary_dict)]}
    ("call",) clásico -> unknown -> vacía (compat M629).
    """
    from tools.rxre.analysis.mem_pred import overlap as _overlap
    IN={n:set() for n in ids}; OUT={n:set() for n in ids}
    changed=True
    while changed:
        changed=False
        for n in ids:
            preds=[OUT.get(p,set()) for p in pred.get(n,[])]
            if preds:
                new_in=set(preds[0])
                for s in preds[1:]: new_in &= set(s)
            else: new_in=set()
            cur=set(new_in)
            for ev in block_events.get(n,[]):
                if ev[0]=="load":
                    _,l,op,val=ev; cur.add((l,op,val))
                elif ev[0]=="store":
                    _,l,val=ev
                    cur={p for p in cur if not _overlap(p[0],l)}
                    if val in (0,1): cur.add((l,"EQ",val))
                elif ev[0]=="call":
                    cur=set()
                elif ev[0]=="call_summary":
                    cur=apply_summary(cur, ev[1])
            if cur!=OUT[n] or new_in!=IN[n]:
                IN[n]=new_in; OUT[n]=cur; changed=True
    return IN, OUT
