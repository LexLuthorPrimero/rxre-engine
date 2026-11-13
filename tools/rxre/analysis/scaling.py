"""E1-E4 scaling minimal: anderson flow-set, mem use/def, summary, alias-trace, ir nway/flags/sse/syscall, type2, oracle-cov, prop-test, ledger adapter.
Todo acotado, conservative, NOT_DETERMINED fuera de subset."""
from __future__ import annotations
import random
from tools.rxre.analysis.ir import validate_ir, simulate
from tools.rxre.analysis.points_to import anderson_subset, may_alias

def anderson_flow(alloc_sites, stmts):
    # stmts ordenadas: ("assign",v,rhs) flow-sensitive trivial (secuencial)
    pts = anderson_subset(alloc_sites, [])
    for s in stmts:
        if s[0]=="assign" and s[2] in pts:
            pts.setdefault(s[1], set()); pts[s[1]] |= pts[s[2]]
    return pts

def mem_use_def(stack_slots):
    # use_def_map memoria acotado: slots = {slot: ("use"|"def",)}
    use={s for s,v in stack_slots.items() if v=="use"}
    return {"use": use, "def": set(stack_slots)-use}

def summary(fname, calls):
    return {"func": fname, "n_calls": len(calls), "calls": list(calls), "note": "summary acotado sin recursion"}

def alias_trace(pts, a, b):
    return {"may_alias": may_alias(pts,a,b), "epistemic": "MAY (NOT_DETERMINED)"}

def ir_nway(blocks, entry, regs):
    ok,_=validate_ir(blocks)
    return {"ok": ok, "regs": simulate(blocks, entry, dict(regs))}

def flags_model(a, b):
    zf = 1 if a==b else 0
    cf = 1 if a<b else 0  # unsigned
    sf = 1 if (a ^ b) & 0x80 else 0  # simplificado 8b
    return {"ZF": zf, "CF": cf, "SF": sf, "epistemic": "subset NOT_DETERMINED"}

def sse_fp(a, b, op="add"):
    return {"res": a+b if op=="add" else a*b, "epistemic": "subset"}

def syscall_allow(name):
    return {"allow": name in {"exit","read","write"}, "epistemic": "lista cerrada"}

def type2(op):
    return {"type": op.get("type","unknown"), "epistemic": "SUGGESTED"}

def oracle_cov(blocks_covered, total):
    cov = blocks_covered/total if total else 0
    return {"cov": cov, "pass": cov>=0.8}

def prop_test(n, fn, seed=0):
    rng=random.Random(seed)
    fails=0
    for _ in range(n):
        x=rng.randint(0,2**31-1)
        if not fn(x): fails+=1
    return {"n": n, "fails": fails, "pass": fails==0}

def ledger_adapter(entry):
    return {"adapter": "separado (no toca store.py)", "entry": entry, "productive": "BLOCKED"}
