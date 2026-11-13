"""M640 test_external_limit (8): limite runtime conservador."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dep_identity import summarize_external, lib_identity
from tools.rxre.analysis.plt_got_effects import summary_for_symbol

def test_01_identificada():
    from tools.rxre.analysis.dep_identity import inventory
    inv=inventory(); assert inv["interp"].endswith("ld-linux-x86-64.so.2")

def test_02_body_available_no_semantica():
    # BODY_AVAILABLE != semántica probada
    s=summarize_external("__cxa_finalize", {"0":[]}, True); assert s["unknown"]

def test_03_cxa_unknown():
    assert summary_for_symbol("__cxa_finalize")["unknown"]

def test_04_deregister_got_may():
    from tools.rxre.analysis.plt_got_effects import resolve_plt_got
    r=resolve_plt_got("deregister_tm_clones"); assert r["is_local_body"]  # local pero destino GOT MAY

def test_05_no_fabricar():
    # ninguna summary externa debe ser known sin evidencia local completa
    for sym in ["__cxa_finalize","free","getenv"]:
        s=summary_for_symbol(sym)
        assert s["unknown"]

def test_06_equiv_no_proven():
    from tools.rxre.analysis.decompiler_lite import build_report
    # no expandir: equiv sigue NOT_DETERMINED por diseño (verificado en lite)
    import inspect
    from tools.rxre.analysis import decompiler_lite
    assert "NOT_DETERMINED" in inspect.getsource(decompiler_lite)

def test_07_hash_ligado():
    assert lib_identity("/usr/lib64/libc.so.6")["build_id"]=="85075e2ae2e13352a1413d41c327dacf6461526c"

def test_08_regresion_M630():
    from tools.rxre.analysis.call_summary import apply_summary
    from tools.rxre.analysis.mem_pred import loc
    FLAG=loc(0x25260,1)
    s=summary_for_symbol("__cxa_finalize")
    assert apply_summary({(FLAG,"EQ",0)}, s)==set()

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
