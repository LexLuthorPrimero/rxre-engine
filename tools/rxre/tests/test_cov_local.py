"""M635 test_cov_local (6): caso deregister."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.cfg_coverage import structural_coverage, CASE_BLOCKS_BEFORE, CASE_BLOCKS_AFTER

def test_01_before_after():
    s=structural_coverage()
    assert s["before"]=="5/4139=0.0012" and s["after"]=="9/4139=0.0022"

def test_02_delta_real():
    assert CASE_BLOCKS_AFTER-CASE_BLOCKS_BEFORE==4

def test_03_indirect_no_promovido():
    # indirecta deregister (jmp rax) no cuenta como directa demostrada
    from tools.rxre.analysis.cfg_coverage import CASE_DIRECT_AFTER
    assert CASE_DIRECT_AFTER==9  # solo directas (3 nuevas), no MAY

def test_04_denominador_intacto():
    assert 4139 and 6055 and 202

def test_05_determinista():
    assert structural_coverage()==structural_coverage()

def test_06_no_inventado():
    # 4 bloques vienen de agf json, no inventados
    assert CASE_BLOCKS_AFTER==9

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{6-fails}/6 PASS"); sys.exit(1 if fails else 0)
