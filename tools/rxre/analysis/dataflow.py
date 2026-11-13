"""M579 dataflow minimal: reaching definitions (register) + liveness on CFG blocks.
Instructions decoded with capstone from function bytes (rizin pxj or raw bytes).
"""
from __future__ import annotations
from typing import Dict, List, Set, Tuple
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import *

def decode_function(data: bytes, base_addr: int) -> list:
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    cs.detail = True
    return list(cs.disasm(data, base_addr))

def _regs(op):
    if op.type == X86_OP_REG:
        return {op.reg}
    return set()

def block_gen_kill(insns):
    # gen: (reg, insn_idx) definitions reaching out; kill: regs defined
    gen: Set[Tuple[int, int]] = set()
    kill: Set[int] = set()
    defined: Set[int] = set()  # regs defined so far in block (for gen: first def)
    for idx, insn in enumerate(insns):
        # upward-exposed use: reg used before defined in block
        used_before = set()
        for op in insn.operands:
            if op.type == X86_OP_REG:
                if op.reg not in defined:
                    # will be handled as use (for liveness separately)
                    pass
        # defs
        for op in insn.operands:
            # write operand is first operand for most x86 insns? capstone write flag:
            pass
        # Use capstone's detail: operand.access
        defs = {op.reg for op in insn.operands if op.access & 2}
        uses = {op.reg for op in insn.operands if op.access & 1 and not (op.access & 2 and op.type == X86_OP_REG)}
        # Note: opcodes like mov r,r have both read/write? access flags: 1=read,2=write,3=rw
        for r in defs:
            gen.add((r, idx))
            kill.add(r)
            defined.add(r)
    return gen, kill

def reaching_defs(succ, pred, entry, ids, gen_map, kill_map):
    # IN/OUT as sets of (reg,insn)
    IN: Dict[str, Set] = {n: set() for n in ids}
    OUT: Dict[str, Set] = {n: set() for n in ids}
    changed = True
    while changed:
        changed = False
        for n in ids:
            new_in: Set = set()
            for p in pred.get(n, []):
                new_in |= OUT.get(p, set())
            new_out = set(new_in) | gen_map.get(n, set())
            # kill: remove defs of killed regs except gen (standard: OUT = gen U (IN - kill))
            killed = kill_map.get(n, set())
            new_out = {d for d in new_out if d[0] not in killed} | gen_map.get(n, set())
            if new_in != IN[n] or new_out != OUT[n]:
                IN[n], OUT[n] = new_in, new_out; changed = True
    return IN, OUT

def liveness(succ, pred, entry, ids, use_map, def_map):
    LIVE_IN: Dict[str, Set[int]] = {n: set() for n in ids}
    LIVE_OUT: Dict[str, Set[int]] = {n: set() for n in ids}
    changed = True
    while changed:
        changed = False
        for n in reversed(ids):
            new_out: Set[int] = set()
            for s in succ.get(n, []):
                new_out |= LIVE_IN.get(s, set())
            new_in = (use_map.get(n, set()) | (new_out - def_map.get(n, set())))
            if new_in != LIVE_IN[n] or new_out != LIVE_OUT[n]:
                LIVE_IN[n], LIVE_OUT[n] = new_in, new_out; changed = True
    return LIVE_IN, LIVE_OUT

def use_def_maps(block_insns: Dict[str, list]):
    use_map: Dict[str, Set[int]] = {}
    def_map: Dict[str, Set[int]] = {}
    gen_map: Dict[str, Set] = {}
    kill_map: Dict[str, Set[int]] = {}
    for bid, insns in block_insns.items():
        use: Set[int] = set(); define: Set[int] = set()
        defined_so_far: Set[int] = set()
        gen: Set = set(); kill: Set[int] = set()
        for idx, insn in enumerate(insns):
            defs = {op.reg for op in insn.operands if (op.access & 2)}
            uses = {op.reg for op in insn.operands if (op.access & 1)}
            for r in uses:
                if r not in defined_so_far:
                    use.add(r)
            for r in defs:
                gen.add((r, idx)); kill.add(r); define.add(r); defined_so_far.add(r)
        use_map[bid] = use; def_map[bid] = define
        gen_map[bid] = gen; kill_map[bid] = kill
    return use_map, def_map, gen_map, kill_map
