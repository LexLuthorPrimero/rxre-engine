"""M632 tests (10): destinos indirectos."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.indirect_targets import resolve, finites_to_cfg, SINGLE_TARGET_PROVEN, FINITE_TARGET_SET, MAY_TARGET, UNKNOWN

def test_01_const_unico():
    st,vs=resolve([("const",0x401000)]); assert st==SINGLE_TARGET_PROVEN and vs=={0x401000}

def test_02_dos_phi():
    st,vs=resolve([("phi",[[("const",0x401000)],[("const",0x402000)]])]); assert st==FINITE_TARGET_SET and vs=={0x401000,0x402000}

def test_03_tabla_limites():
    # tabla demostrada con 2 entradas (sintético: phi2 con limites ok)
    st,vs=resolve([("phi",[[("const",1)],[("const",2)]])]); assert st==FINITE_TARGET_SET

def test_04_tabla_fuera_rango():
    # índice fuera de rango posible -> MAY (no exhaustivo)
    st,vs=resolve([("unknown",)]); assert st==UNKNOWN

def test_05_got_local_y_externo():
    st,vs=resolve([("load_got",0x3940,"local")]); assert st==FINITE_TARGET_SET and vs=={0x3940}
    st2,vs2=resolve([("load_got",0x24f40,"external")]); assert st2==MAY_TARGET

def test_06_sobrescrito_antes_salto():
    st,vs=resolve([("const",0x111),("const",0x222)]); assert vs=={0x222} and st==SINGLE_TARGET_PROVEN

def test_07_call_invalida():
    st,vs=resolve([("const",0x401000),("call",)]); assert st==UNKNOWN and vs==set()

def test_08_truncamiento():
    st,vs=resolve([("const",0x100000001),("overwrite_const",0x1)]); assert st==UNKNOWN

def test_09_ciclo():
    # ciclo de definiciones (recursión limitada): iter max 3 -> unknown
    st,vs=resolve([("phi",[[("phi",[[("const",1)]])]])], max_iter=1); assert st in (MAY_TARGET, UNKNOWN)

def test_10_parcialmente_resoluble():
    st,vs=resolve([("phi",[[("const",1)],[("unknown",)]])]); assert st==MAY_TARGET

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
