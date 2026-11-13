"""M616-M623 tests (16): 2 por margen."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.scaling2 import andersen_path, heap_alias, ir_recursion, ir_indirect, acre_heap_synth, oracle_broader, prop_test_1000, fuzz_dedup

def test_01_path_assign(): assert andersen_path({"a":{"x"}},[("assign","b","a")])["b"]=={"x"}
def test_02_path_bound(): assert len(andersen_path({"a":{"x"}},[("assign",f"v{i}","a") for i in range(30)]))<=31
def test_03_heap_live(): r=heap_alias([("alloc","h1"),("store","h1","v")]); assert "h1" in r["live"]
def test_04_heap_free(): r=heap_alias([("alloc","h1"),("free","h1")]); assert r["live"]==set()
def test_05_ir_rec_ok(): assert ir_recursion([{"id":"A","ops":[("RET",())]}],"A",{},depth=2)["ok"] is True
def test_06_ir_rec_depth(): assert ir_recursion([{"id":"A","ops":[("RET",())]}],"A",{},depth=-1)["ok"] is False
def test_07_ir_indirect(): assert set(ir_indirect(["f1","f2"])["targets"])=={"f1","f2"}
def test_08_ir_indirect_epi(): assert ir_indirect(["f1"])["epistemic"].startswith("MAY")
def test_09_acre_inrange(): assert acre_heap_synth(16,[True,True])["verdict"]=="IN_RANGE"
def test_10_acre_oob(): assert acre_heap_synth(16,[True,False])["verdict"]=="OOB"
def test_11_oracle_pass(): assert oracle_broader(9,10)["pass"] is True
def test_12_oracle_fail(): assert oracle_broader(7,10)["pass"] is False
def test_13_prop1000_pass(): assert prop_test_1000(lambda x: True)["pass"] is True
def test_14_prop1000_fail(): assert prop_test_1000(lambda x: x<100, seed=1)["pass"] is False
def test_15_dedup_unique(): assert fuzz_dedup(["a","b","a"])["unique"]==2
def test_16_dedup_count(): assert fuzz_dedup([])=={"raw":0,"unique":0,"ids":[]}

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{16-fails}/16 PASS"); sys.exit(1 if fails else 0)
