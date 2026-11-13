"""M590 tests (10): scout end-to-end acotado."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.patch_scout import scout_cycle

def test_01_no_change():
    r=scout_cycle(b"\x90",b"\x90"); assert r["applied"] and r["oracle"] and r["reverted"]

def test_02_one_byte_ok():
    r=scout_cycle(b"\x90\xeb",b"\x90\x90"); assert r["applied"] and len(r["diffs"])==1 and r["reverted"]

def test_03_oracle_reject():
    r=scout_cycle(b"\x00",b"\x02",oracle_fn=lambda d: False); assert r["applied"] and not r["oracle"]

def test_04_oracle_accept():
    r=scout_cycle(b"\x00",b"\x01",oracle_fn=lambda d: True); assert r["oracle"]

def test_05_len_mismatch_noapply():
    r=scout_cycle(b"\x00",b"\x00\x00"); assert not r["applied"]

def test_06_too_many_noapply():
    r=scout_cycle(b"\x00"*6,b"\xff"*6); assert not r["applied"]

def test_07_offset_preserved():
    r=scout_cycle(b"\xaa\xbb",b"\xaa\xcc",offset=0x1000); assert r["diffs"][0]["off"]==0x1001

def test_08_two_bytes():
    r=scout_cycle(b"\x00\x00",b"\x01\x02"); assert len(r["diffs"])==2

def test_09_reverted_always():
    r=scout_cycle(b"\x00",b"\x01"); assert r["reverted"]

def test_10_four_boundary():
    r=scout_cycle(b"\x00"*4,b"\x01"*4); assert r["applied"] and len(r["diffs"])==4

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
