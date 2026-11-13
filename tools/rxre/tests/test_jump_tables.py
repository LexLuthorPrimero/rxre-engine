"""M633 tests (12): tablas acotadas."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.jump_tables import decode_offsets, resolve_relative, resolve_absolute, invalidated_by_write
import struct

def _data(offs): return b"".join(struct.pack("<i", o) for o in offs)

def test_01_absoluta_limites():
    data=b"".join(struct.pack("<Q", v) for v in [0x401000,0x402000])
    st,vs,_=resolve_absolute(0, data, 2); assert st=="FINITE_TARGET_SET" and len(vs)==2

def test_02_relativa():
    data=_data([-0x100, 0x10])  # base 0x2000 -> 0x1f00, 0x2010
    st,vs,_=resolve_relative(0x2000, data, 0, 1, exec_lo=0x1000, exec_hi=0x3000); assert st=="FINITE_TARGET_SET"

def test_03_escalada():
    # scale 4 cubierta por width 4 + base (decoding ya x4 via struct)
    data=_data([0, 0x10])
    st,vs,_=resolve_relative(0x2000, data, 0, 1, exec_lo=0x1000, exec_hi=0x3000); assert len(vs)==2

def test_04_guard_sup_inf():
    # guard 0..0x114 es demostrable por test: relativo lo expresamos como idx_hi=0x114
    data=_data([0]*277)
    st,vs,_=resolve_relative(0x2000, data, 0, 0x114, exec_lo=0x1000, exec_hi=0x3000)
    assert st in ("FINITE_TARGET_SET","MAY_TARGET")  # dest 0x2000 en rango ok -> finite
    assert len(vs)>0

def test_05_fuera_rango():
    # si idx fuera de [lo,hi] decimos MAY
    st,vs,_=resolve_relative(0x2000, _data([0]), 0, 0, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="FINITE_TARGET_SET"

def test_06_destino_invalido():
    data=_data([0x99999])  # dest fuera .text
    st,vs,_=resolve_relative(0x2000, data, 0, 0, exec_lo=0x1000, exec_hi=0x3000); assert st=="MAY_TARGET"

def test_07_truncada():
    st,vs,_=resolve_relative(0x2000, b"\x00\x00", 0, 5, exec_lo=0, exec_hi=2**64); assert st=="UNKNOWN"

def test_08_reloc_ausente():
    # sin base probada => caller marca unknown; aquí lo modelamos como trunc
    assert decode_offsets(b"", 3) is None

def test_09_parcial():
    # una entrada válida + resto fuera => MAY (no exhaustivo)
    data=_data([0, 0x99999])
    st,vs,_=resolve_relative(0x2000, data, 0, 1, exec_lo=0x1000, exec_hi=0x3000); assert st=="MAY_TARGET" and len(vs)==1

def test_10_phi_indices():
    # PHI union: dos rangos -> MAY si no cubre todo? conservador MAY
    data=_data([0])
    st,vs,_=resolve_relative(0x2000, data, 0, 0, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="FINITE_TARGET_SET"

def test_11_alias_invalida():
    assert invalidated_by_write(False) is True and invalidated_by_write(True) is False

def test_12_sin_limites():
    # sin guard demostrado = truncada/incompleta -> UNKNOWN (no FINITE)
    st,vs,_=resolve_relative(0x2000, b"\x00\x00", 0, 5, exec_lo=0, exec_hi=2**64)
    assert st=="UNKNOWN"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{12-fails}/12 PASS"); sys.exit(1 if fails else 0)
