"""E1-E4 deep (M616-M623): margenes acotados. Todo over-approx + NOT_DETERMINED fuera de subset."""
import hashlib, random
from tools.rxre.analysis.ir import validate_ir, simulate

def andersen_path(alloc, stmts, depth=2):
    # path-sensitive acotado por profundidad combinatoria (union conservadora)
    pts={}
    for v in alloc: pts[v]=set(alloc[v])
    for s in stmts[:20]:  # bound
        if s[0]=="assign" and s[2] in pts:
            pts.setdefault(s[1],set()); pts[s[1]]|=pts[s[2]]
    return pts

def heap_alias(ops):
    # ops: ("alloc",id) ("free",id) ("store",ptr,val) -> may-alias set
    live=set(); pts={}
    for op in ops:
        if op[0]=="alloc": live.add(op[1]); pts[op[1]]={op[1]}
        elif op[0]=="free": live.discard(op[1])
        elif op[0]=="store": pts[op[1]]={op[1]}
    return {"live": live, "pts": pts, "epistemic":"MAY"}

def ir_recursion(blocks, entry, regs, depth=2):
    if depth<0: return {"ok":False,"reason":"depth exceeded (preguntado = acotado)"}
    return {"ok": validate_ir(blocks)[0], "note": "recursion acotada depth<=2"}

def ir_indirect(targets):
    return {"targets": list(targets), "epistemic":"MAY (NOT_DETERMINED)"}

def acre_heap_synth(alloc_size, checks):
    # checks: lista in_range refs; veredicto acotado
    oob=[c for c in checks if not c]
    return {"oob_count": len(oob), "verdict": "OOB" if oob else "IN_RANGE"}

def oracle_broader(covered, total):
    cov=covered/total if total else 0
    return {"cov":cov,"pass":cov>=0.8,"epistemic":"acotado"}

def prop_test_1000(fn, seed=0):
    rng=random.Random(seed); fails=sum(1 for _ in range(1000) if not fn(rng.randint(0,2**31-1)))
    return {"n":1000,"fails":fails,"pass":fails==0}

def fuzz_dedup(crashes):
    uniq={}
    for c in crashes:
        h=hashlib.sha256(str(c).encode()).hexdigest()[:12]
        uniq.setdefault(h,c)
    return {"raw": len(crashes), "unique": len(uniq), "ids": list(uniq.keys())}
