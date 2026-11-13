"""M673 tests (8): matriz transferencia."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.transfer import SUBJECTS, matrix, coverage_counts

def test_01_subjects():
    assert SUBJECTS==["ls","true","cat","tee","grep","sed"]

def test_02_cfg_transfer():
    assert matrix()["CFG"]["sed"]=="TRANSFERRED"

def test_03_grep_partial():
    assert matrix()["grep_finite_vs_DFA"]["grep"].startswith("PARTIAL")

def test_04_sed_nd():
    assert "NOT_DETERMINED" in matrix()["sed_stride"]["sed"]

def test_05_tee_specific():
    assert matrix()["IO"]["tee"]=="SUBJECT_SPECIFIC"

def test_06_no_universal():
    m=matrix()
    assert all(v!="PROVEN" for cap in m.values() for v in ([cap] if isinstance(cap,str) else cap.values()))

def test_07_coverage():
    c=coverage_counts(); assert c["subjects"]==6

def test_08_deterministic():
    assert matrix()==matrix()

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
