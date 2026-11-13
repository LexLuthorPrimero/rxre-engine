"""M662 tests (8): table evidence."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.table_evidence import classify, searchable_regions, coverage, STATUS

def test_01_confirmed():
    assert classify(True,True,True,True)=="CONFIRMED_TABLE"

def test_02_materialized():
    assert classify(True,True,False,True)=="MATERIALIZED"

def test_03_runtime():
    assert classify(True,True,True,False)=="RUNTIME_BUILT"

def test_04_no_bytes():
    assert classify(False,True,False,True)=="INACCESSIBLE"

def test_05_regions():
    assert ".rodata" in searchable_regions()

def test_06_coverage_note():
    assert "ausencia" in coverage()

def test_07_status_map():
    assert STATUS["CONFIRMED_TABLE"]=="PROVEN" and STATUS["INACCESSIBLE"]=="NOT_DETERMINED"

def test_08_no_reconstruccion():
    # clasificar no reconstruye transiciones
    assert classify(True,True,True,True)!="RECONSTRUCTED"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
