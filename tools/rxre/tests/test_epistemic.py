"""M657 tests (8): calibración acotada."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.epistemic import select_sample, classify_result, metrics

SAMPLE=[
    {"id":"true_exit","state":"SUPPORTED","evidence":"M642 trace","oracle":"shell rc","producer":"decompiler-lite","oracle_component":"os"},
    {"id":"cat_copy","state":"SUPPORTED","evidence":"M643 P1-P5","oracle":"shell bytes","producer":"decompiler-lite","oracle_component":"os"},
    {"id":"full_write","state":"PROVEN","evidence":"M646 objdump","oracle":"modelo independiente","producer":"full_write_ref","oracle_component":"objdump"},
    {"id":"finiopt","state":"PARTIAL","evidence":"M628 H1","oracle":"guard GDB","producer":"decompiler-lite","oracle_component":"gdb"},
    {"id":"cxa_effect","state":"NOT_DETERMINED","evidence":"M639 deps","oracle":"NO-DISPONIBLE","producer":"plt_got","oracle_component":"ninguno"},
]

def test_01_sample():
    assert len(select_sample(SAMPLE))==4  # cxa excluido (sin oráculo)

def test_02_independencia():
    s=select_sample(SAMPLE)
    assert all(c["producer"]!=c["oracle_component"] for c in s)

def test_03_confirmed():
    assert classify_result("PROVEN","confirms")=="CONFIRMED"

def test_04_refuted():
    assert classify_result("PROVEN","refutes")=="REFUTED"

def test_05_unresolved():
    assert classify_result("NOT_DETERMINED","no_says")=="UNRESOLVED"

def test_06_metrics():
    res=[("PROVEN","CONFIRMED"),("PROVEN","REFUTED"),("NOT_DETERMINED","UNRESOLVED")]
    m=metrics(res); assert m["proven_confirmed"]=="1/2" and m["notd_unresolved"]=="1/1"

def test_07_empty():
    assert metrics([])["denominator"]==0

def test_08_no_rewrite():
    # revalidación no reescribe estado histórico (classify no muta)
    orig=SAMPLE[0]["state"]
    _=classify_result(orig,"confirms")
    assert SAMPLE[0]["state"]==orig

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
