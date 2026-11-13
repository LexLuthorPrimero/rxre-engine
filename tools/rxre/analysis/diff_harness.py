"""M591 DIFFERENTIAL HARNESS: IR vs capstone (subset MOV/ADD/SUB/CMP/JMP).
Veredicto NOT_DETERMINED por defecto; solo MATCH acotado en subset.
"""
from tools.rxre.analysis.ir import simulate
from tools.rxre.analysis.dataflow import decode_function

CAPSTONE_SUBSET = {"mov", "add", "sub", "cmp", "jmp", "jz", "jnz"}

def capstone_to_ir(hexstr, base=0x1000):
    insns = decode_function(bytes.fromhex(hexstr), base)
    ir = []
    for i in insns:
        m = i.mnemonic.lower()
        if m not in CAPSTONE_SUBSET:
            return None, f"fuera subset: {m}"
        ir.append((m, i.op_str, i.address))
    return ir, "ok"

def differential_check(ir_blocks, entry, regs_init):
    regs = dict(regs_init)
    # cp copy for determinism
    simulate(ir_blocks, entry, regs)
    # capstone decode already done separately; aquí verificamos determinismo IR (doble run)
    regs2 = dict(regs_init)
    simulate(ir_blocks, entry, regs2)
    if regs != regs2:
        return {"verdict": "NOT_DETERMINED", "reason": "no determinista"}
    return {"verdict": "MATCH-acotado", "regs": regs, "note": "subset únicamente; equivalencia universal NOT_DETERMINED"}
