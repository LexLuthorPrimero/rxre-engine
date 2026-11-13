"""M582 EDICT IR minimal (explicable, sin equivalencia universal).
Subset verificable: MOV/ADD/SUB/CMP/JMP/JZ/JNZ/CALL/RET + loops no-recursivos.
"""
from __future__ import annotations
from typing import Dict, List

OPS = {"MOV","ADD","SUB","MUL","CMP","JMP","JZ","JNZ","CALL","RET","PHI","MEM_PRED"}

def validate_ir(blocks) -> tuple:
    # blocks: [{"id":..,"ops":[(op,args)]}]
    ids = {str(b["id"]) for b in blocks}
    for b in blocks:
        for op, args in b.get("ops", []):
            if op not in OPS:
                return False, f"op desconocida {op}"
            if op in ("JMP","JZ","JNZ"):
                if not args or str(args[0]) not in ids:
                    return False, f"salto a id inexistente {args}"
            if op in ("MOV","ADD","SUB","MUL","CMP"):
                if len(args) < 2:
                    return False, f"operands insuficientes {op}"
    return True, "ok"

def simulate(blocks, entry, regs) -> Dict[str,int]:
    # interpretación tiny para tests diferenciales (solo MOV/ADD/SUB/CMP/JMP/JZ/JNZ/RET)
    prog = {str(b["id"]): list(b.get("ops", [])) for b in blocks}
    by_id = {str(b["id"]): b for b in blocks}
    cur = str(entry)
    steps = 0
    while cur in prog and steps < 1000:
        steps += 1
        jumped = False
        for op, args in prog[cur]:
            if op == "MOV":
                dst, src = args[0], args[1]
                regs[dst] = regs.get(src, 0) if isinstance(src, str) else src
            elif op == "ADD":
                regs[args[0]] = regs.get(args[1],0) + (regs.get(args[2],0) if isinstance(args[2],str) else args[2])
            elif op == "SUB":
                regs[args[0]] = regs.get(args[1],0) - (regs.get(args[2],0) if isinstance(args[2],str) else args[2])
            elif op == "CMP":
                a = regs.get(args[0],0) if isinstance(args[0],str) else args[0]
                b = regs.get(args[1],0) if isinstance(args[1],str) else args[1]
                regs["__ZF"] = 1 if a == b else 0
            elif op == "JMP":
                cur = str(args[0]); jumped = True; break
            elif op == "JZ":
                if regs.get("__ZF",0) == 1:
                    cur = str(args[0]); jumped = True; break
            elif op == "JNZ":
                if regs.get("__ZF",0) != 1:
                    cur = str(args[0]); jumped = True; break
            elif op == "RET":
                return regs
        if not jumped:
            break
    return regs

def native_equiv_check() -> str:
    return "NOT_DETERMINED (sin equivalencia universal demostrada)"
