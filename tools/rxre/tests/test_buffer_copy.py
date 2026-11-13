"""M644 tests (8): buffer copy discriminantes."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.buffer_copy import describe_read, describe_write, trace_read_write, classify_mechanism

def test_01_describe():
    assert "read" in describe_read("fd0",64,"buf") and "write" in describe_write("buf",0,10)

def test_02_reused():
    t=trace_read_write([{"buf":"heap1","size":64}], [{"buf":"heap1","offset":0,"length":64}])
    assert t["reuse"] and t["reread_propagation"]["same_buf"]

def test_03_no_reuse():
    t=trace_read_write([{"buf":"heap1","size":64}], [{"buf":"heap2","offset":0,"length":64}])
    assert not t["reuse"]

def test_04_classify_reuse():
    assert classify_mechanism(True, True, True, False)=="VAR_REUSE"

def test_05_classify_fixed():
    assert classify_mechanism(True, True, False, False)=="FIXED_REUSE"

def test_06_classify_alt():
    assert classify_mechanism(True, True, True, True)=="ALTERNATIVE_ROUTES_PARTIAL"

def test_07_classify_undetermined():
    assert classify_mechanism(False, True, False, False)=="NOT_DETERMINED"

def test_08_partial_write_candidate():
    # no demuestra mecanismo completo solo por bytes iguales (coincidencia)
    t=trace_read_write([{"buf":"heap1","size":4}], [{"buf":"heap1","offset":0,"length":4}])
    assert t["writes"][0]["length"]==4  # observación, no prueba mecanismo

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
