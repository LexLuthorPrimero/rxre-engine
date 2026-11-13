"""M672 tests (8): stride sem."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.stride_sem import FIELDS, map_accesses, classify_field

def test_01_fields():
    assert len(map_accesses())==5

def test_02_offsets_proven():
    assert classify_field("+0x10")=="PROVEN" and classify_field("+0")=="PROVEN"

def test_03_partial():
    assert classify_field("+0x15")=="SUPPORTED"

def test_04_resto_nd():
    assert classify_field("0..0x27 resto")=="NOT_DETERMINED"

def test_05_not_inferir_tipo():
    # tamaño 40 no significa tipo homogéneo
    assert "resto" in map_accesses()[-1]["offset"]

def test_06_stride40():
    assert FIELDS[0][1]=="8"

def test_07_deterministic():
    assert map_accesses()==map_accesses()

def test_08_no_dfa():
    assert all("DFA" not in d.get("op","") for d in map_accesses())

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
