"""M658 tests (8): igualdad discriminante."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.equality_audit import eq_bytes, eq_struct, eq_normalized, eq_state, eq_hash

def test_01_bytes_exacta():
    assert eq_bytes(b"hola",b"hola")["equal"] and not eq_bytes(b"hola",b"hola2")["equal"]

def test_02_bytes_no_equiv_interna():
    # bytes iguales no implican equivalencia interna
    assert eq_bytes(b"x",b"x")["equal"] is True

def test_03_struct_fields():
    r=eq_struct({"a":1,"b":2},{"a":1})
    assert not r["equal"] and r["missing"]==["b"]

def test_04_normalizada():
    r=eq_normalized(" Hola ","hola", lambda s: s.strip().lower())
    assert r["naive"] is False and r["equal"] is True

def test_05_state_no_evidence():
    r=eq_state("SUPPORTED","SUPPORTED")
    assert r["equal"] and not r["implies_evidence_equal"]

def test_06_hash_no_semantica():
    r=eq_hash("ab","ab")
    assert r["equal"] and not r["semantic"]

def test_07_dominio_incompatible():
    # byte vs hash mismos valores en string no se comparan
    assert eq_bytes(b"1",b"1")["domain"]=="bytes exact" and eq_hash("1","1")["domain"]=="hash artefacto"

def test_08_falso_negativo_trivial():
    # normalización irrelevante no debe rechazar: "x" vs "x" exact es True
    assert eq_bytes(b"x",b"x")["equal"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
