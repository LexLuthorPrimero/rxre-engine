"""M645 tests (8): summaries read/write."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.rw_summary import summary_read, summary_full_write, summary_copy_range

def test_01_read_ret():
    s=summary_read("fd>=0",("fd0","buf",64),"len>0","0 bytes","-1")
    assert s["ret"]["eof"]=="0 bytes" and s["check"]=="__read_chk"

def test_02_full_write_loop():
    s=summary_full_write("heap",100); assert "loop" in s and "EINTR" in s["loop"]

def test_03_composicion():
    # M644 buffer heap + read ret len -> full_write len mismo len
    r=summary_read("fd>=0",("fd","heap",64),64,"0","-1")
    w=summary_full_write("heap",64)
    assert r["args"][1]==w["buf"] and r["ret"]["pos"]==64 and w["len"]==64

def test_04_alias_sigue_partial():
    s=summary_read("fd>=0",("fd","heap",64))
    assert "PARTIAL" in s["mem"]

def test_05_copy_range_partial():
    s=summary_copy_range("a","b",100); assert s["status"].startswith("PARTIAL")

def test_06_eof_correcto():
    s=summary_read("fd>=0",("fd","buf",10),10,"0 bytes","-1"); assert s["ret"]["eof"]=="0 bytes"

def test_07_error_correcto():
    s=summary_read("fd>=0",("fd","buf",10),10,"0 bytes","-1"); assert s["ret"]["err"]=="-1"

def test_08_no_oraculo_propio():
    # summary no se usa como oráculo: test usa valores fijos (no invoca summary para generar esperado sin leer dict)
    s=summary_full_write("heap",10)
    assert s["len"]==10  # dato literal, no derivado del módulo

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
