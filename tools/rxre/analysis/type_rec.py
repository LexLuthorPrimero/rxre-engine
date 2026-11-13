"""M597 Type-recovery subset: inferencia ancho por uso (i32/i64) sin prueba universal."""
from tools.rxre.analysis.dataflow import decode_function
from capstone.x86 import *

def infer_width(insns):
    # heuristic: 67/48 prefix -> i32/i64; solo sugerencia NOT_DETERMINED
    w = "i32"
    for i in insns:
        for op in i.operands:
            if op.type == X86_OP_REG and op.reg in (X86_REG_RAX, X86_REG_RBX, X86_REG_RCX):
                w = "i64"
    return {"width": w, "epistemic": "SUGGESTED (NOT_DETERMINED)"}
