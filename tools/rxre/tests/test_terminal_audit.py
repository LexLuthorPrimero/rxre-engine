"""M659 tests (8): terminal audit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.terminal_audit import audit_subject, audit_test, check_no_promotion, categorize

def test_01_ls_hash():
    assert audit_subject("/usr/bin/ls","54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c")["ok"]

def test_02_true_hash():
    assert audit_subject("/usr/bin/true","b639fd49da0eeaffe498316c9788a081d41d2e009d343f8e75d7e5a219e82921")["ok"]

def test_03_cat_hash():
    assert audit_subject("/usr/bin/cat","73f19135b6cfb36142a19345557c48bdcc7d0d3b414b745be86e4458dfe5845b")["ok"]

def test_04_tee_hash():
    assert audit_subject("/usr/bin/tee","8b82974253a38c0dec81207af4258feaf46d019cccb1f040d52e04370e1cc5c9")["ok"]

def test_05_tests_exist():
    assert audit_test("/home/lucas/Escritorio/rxre/tools/rxre/tests/test_jump_tables.py")["exists"]

def test_06_no_promotion():
    assert check_no_promotion("/home/lucas/Escritorio/rxre/tools/rxre/analysis/decompiler_lite.py")

def test_07_categorize():
    c=categorize()
    assert c["traceability"]=="CONSISTENT" and c["promotions"]=="NONE"

def test_08_limits():
    c=categorize()
    assert "LIBC" in c["open_limits"] and "EQUIV" in c["open_limits"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
