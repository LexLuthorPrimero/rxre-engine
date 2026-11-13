"""M664 tests (8): index trace."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.index_trace import table, classify, proven_count

def test_01_rows():
    assert len(table())==14

def test_02_all_finite():
    assert proven_count()==14

def test_03_sites():
    sites=[r["site"] for r in table()]
    assert "0x18e0" in sites and "0x1cdf3" in sites

def test_04_no_inventado():
    # classify nunca promueve sin guard
    assert classify("UNKNOWN")=="UNKNOWN"

def test_05_guard_presente():
    assert all(r["guard"] for r in table())

def test_06_dest_form():
    assert all(r["dest"]=="dest=base+off" for r in table())

def test_07_kwsprep_sin_relacion():
    # ninguna fila reclama relación con kwsprep (0x948) — sitio distinto
    assert all("kwsprep" not in r["base"] for r in table())

def test_08_deterministic():
    assert table()==table()

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
