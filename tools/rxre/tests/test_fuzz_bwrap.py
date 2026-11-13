"""M592 tests (8): bwrap ok/segv/hang + aislamiento sincero."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.fuzz_bwrap import run_sandboxed, classify_sandbox

def test_01_true_ok():
    assert run_sandboxed("/bin/true", timeout=5).startswith("OK")

def test_02_segv_crash():
    r=run_sandboxed("/tmp/fuzz_segv", timeout=5); assert r.startswith("CRASH"), r

def test_03_hang_timeout():
    r=run_sandboxed("/tmp/fuzz_hang", timeout=3); assert r.startswith("HANG"), r

def test_04_classify_true():
    assert classify_sandbox("/bin/true")== "ok"

def test_05_classify_segv():
    assert classify_sandbox("/tmp/fuzz_segv")== "crash"

def test_06_classify_hang():
    assert classify_sandbox("/tmp/fuzz_hang", timeout=3)== "hang"

def test_07_no_net_flag_present():
    from tools.rxre.analysis.fuzz_bwrap import BWRAP_BASE
    assert "--unshare-net" in BWRAP_BASE and "--unshare-user" in BWRAP_BASE

def test_08_missing_bin_no_crash_hang_up():
    r=run_sandboxed("/tmp/no_existe_zzz", timeout=5)
    assert r.startswith("CRASH") or r.startswith("OK")  # no exception, clasificado

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
