"""M639 tests (8): dep identity + external effects."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dep_identity import inventory, lib_identity, summarize_external

def test_01_needed():
    inv=inventory(); assert "libc.so.6" in inv["needed"] and "libselinux.so.1" in inv["needed"]

def test_02_interp():
    inv=inventory(); assert "ld-linux" in inv["interp"]

def test_03_buildid():
    inv=inventory(); assert len(inv["build_id"])>=10

def test_04_libc_identity():
    idn=lib_identity("/usr/lib64/libc.so.6"); assert len(idn["sha"])==64 and idn["compat"]

def test_05_selinux():
    idn=lib_identity("/lib64/libselinux.so.1"); assert idn["compat"]

def test_06_external_unknown():
    s=summarize_external("__cxa_finalize", None, False); assert s["unknown"]

def test_07_body_existe_pero_unknown():
    # aunque cuerpo existe, runtime no modelado => unknown
    s=summarize_external("__cxa_finalize", {"0":[]}, True); assert s["unknown"]

def test_08_no_promote():
    # una resolución no promueve todos stubs misma lib
    from tools.rxre.analysis.plt_got_effects import summary_for_symbol
    assert summary_for_symbol("__cxa_finalize")["unknown"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
