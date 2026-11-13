"""M668 tests (8): tokenizer audit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.tokenizer_audit import describe_pattern_entry, classify_token, consumer_relation

def test_01_caller():
    assert describe_pattern_entry()["caller"]=="GEAcompile 0xd370"

def test_02_callee():
    assert "kwsprep 0xa850" in describe_pattern_entry()["callee"]

def test_03_fields():
    assert "0x948" in "".join(describe_pattern_entry()["fields_partial"]) or "0x948" in str(describe_pattern_entry())

def test_04_classify_copy():
    assert classify_token("copy_memset_xmm")=="PARTIAL (runtime byte class, no tabla transiciones)"

def test_05_classify_dfa():
    assert classify_token("dfa_transitions")=="NOT_DETERMINED"

def test_06_classify_support():
    assert classify_token("other")=="SUPPORTED (oraculo externo)"

def test_07_consumer():
    assert consumer_relation()["feeds_dfa"]=="NOT_DETERMINED"

def test_08_no_atribucion():
    # no atribuir 14 dispatch M664 al tokenizer sin conexion demostrada
    assert "NOT_DETERMINED" in consumer_relation()["literal"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
