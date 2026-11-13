"""M665 tests (8): cardinalidades."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.cardinality import card_of, check_guard, outside

def test_01_cardinalidad():
    c=card_of(0,137,[1,2,2]); assert c["idx_card"]==138 and c["uniq"]==2 and c["class"]=="PROVEN"

def test_02_guard_ok():
    assert check_guard(0,137,137) and not check_guard(0,200,137)

def test_03_min_max():
    assert not outside(0,0,137) and not outside(137,0,137) and outside(-1,0,137) and outside(138,0,137)

def test_04_convergencia():
    # varios índices convergen: uniq <= idx
    c=card_of(0,4,[1,1,2,2,2]); assert c["uniq"]==2 and c["uniq"]<=c["idx_card"]

def test_05_no_inventado():
    assert card_of(0,0,[1])["class"]=="PROVEN"

def test_06_sin_dominio():
    assert card_of(0,-1,[])["class"]=="NOT_DETERMINED"

def test_07_fracaso_descarta():
    # guard failedo => fuera de rango posible -> UNKNOWN via outside
    assert outside(999,0,5)

def test_08_provenance():
    assert card_of(0,0,[1])["lo"]==0

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
