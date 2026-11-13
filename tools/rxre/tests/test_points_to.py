"""M581 points-to tests (10): Andersen subset + alias conservador."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.points_to import anderson_subset, may_alias

def test_01_direct_assign():
    pts=anderson_subset({"a":{"stack_local(0)"}},[("assign","b","a")])
    assert pts["b"]=={"stack_local(0)"}

def test_02_transitive():
    pts=anderson_subset({"a":{"stack_local(0)"}},[("assign","b","a"),("assign","c","b")])
    assert pts["c"]=={"stack_local(0)"}

def test_03_distinct_no_alias():
    pts=anderson_subset({"a":{"stack_local(0)"},"b":{"stack_local(8)"}},[])
    assert not may_alias(pts,"a","b")

def test_04_same_alloc_alias():
    pts=anderson_subset({"a":{"heap_alloc(0)"},"b":{"heap_alloc(0)"}},[])
    assert may_alias(pts,"a","b")

def test_05_load_propagates():
    pts=anderson_subset({"p":{"stack_local(0)"}},[("load","x","p")])
    assert pts["x"]=={"stack_local(0)"}

def test_06_store_union():
    pts=anderson_subset({"p":{"stack_local(0)"},"v":{"heap_alloc(1)"}},[("store","p","v")])
    assert "heap_alloc(1)" in pts["stack_local(0)*"]

def test_07_empty_stays_empty():
    pts=anderson_subset({},[("assign","a","b")])
    assert pts.get("a",set())==set()

def test_08_union_merge():
    pts=anderson_subset({"a":{"stack_local(0)"},"b":{"stack_local(8)"}},[("assign","c","a"),("assign","c","b")])
    # c union both via two assigns (second overwrites? we union semantics: keep both by init)
    # our impl unions both: pts[c] accumulates
    assert "stack_local(0)" in pts["c"] and "stack_local(8)" in pts["c"]

def test_09_func_ptr():
    pts=anderson_subset({"f":{"func(helper)"}},[("assign","g","f")])
    assert pts["g"]=={"func(helper)"}

def test_10_no_false_proven():
    # points-to es sobre-aproximación: no afirma no-alias sin pts
    pts=anderson_subset({"a":{"stack_local(0)"}},[])
    assert pts["a"]=={"stack_local(0)"}
    assert may_alias(pts,"a","a")

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
