"""M597 tests (8): width suggestion + NOT_DETERMINED."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dataflow import decode_function
from tools.rxre.analysis.type_rec import infer_width

def test_01_i64():
    ins=decode_function(bytes.fromhex("48 89 d8"),0x1000)
    assert infer_width(ins)["width"]=="i64"

def test_02_i32():
    ins=decode_function(bytes.fromhex("89 d8"),0x1000)
    assert infer_width(ins)["width"]=="i32"

def test_03_epistemic():
    ins=decode_function(bytes.fromhex("48 89 d8"),0x1000)
    assert infer_width(ins)["epistemic"].startswith("SUGGESTED")

def test_04_empty():
    assert infer_width([])["width"]=="i32"

def test_05_nop():
    ins=decode_function(bytes.fromhex("90"),0x1000)
    assert infer_width(ins)["width"]=="i32"

def test_06_no_proven():
    ins=decode_function(bytes.fromhex("48 89 d8"),0x1000)
    assert infer_width(ins)["width"]!="PROVEN"

def test_07_deterministic():
    ins=decode_function(bytes.fromhex("48 89 d8"),0x1000)
    assert infer_width(ins)==infer_width(ins)

def test_08_two_regs():
    ins=decode_function(bytes.fromhex("48 89 d8 48 89 c1"),0x1000)
    assert infer_width(ins)["width"]=="i64"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
