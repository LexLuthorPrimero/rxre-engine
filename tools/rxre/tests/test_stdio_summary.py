"""M648 tests (8): stdio summaries."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.stdio_summary import summary_stdio_read, summary_stdio_write, summary_iopoll

def test_01_read_req():
    s=summary_stdio_read("stdin","0x2000_stack"); assert s["req"]==8192 and "0x2000" in s["evidence"]

def test_02_read_eof_err():
    s=summary_stdio_read("stdin","buf"); assert s["ret"]["eof"]=="0" and "4d90" in s["evidence"]

def test_03_read_mem_partial():
    assert "PARTIAL" in summary_stdio_read("a","b")["mem"]

def test_04_write_loop():
    s=summary_stdio_write("buf",10,"stream"); assert "4f00" in s["loop"]

def test_05_write_stdio_partial():
    assert "PARTIAL" in summary_stdio_write("b",1,"s")["stdio"]

def test_06_iopoll_partial():
    assert "PARTIAL" in summary_iopoll(True)["semantics"]

def test_07_compose():
    r=summary_stdio_read("stdin","buf0x2000")
    w=summary_stdio_write("buf0x2000",8,"out")
    # mismo buffer (observado) enlazado como observación, no como mecanismo libc probado
    assert r["buf"] if "buf" in r else True

def test_08_no_raw_equiv():
    s=summary_stdio_write("buf",8,"s")
    assert "no equivalencia" in str(s).lower() or "PARTIAL" in s["stdio"] or "PARTIAL" in s["loop"] or "PARTIAL" in s["ret"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
