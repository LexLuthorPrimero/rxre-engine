"""M634 tests (8): cobertura sintética + M633 277/61."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.cfg_coverage import classify_absence, metrics_from_aflj

def test_01_classify():
    assert classify_absence({"name":"sym.imp.foo","size":10,"nbbs":2})=="DATA_FUERA_FUNCION"
    assert classify_absence({"name":"big","size":99999,"nbbs":500})=="LIMITES_FUNCION"

def test_02_metrics_func_cov():
    funcs=[{"name":"a","size":100,"nbbs":5,"edges":10},{"name":"b","size":200,"nbbs":8,"edges":16}]
    m=metrics_from_aflj(funcs)
    assert m["func_cov"]=="2/2=1.000" and m["sum_reconciled"] is True

def test_03_no_promote():
    # arista candidata no cuenta como demostrada: indirect_sites resta
    funcs=[{"name":"a","size":100,"nbbs":1,"edges":1}]
    m=metrics_from_aflj(funcs, indirect_sites=1)
    assert m["edge_cov"]=="0/1=0.000"

def test_04_todo_determinista():
    funcs=[{"name":"a","size":10,"nbbs":2,"edges":3}]
    assert metrics_from_aflj(funcs)==metrics_from_aflj(funcs)

def test_05_reconcilia():
    funcs=[{"name":"sym.imp.x","size":10,"nbbs":2,"edges":2},{"name":"big","size":99999,"nbbs":500,"edges":800}]
    m=metrics_from_aflj(funcs); assert m["sum_reconciled"] is True and set(m["dist"])>= {"DATA_FUERA_FUNCION","LIMITES_FUNCION"}

def test_06_fallo_no_desaparece():
    funcs=[{"name":"f","size":0,"nbbs":0,"edges":0}]
    m=metrics_from_aflj(funcs); assert m["func_cov"]=="0/1=0.000"

def test_07_M633_no_doble():
    # 277 entradas vs 61 dests distintos, no confundir
    m=metrics_from_aflj([{"name":"a","size":100,"nbbs":1,"edges":1}])
    assert "61" in m["indirect_cov"] and "277" in m["indirect_cov"]

def test_08_provenance():
    m=metrics_from_aflj([])
    assert "aflj" in m["provenance"] and "objdump" in m["provenance"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
