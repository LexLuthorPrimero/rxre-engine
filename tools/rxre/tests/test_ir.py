"""M582 IR tests (10): validación + simulación loops/switch acotados."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.ir import validate_ir, simulate, native_equiv_check

def test_01_validate_mov():
    ok,_=validate_ir([{"id":"B0","ops":[("MOV",("rax","rbx"))]}]); assert ok

def test_02_unknown_op_rejected():
    ok,_=validate_ir([{"id":"B0","ops":[("FOO",("rax","rbx"))]}]); assert not ok

def test_03_jump_target_required():
    ok,_=validate_ir([{"id":"B0","ops":[("JMP",("NOWHERE",))]}]); assert not ok

def test_04_sim_mov_add():
    regs={}
    simulate([{"id":"B0","ops":[("MOV",("rax",5)),("ADD",("rbx","rax",3)),("RET",())]}],"B0",regs)
    assert regs["rbx"]==8

def test_05_sim_loop_countdown():
    # for: while x>0 { x-- } using CMP/JZ
    blocks=[
        {"id":"HEAD","ops":[("CMP",("x",0)),("JZ",("EXIT",))]},
        {"id":"BODY","ops":[("SUB",("x","x",1)),("JMP",("HEAD",))]},
        {"id":"EXIT","ops":[("RET",())]},
    ]
    # widen: HEAD fallthrough? model: HEAD JZ->EXIT else JMP BODY
    blocks[0]["ops"].append(("JMP",("BODY",)))
    regs={"x":5}
    simulate(blocks,"HEAD",regs)
    assert regs["x"]==0

def test_06_sim_switch_two_way():
    blocks=[
        {"id":"T","ops":[("CMP",("x",1)),("JZ",("A",)),("JMP",("B",))]},
        {"id":"A","ops":[("MOV",("r",10)),("RET",())]},
        {"id":"B","ops":[("MOV",("r",20)),("RET",())]},
    ]
    regs={"x":1}
    simulate(blocks,"T",regs); assert regs["r"]==10
    regs={"x":9}
    simulate(blocks,"T",regs); assert regs["r"]==20

def test_07_no_equivalence_claim():
    assert native_equiv_check().startswith("NOT_DETERMINED")

def test_08_phi_accepted():
    ok,_=validate_ir([{"id":"B0","ops":[("PHI",("rax",("B1","B2")) )]}]); assert ok

def test_09_ops_coverage():
    from tools.rxre.analysis.ir import OPS
    assert {"MOV","ADD","SUB","CMP","JMP","JZ","JNZ","CALL","RET"} <= OPS

def test_10_cmp_zf_path():
    blocks=[{"id":"S","ops":[("CMP",("a","b")),("JZ",("YES",)),("JMP",("NO",))]}, {"id":"YES","ops":[("MOV",("r",1)),("RET",())]}, {"id":"NO","ops":[("MOV",("r",0)),("RET",())]}]
    r={"a":1,"b":1}; simulate(blocks,"S",r); assert r["r"]==1
    r={"a":1,"b":2}; simulate(blocks,"S",r); assert r["r"]==0

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
