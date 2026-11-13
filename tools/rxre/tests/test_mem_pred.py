"""M629 test_mem_pred (10): byte flag, fn ptr, store disjoint, store alias, join eq/neq, width, unresolved."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.mem_pred import loc, same, overlap, prop_predicate, holds

FLAG = loc(0x25260, 1)
FNPTR = loc(0x24fe8, 8)

def _run(blocks, events):
    succ={b["id"]:[str(o) for o in b["out_nodes"]] for b in blocks}
    from tools.rxre.analysis.ssa import build_graph
    # build_graph expects ids str
    _, pred, ids = build_graph(blocks)
    IN, OUT = prop_predicate(succ, pred, "0", ids, events)
    return IN, OUT

def test_01_byte_flag_pred():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    IN,OUT=_run(blocks, {"0":[("load",FLAG,"EQ",0)]})
    assert holds(OUT["0"], FLAG, "EQ", 0)

def test_02_fnptr_pred():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    IN,OUT=_run(blocks, {"0":[("load",FNPTR,"EQ",0)]})
    assert holds(OUT["0"], FNPTR, "EQ", 0)

def test_03_store_disjoint_preserves():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    OTHER=loc(0x30000,1)
    IN,OUT=_run(blocks, {"0":[("load",FLAG,"EQ",0),("store",OTHER,1)]})
    assert holds(OUT["0"], FLAG, "EQ", 0)

def test_04_store_alias_invalidates():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    IN,OUT=_run(blocks, {"0":[("load",FLAG,"EQ",0),("store",FLAG,1)]})
    assert not holds(OUT["0"], FLAG, "EQ", 0) and holds(OUT["0"], FLAG, "EQ", 1)

def test_05_join_same():
    blocks=[{"id":"0","offset":0,"out_nodes":["1","2"]},{"id":"1","offset":16,"out_nodes":["3"]},{"id":"2","offset":32,"out_nodes":["3"]},{"id":"3","offset":48,"out_nodes":[]}]
    events={"0":[("load",FLAG,"EQ",0)],"1":[],"2":[]}
    IN,OUT=_run(blocks, events)
    assert holds(OUT["0"], FLAG, "EQ", 0) and holds(OUT["3"], FLAG, "EQ", 0)

def test_06_join_different():
    blocks=[{"id":"0","offset":0,"out_nodes":["1","2"]},{"id":"1","offset":16,"out_nodes":["3"]},{"id":"2","offset":32,"out_nodes":["3"]},{"id":"3","offset":48,"out_nodes":[]}]
    events={"0":[],"1":[("load",FLAG,"EQ",0)],"2":[("load",FLAG,"EQ",1)]}
    IN,OUT=_run(blocks, events)
    # join intersect: ninguno sobrevive
    assert not holds(OUT["3"], FLAG, "EQ", 0) and not holds(OUT["3"], FLAG, "EQ", 1)

def test_07_width_diff_invalidates():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    # load byte, store qword solapada -> invalida conservador
    IN,OUT=_run(blocks, {"0":[("load",FLAG,"EQ",0),("store",loc(0x25260,8),1)]})
    assert not holds(OUT["0"], FLAG, "EQ", 0)

def test_08_unresolved_alias_conservative():
    blocks=[{"id":"0","offset":0,"out_nodes":[]}]
    # call invalida todo
    IN,OUT=_run(blocks, {"0":[("load",FLAG,"EQ",0),("call",)]})
    assert OUT["0"]==set()

def test_09_call_ret_stale():
    # CALL/RET no inventa pred: tras call, OUT vacío
    blocks=[{"id":"0","offset":0,"out_nodes":["1"]},{"id":"1","offset":16,"out_nodes":[]}]
    events={"0":[("load",FNPTR,"NE",0)],"1":[("call",)]}
    IN,OUT=_run(blocks, events)
    assert OUT["1"]==set()

def test_10_no_proven_by_default():
    # join con rama vacía no afirma PROVEN (conservador intersect)
    blocks=[{"id":"0","offset":0,"out_nodes":["1","2"]},{"id":"1","offset":16,"out_nodes":["3"]},{"id":"2","offset":32,"out_nodes":["3"]},{"id":"3","offset":48,"out_nodes":[]}]
    events={"0":[],"1":[("load",FLAG,"EQ",0)],"2":[]}
    IN,OUT=_run(blocks, events)
    assert OUT["3"]==set()  # no afirma

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
