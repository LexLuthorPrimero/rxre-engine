"""M649 tests (8): flush propagation."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.flush_prop import graph_edges, propagate, failure_chain

def test_01_edges():
    es=graph_edges(); assert any(e["from"].startswith("fwrite") for e in es) and len(es)==7

def test_02_err_js():
    assert propagate(-1,0)=="error_path"

def test_03_zero_iopoll():
    assert propagate(0,0)=="iopoll_continue"

def test_04_pos_progress():
    assert propagate(10,0)=="loop_progress"

def test_05_chain_write():
    assert "fail_output" in failure_chain("write")

def test_06_chain_flush():
    assert "NOT_DETERMINED" in failure_chain("flush")

def test_07_not_equiv():
    assert propagate(None,0)=="NOT_DETERMINED"

def test_08_loop_retry():
    assert any(e["to"]=="loop_4f00" for e in graph_edges())

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
