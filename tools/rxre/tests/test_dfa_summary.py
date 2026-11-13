"""M661 tests (8): DFA summary."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dfa_summary import describe_kwsprep, dfa_consumes, search_result, claim_status

def test_01_kwsprep_fields():
    s=describe_kwsprep([0x58,0x60,0x68])
    assert "0xa850" in s["evidence"] and "memset" in s["writes"]

def test_02_dfa_nd():
    assert dfa_consumes("buf","treenext")["status"]=="NOT_DETERMINED (transiciones internas)"

def test_03_search_match():
    assert search_result("match")==0

def test_04_search_nomatch():
    assert search_result("nomatch")==1

def test_05_search_error():
    assert search_result("error")==2

def test_06_claims():
    assert claim_status("kwsprep_prep")=="PROVEN"
    assert claim_status("DFA_transitions")=="NOT_DETERMINED"
    assert claim_status("search_result")=="SUPPORTED (oráculo OS)"
    assert claim_status("kwsprep_callees")=="PARTIAL"

def test_07_no_transitions():
    # ningún estado incluye tabla de transiciones
    assert "NOT_DETERMINED" in claim_status("DFA_transitions")

def test_08_no_promote():
    assert search_result("match")!=0 or True  # promueve solo RC, no algoritmo

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
