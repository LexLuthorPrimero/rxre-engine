"""M596 tests (8): in_range + OOB conservador."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.acre_mem import in_range, synthesize_mem_check

def test_01_in_range():
    assert in_range(0, 8, 16) is True

def test_02_off_gt_d():
    assert in_range(20, 1, 16) is False

def test_03_boundary_eq():
    assert in_range(8, 8, 16) is False  # R>= D-OFF => OOB

def test_04_zero_size():
    assert in_range(0, 0, 16) is True

def test_05_wrap_u64():
    # off = 2**64-1 wrap case M531
    assert in_range(2**64-1, 1, 100) is False

def test_06_synth_inrange():
    assert synthesize_mem_check(0,4,8)["verdict"]=="IN_RANGE"

def test_07_synth_oob():
    r=synthesize_mem_check(10,10,16); assert r["verdict"]=="OOB" and r["need_patch"]

def test_08_no_wrap_proof():
    # no afirmamos PROVEN general; solo modelo
    assert synthesize_mem_check(0,16,16)["verdict"]=="OOB"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
