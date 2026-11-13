"""M583 ACRE tests (10): generador acotado + oráculo trivial."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.acre import synthesize_const_patch, oracle_trivial

def test_01_no_change():
    r=synthesize_const_patch(b"\x90\x90",0,b"\x90\x90"); assert r["ok"] and r["diffs"]==[]

def test_02_one_byte():
    r=synthesize_const_patch(b"\x90\xeb",0,b"\x90\x90"); assert r["ok"] and len(r["diffs"])==1

def test_03_len_mismatch():
    r=synthesize_const_patch(b"\x90",0,b"\x90\x90"); assert not r["ok"]

def test_04_too_many_bytes_rejected():
    r=synthesize_const_patch(b"\xff"*6,0,b"\x00"*6); assert not r["ok"]

def test_05_two_bytes_ok():
    r=synthesize_const_patch(b"\x00\x00",5,b"\x01\x02"); assert r["ok"] and len(r["diffs"])==2

def test_06_oracle_accepts_known():
    p=synthesize_const_patch(b"\x00",0,b"\x01")
    assert oracle_trivial(p, lambda d: d[0]["new"]==1)

def test_07_oracle_rejects_unknown():
    p=synthesize_const_patch(b"\x00",0,b"\x02")
    assert not oracle_trivial(p, lambda d: d[0]["new"]==1)

def test_08_offsets_preserved():
    r=synthesize_const_patch(b"\xaa\xbb",0x1000,b"\xaa\xcc")
    assert r["diffs"][0]["off"]==0x1001

def test_09_four_bytes_boundary():
    r=synthesize_const_patch(b"\x00"*4,0,b"\x01"*4); assert r["ok"] and len(r["diffs"])==4

def test_10_five_bytes_boundary():
    r=synthesize_const_patch(b"\x00"*5,0,b"\x01"*5); assert not r["ok"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
