"""M638 test_foci_causal (8): matriz causal."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.foci_causal import classify_loss, recoverability

def test_01_stub_externa():
    assert classify_loss("external_stub", True, True, False, False)=="EXTERNAL_DEPENDENCY"

def test_02_limite_instrumental():
    assert classify_loss("limit_mega", True, False, False, True)=="LOCAL_ANALYZER_LIMITATION"

def test_03_limite_ambiguo():
    assert classify_loss("limit_mega", False, False, True, False)=="AMBIGUOUS_STRUCTURE"

def test_04_indirect_externo():
    assert classify_loss("indirect_got", True, True, False, False)=="EXTERNAL_DEPENDENCY"

def test_05_indirect_insufficient():
    assert classify_loss("indirect_got", False, False, False, False)=="INSUFFICIENT_EVIDENCE"

def test_06_invalid_input():
    assert classify_loss("other", False, False, False, True)=="INVALID_INPUT"

def test_07_recover_no_externa():
    assert recoverability("EXTERNAL_DEPENDENCY")=="NO"

def test_08_recover_yes_limit():
    assert recoverability("LOCAL_ANALYZER_LIMITATION")=="YES"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
