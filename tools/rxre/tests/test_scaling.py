"""E1-E4 tests (14): 2 por subfase acotada."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.scaling import anderson_flow, mem_use_def, summary, alias_trace, ir_nway, flags_model, sse_fp, syscall_allow, type2, oracle_cov, prop_test, ledger_adapter

def test_01_anderson_flow():
    pts=anderson_flow({"a":{"stack_local(0)"}},[("assign","b","a")]); assert pts["b"]=={"stack_local(0)"}
def test_02_mem_use_def():
    assert mem_use_def({"s0":"use","s1":"def"})["use"]=={"s0"}
def test_03_summary():
    assert summary("f",["g"])["n_calls"]==1
def test_04_alias_trace():
    r=alias_trace({"a":{"x"}},"a","a"); assert r["may_alias"] is True
def test_05_ir_nway():
    blocks=[{"id":"S","ops":[("MOV",("r",1)),("RET",())]}]; assert ir_nway(blocks,"S",{})["ok"] is True
def test_06_flags():
    assert flags_model(1,1)["ZF"]==1 and flags_model(1,2)["CF"]==1
def test_07_sse():
    assert sse_fp(2,3,"add")["res"]==5
def test_08_syscall():
    assert syscall_allow("exit")["allow"] and not syscall_allow("ptrace")["allow"]
def test_09_type2():
    assert type2({"type":"i64"})["epistemic"]=="SUGGESTED"
def test_10_oracle_cov():
    assert oracle_cov(9,10)["pass"] and not oracle_cov(7,10)["pass"]
def test_11_prop_test():
    assert prop_test(100, lambda x: 0<=x<2**31)["pass"]
def test_12_ledger_adapter():
    assert ledger_adapter("e")["productive"]=="BLOCKED"
def test_13_flow_order():
    pts=anderson_flow({"a":{"stack_local(0)"}},[("assign","b","a"),("assign","c","b")]); assert pts["c"]=={"stack_local(0)"}
def test_14_no_proven_claim():
    assert flags_model(0,0)["epistemic"]=="subset NOT_DETERMINED"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{14-fails}/14 PASS"); sys.exit(1 if fails else 0)
