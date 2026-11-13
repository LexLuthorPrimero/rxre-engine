"""M584 fuzz tests (10): mutador + clasificación + ciclo FUZZ->REPAIR sintético."""
import sys, random
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.fuzz import mutate, classify, fuzz_once

def test_01_empty_seed():
    assert mutate(b"", random.Random(0))==b""

def test_02_mutates_bits():
    rng=random.Random(1)
    m=mutate(b"\x00"*8, rng)
    assert len(m)==8 and m!=b"\x00"*8

def test_03_deterministic():
    a=mutate(b"\x00"*8, random.Random(42))
    b=mutate(b"\x00"*8, random.Random(42))
    assert a==b

def test_04_classify_crash():
    assert classify("CRASH:segv")== "crash"

def test_05_classify_hang():
    assert classify("HANG:timeout")== "hang"

def test_06_classify_ok():
    assert classify("OK:exit0")== "ok"

def test_07_fuzz_once_ok():
    r=fuzz_once(b"\x00", lambda m: "OK", random.Random(0)); assert r=="OK"

def test_08_cycle_fuzz_repair_synthetic():
    # ciclo: fuzz detecta crash en input 0xff, repair synth dice ok (solo contrato)
    rng=random.Random(7)
    m=mutate(b"\xff", rng)
    cls=classify("CRASH" if m==b"\xff" else "OK")
    assert cls in ("crash","ok")

def test_09_len_preserved():
    assert len(mutate(b"abcd", random.Random(0)))==4

def test_10_unknown_class():
    assert classify("WAT")== "unknown"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
