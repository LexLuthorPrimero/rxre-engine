"""M646 tests (8): transiciones full_write vs modelo independiente."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.full_write_ref import step

def test_01_partial():
    s=step(0,100,30); assert s=={"offset":30,"remaining":70,"action":"loop","total":None}

def test_02_completa():
    s=step(30,70,70); assert s["action"]=="exit_total" and s["total"]==100

def test_03_eintr_retry():
    s=step(10,90,-1,errno=4); assert s["action"]=="retry" and s["offset"]==10

def test_04_error_no_eintr():
    s=step(10,90,-1,errno=5); assert s["action"]=="exit_partial" and s["total"]==10

def test_05_ret_cero():
    s=step(7,93,0); assert s["action"]=="exit_errno28" and s["total"]==7

def test_06_secuencia_parcial():
    o,r=0,100
    for ret in [30,40,30]:
        s=step(o,r,ret); o,r=s["offset"],s["remaining"]
    assert s["action"]=="exit_total" and s["total"]==100

def test_07_ret_larger_rem():
    st=step(0,10,15)
    # ret > rem no esperado en write real; modelo lo trata como completa (total 15) — documentado como fuera de dominio
    assert st["remaining"]==0

def test_08_no_promover_equiv():
    # ninguno de los pasos afirmas equivalencia global: solo transiciones locales
    assert step(0,5,5)["total"]==5

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
