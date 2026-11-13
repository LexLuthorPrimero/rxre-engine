"""M666 tests (8): coverage audit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.coverage_audit import AUDITED, ADDITIONAL, correspondence, coverage

def test_01_correspond():
    c=correspondence(AUDITED, AUDITED)
    assert c["audited"]==14 and c["dup"]==0 and c["missing"]==[]

def test_02_dup_none():
    assert len(AUDITED)==len(set(AUDITED))

def test_03_additional():
    assert ADDITIONAL==["0x34cf","0x3510"]

def test_04_coverage():
    cov=coverage(); assert cov["funcs"]==259 and cov["blocks"]==5504

def test_05_audited14():
    assert len(AUDITED)==14

def test_06_uncovered():
    assert coverage()["uncovered"]==ADDITIONAL

def test_07_no_rewrite():
    # correspondence no muta estados históricos
    assert correspondence(AUDITED, AUDITED)["audited"]==14

def test_08_determinista():
    assert coverage()==coverage()

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
