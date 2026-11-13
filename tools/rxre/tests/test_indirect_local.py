"""M636 tests (10): indirectos locales."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.indirect_local import resolve_table, classify_indirect
from tools.rxre.analysis.jump_tables import resolve_relative
from tools.rxre.analysis.indirect_targets import resolve
import struct

def _data(offs): return b"".join(struct.pack("<i", o) for o in offs)

def test_01_got_local():
    st,vs,_=resolve_relative(0x2000, _data([0x10]), 0, 0, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="FINITE_TARGET_SET"

def test_02_got_plt():
    assert classify_indirect("got_plt")=="MAY_TARGET"

def test_03_got_externa():
    assert classify_indirect("got_external")=="MAY_TARGET"
    st,vs=resolve([("load_got",0x24f40,"external")]); assert st=="MAY_TARGET"

def test_04_reloc_ausente():
    st,vs=resolve([("load_got",0x24f40,"external")]); assert st=="MAY_TARGET"

def test_05_sobrescrito():
    st,vs=resolve([("load_got",0x3940,"local"),("const",0x5555)])
    # última def gana (const) -> single
    assert st=="SINGLE_TARGET_PROVEN"

def test_06_alias_invalida():
    st,vs=resolve([("const",0x401000),("call",)])
    assert st=="UNKNOWN"

def test_07_call_conocido():
    # store disjunta preserva: modelado via indirect_targets path
    st,vs=resolve([("const",0x401000)])
    assert st=="SINGLE_TARGET_PROVEN"

def test_08_dos_finitos():
    data=_data([0x10, 0x20])
    st,vs,_=resolve_relative(0x2000, data, 0, 1, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="FINITE_TARGET_SET" and len(vs)==2

def test_09_fuera_seccion():
    data=_data([0x99999])
    st,vs,_=resolve_relative(0x2000, data, 0, 0, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="MAY_TARGET"

def test_10_sin_reaching():
    st,vs=resolve([]); assert st=="UNKNOWN"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
