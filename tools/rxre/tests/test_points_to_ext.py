"""M595 tests (8): field-sensitivity + heap summary."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.points_to_ext import anderson_field, heap_summary

def test_01_field_store_load():
    pts=anderson_field({"v":{"heap_alloc(0)"}},[("store_field","b",8,"v"),("assign_field","x","b",8)])
    assert pts["x"]=={"heap_alloc(0)"}

def test_02_field_distinct_off():
    pts=anderson_field({"v":{"heap_alloc(0)"},"w":{"heap_alloc(1)"}},[("store_field","b",0,"v"),("store_field","b",8,"w")])
    assert pts["b.0*"]=={"heap_alloc(0)"} and pts["b.8*"]=={"heap_alloc(1)"}

def test_03_no_cross_off():
    pts=anderson_field({"v":{"heap_alloc(0)"}},[("store_field","b",0,"v"),("assign_field","x","b",8)])
    assert pts.get("x",set())==set()

def test_04_heap_summary_collapse():
    assert heap_summary(10)=={"heap_alloc[*]"}

def test_05_heap_summary_keep():
    assert heap_summary(2)=={"heap_alloc(0)","heap_alloc(1)"}

def test_06_base_m581_intact():
    from tools.rxre.analysis.points_to import anderson_subset
    pts=anderson_subset({"a":{"stack_local(0)"}},[("assign","b","a")])
    assert pts["b"]=={"stack_local(0)"}

def test_07_conservative_union():
    pts=anderson_field({"v":{"heap_alloc(0)"},"w":{"heap_alloc(1)"}},[("store_field","b",0,"v"),("store_field","b",0,"w")])
    assert pts["b.0*"]=={"heap_alloc(0)","heap_alloc(1)"}

def test_08_no_false_noalias():
    pts=anderson_field({"v":{"heap_alloc(0)"}},[("store_field","b",0,"v")])
    assert "heap_alloc(0)" in pts["b.0*"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
