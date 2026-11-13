"""M653 tests (8): composición exit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.exit_summary import summary_exit, rule_exit

def test_01_normal():
    s=summary_exit(False,0,0,1); assert s["exit"]==0 and s["priority"]=="resultado tee_files"

def test_02_write_fail():
    s=summary_exit(True,0,0,0); assert "fail_output" in s["errors"][0]

def test_03_close_fail():
    s=summary_exit(False,0,1,1); assert s["exit"]==1 and "fail" in s["cleanup"]

def test_04_rule():
    assert rule_exit(1,0)==0 and rule_exit(0,0)==1 and rule_exit(1,1)==1

def test_05_libc_nd():
    assert "NOT_DETERMINED" in summary_exit(False,0,0,1)["libc"]

def test_06_priority_write_over_close():
    s=summary_exit(True,0,1,0); assert s["priority"]=="write fail"  # write domina

def test_07_compose_no_duplicate():
    # integración solo combina, no codifica otra evidencia
    s=summary_exit(False,0,0,1); assert s["exit"]==0

def test_08_wrap():
    assert rule_exit(255,0)==254

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
