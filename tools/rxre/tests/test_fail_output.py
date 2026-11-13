"""M650 tests (8): fail_output routes."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.fail_output import summary_fwrite_fail, summary_flush_fail, summary_close_fail, summary_full

def test_01_fwrite_fail():
    assert summary_fwrite_fail(-1,5)["route"]=="fail_output"

def test_02_fwrite_ok():
    assert summary_fwrite_fail(10,0)["route"]=="continue"

def test_03_flush():
    assert summary_flush_fail(0)["route"]=="retry_or_error"

def test_04_close_fail():
    assert summary_close_fail(1)["route"]=="fail_output@514d"

def test_05_close_ok():
    assert summary_close_fail(0)["route"]=="continue"

def test_06_full_local():
    s=summary_full(); assert s["fail_output_local"].startswith("0x4a30") and s["status"]=="PARTIAL_LOCAL"

def test_07_libc_not_determined():
    assert summary_flush_fail(1)["libc"]=="NOT_DETERMINED"

def test_08_no_raw_equiv():
    # no expandir a equivalencia global
    assert summary_fwrite_fail(None,0)["route"]=="NOT_DETERMINED"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
