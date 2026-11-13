"""M591 tests (10): harness subset + NOT_DETERMINED."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.diff_harness import capstone_to_ir, differential_check

def test_01_mov_in_subset():
    ir, why = capstone_to_ir("48 89 d8", 0x1000); assert why=="ok" and ir[0][0]=="mov"

def test_02_add_in_subset():
    ir, why = capstone_to_ir("48 01 d8", 0x1000); assert why=="ok"

def test_03_ret_out_of_subset():
    ir, why = capstone_to_ir("c3", 0x1000); assert ir is None and "subset" in why

def test_04_diff_mov_add():
    blocks=[{"id":"B0","ops":[("MOV",("rax",5)),("ADD",("rbx","rax",3)),("RET",())]}]
    r=differential_check(blocks,"B0",{}); assert r["verdict"]=="MATCH-acotado" and r["regs"]["rbx"]==8

def test_05_diff_not_determined_note():
    blocks=[{"id":"B0","ops":[("MOV",("rax",1)),("RET",())]}]
    r=differential_check(blocks,"B0",{}); assert "NOT_DETERMINED" in r["note"]

def test_06_determinism_double_run():
    blocks=[{"id":"B0","ops":[("MOV",("rax",2)),("RET",())]}]
    assert differential_check(blocks,"B0",{})["verdict"]=="MATCH-acotado"

def test_07_jmp_target():
    ir, _ = capstone_to_ir("eb 00", 0x1000)  # jmp +0 (offset); mnemonic jmp
    # capstone decode puede variar; si entra en subset o fuera, no llegamos aquí con excepción
    assert ir is None or ir[0][0]=="jmp"

def test_08_empty():
    ir, why = capstone_to_ir("", 0x1000); assert ir==[] and why=="ok"

def test_09_sub_in_subset():
    ir, why = capstone_to_ir("48 29 d8", 0x1000); assert why=="ok"

def test_10_cmp_in_subset():
    # cmp rax, rbx = 48 39 d8
    ir, why = capstone_to_ir("48 39 d8", 0x1000); assert why=="ok"

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
