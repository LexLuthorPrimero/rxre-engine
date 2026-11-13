"""M651 tests (8): close check."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.close_check import summary_close, route_normal, route_write_fail

def test_01_flush_not_determined():
    assert summary_close(0,0)["flush"]=="NOT_DETERMINED (FILE* libc)"

def test_02_close_fail():
    assert summary_close(0,1)["close_fail"]=="fail_output@514d"

def test_03_close_ok():
    assert summary_close(0,0)["close_fail"]=="continue"

def test_04_order():
    assert "4dff" in summary_close(0,0)["order"]

def test_05_normal_route():
    assert route_normal()["exit"]=="0" and route_normal()["status"]=="LOCAL"

def test_06_write_fail_route():
    assert route_write_fail()["route"]=="fail_output@0x4f43"

def test_07_flush_separate_close():
    # no convertir flush ret en cierre probado
    s=summary_close(1,0)
    assert s["close_fail"]=="continue"

def test_08_no_equiv():
    assert summary_close(None,None)["flush"]=="NOT_DETERMINED (FILE* libc)"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
