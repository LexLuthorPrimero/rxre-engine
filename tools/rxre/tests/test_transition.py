"""M663 tests (8): transition audit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.transition_audit import layout_stack, classify_indirect, relations_got, verdict

def test_01_layout_size():
    assert "0x948" in layout_stack()["buf_size"]

def test_02_layout_init():
    assert "0xa8c3" in layout_stack()["writes"] and "min" in layout_stack()["init_byte"]

def test_03_indirect_limits():
    assert classify_indirect(5,0x1000,True,True)=="FINITE_TARGET_SET"

def test_04_indirect_no_limits():
    assert classify_indirect(1,0x1000,False,True)=="UNKNOWN"

def test_05_indirect_no_consumer():
    assert classify_indirect(1,0x1000,True,False)=="MAY_TARGET"

def test_06_rels():
    assert relations_got()[0]["status"].startswith("UNKNOWN")

def test_07_verdict_partial():
    assert verdict().startswith("PASS_PARTIAL")

def test_08_no_reconstruccion():
    assert "0x948" in layout_stack()["buf_size"] and "char-class" in layout_stack()["semantics"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
