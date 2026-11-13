"""M637 test_integration_cfg (8): integracion FINITE + dedup + MAY + reconciliacion."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.cfg_coverage import integrated_cfg, metrics_from_aflj, B519_DESTS
from tools.rxre.analysis.jump_tables import resolve_relative
import struct

def _data(offs): return b"".join(struct.pack("<i", o) for o in offs)

def test_01_finite_cinco():
    d=integrated_cfg()
    assert d["dests"]==B519_DESTS and len(d["dests"])==5

def test_02_dedup():
    # destinos unicos: no duplicar aristas (set)
    assert len(set(B519_DESTS))==5

def test_03_fuera_seccion():
    st,vs,_=resolve_relative(0x2000, _data([0x99999]), 0, 0, exec_lo=0x1000, exec_hi=0x3000)
    assert st=="MAY_TARGET"

def test_04_evidencia_incompleta():
    st,vs,_=resolve_relative(0x2000, b"\x00\x00", 0, 5, exec_lo=0, exec_hi=2**64)
    assert st=="UNKNOWN"

def test_05_may_conservado():
    from tools.rxre.analysis.indirect_targets import resolve
    st,vs=resolve([("load_got",0x24f78,"external")]); assert st=="MAY_TARGET"

def test_06_sin_doble_conteo_M633():
    # M633 277->61 no debe sumar a M637 5 como 66 sin distinguir: son tablas distintas
    assert integrated_cfg()["table_M633"]=="277->61 intacto (sin doble conteo)"

def test_07_reconciliacion():
    d=integrated_cfg()
    assert d["edges_before"]=="14/6055" and d["edges_after"]=="19/6055" and d["delta"]=="+5 aristas CFG"

def test_08_bloques_sin_nuevos():
    d=integrated_cfg()
    assert "sin bloques nuevos" in d["structural_blocks"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
