"""M671 tests (8): dependency audit."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dependency_audit import classify_dep, stride5, coverage_graph

def test_01_internal():
    assert classify_dep("execute_program")=="INTERNAL"

def test_02_libc():
    assert classify_dep("fwrite_unlocked")=="LIBC"

def test_03_external():
    assert classify_dep("sym.imp.mbrtowc")=="EXTERNAL"

def test_04_indirect():
    assert classify_dep("jmp rax unknown")=="INDIRECT_UNKNOWN"

def test_05_stride40():
    assert stride5()["stride_bytes"]==40

def test_06_stride_nd():
    assert stride5()["semantics"].startswith("NOT_DETERMINED")

def test_07_coverage():
    cov=coverage_graph(); assert cov["total_calls"]==114

def test_08_producer():
    assert "arg1+0x10" in stride5()["producer"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
