"""M652 tests (8): result_code."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.result_code import derive

def test_01_normal():
    assert derive(1,0)["exit"]==0

def test_02_tee_fail():
    assert derive(0,0)["exit"]==1

def test_03_close_fail():
    assert derive(1,1)["exit"]==1 and "fail" in derive(1,1)["path"]

def test_04_path_normal():
    assert derive(1,0)["path"]=="xor1 0x127b movzbl"

def test_05_close_fail_path():
    assert derive(1,2)["exit"]==1 and derive(1,2)["tee_ret"]==1

def test_06_no_inferir():
    # exit code 0 no demuestra flush persistente (sin equivalencia)
    assert derive(1,0)["exit"]==0

def test_07_deterministic():
    assert derive(1,0)==derive(1,0)

def test_08_wrapped():
    assert derive(255,0)["exit"]==254  # xor+mask

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
