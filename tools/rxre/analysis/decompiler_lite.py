"""M589 DECOMPILER-LITE: informe estructural CFG+SSA+dataflow+IR (sin equivalencia). M629: +MEM_PRED. M630: +call summaries."""
from tools.rxre.analysis.ssa import build_graph, dominators, dominance_frontier, phi_placement
from tools.rxre.analysis.dataflow import use_def_maps, reaching_defs, liveness
from tools.rxre.analysis.ir import validate_ir
from tools.rxre.analysis.mem_pred import prop_predicate as _mem_prop
from tools.rxre.analysis.call_summary import prop_with_summaries as _mem_prop_s, summarize as _summarize

def build_report(blocks, block_insns, entry) -> dict:
    succ, pred, ids = build_graph(blocks)
    Dom = dominators(succ, pred, str(entry), ids)
    DF = dominance_frontier(succ, pred, str(entry), ids, Dom)
    # phi placeholder: defs per block (by block id)
    var_defs = {}
    um, dm, gm, km = use_def_maps(block_insns)
    for bid, d in dm.items():
        for reg in d:
            var_defs.setdefault(str(reg), set()).add(str(bid))
    phi = phi_placement(DF, var_defs)
    IN, OUT = reaching_defs(succ, pred, str(entry), ids, gm, km)
    LI, LO = liveness(succ, pred, str(entry), ids, um, dm)
    ir_blocks = [{"id": str(b["id"]), "ops": []} for b in blocks]
    valid, reason = validate_ir(ir_blocks)
    # M629: propagar MEM_PRED con evidencia finit0 (flag 0x25260:1 + fnptr 0x24fe8:8) sin inventar valores
    from tools.rxre.analysis.mem_pred import loc
    FLAG = loc(0x25260, 1); FNPTR = loc(0x24fe8, 8)
    # eventos derivados de disasm crudo (cmp byte/qword + mov byte + calls): conservador
    block_events = {
        "0": [("load", FLAG, "EQ", 0)],
        "2": [("load", FNPTR, "EQ", 0)],
        "3": [("call",), ("store", FLAG, 1)],
    }
    try:
        MEM_IN, MEM_OUT = _mem_prop(succ, pred, str(entry), ids, block_events)
        mem_repr = {k: sorted([(hex(p[0][0]), p[0][1], p[1], p[2]) for p in v]) for k, v in MEM_OUT.items()}
    except Exception:
        MEM_OUT = {}; mem_repr = {}
    # M630: summaries de callees (deregister_tm_clones, __cxa_finalize PLT = sin cuerpo -> unknown)
    # Re-propaga con call_summary; callees externos => mismo resultado que M629 (limitación demostrada)
    try:
        s_ext = _summarize("deregister_tm_clones", None, "ls:54e936d3")
        block_events_s = {
            "0": [("load", FLAG, "EQ", 0)],
            "2": [("load", FNPTR, "EQ", 0)],
            "3": [("call_summary", s_ext), ("store", FLAG, 1)],
        }
        MEMS_IN, MEMS_OUT = _mem_prop_s(succ, pred, str(entry), ids, block_events_s)
        mem_s_repr = {k: sorted([(hex(p[0][0]), p[0][1], p[1], p[2]) for p in v]) for k, v in MEMS_OUT.items()}
    except Exception:
        mem_s_repr = {}
    # M631: PLT/GOT -> deregister_tm_clones local (0x3940, 41B, reads 0x24f78) known, __cxa_finalize externo unknown
    try:
        from tools.rxre.analysis.plt_got_effects import summary_for_symbol
        from tools.rxre.analysis.mem_pred import loc as _loc
        s_dereg = summary_for_symbol("deregister_tm_clones", local_events={"0":[("load",_loc(0x24f78,8),"NE",0)]})
        s_cxa = summary_for_symbol("__cxa_finalize")
        block_events_p = {
            "0": [("load", FLAG, "EQ", 0)],
            "2": [("load", FNPTR, "EQ", 0)],
            "3": [("call_summary", s_dereg), ("store", FLAG, 1)],
            "4": [("call_summary", s_cxa)],
        }
        MEM_P_IN, MEM_P_OUT = _mem_prop_s(succ, pred, str(entry), ids, block_events_p)
        mem_p_repr = {k: sorted([(hex(p[0][0]), p[0][1], p[1], p[2]) for p in v]) for k, v in MEM_P_OUT.items()}
    except Exception:
        mem_p_repr = {}
    # IR con MEM_PRED explícito (preserva equiv NOT_DETERMINED)
    ir_blocks_mem = [{"id": str(b["id"]), "ops": [("MEM_PRED", (f"ELF:{hex(FLAG[0])}:1", "EQ", 0))]} for b in blocks[:1]] + ir_blocks[1:]
    valid_mem, _ = validate_ir(ir_blocks_mem)
    return {
        "entry": str(entry),
        "ids": list(ids),
        "dom": {k: sorted(v) for k, v in Dom.items()},
        "phi": {k: sorted(v) for k, v in phi.items()},
        "reaching_nonempty": {k: len(v) for k, v in OUT.items()},
        "liveness_nonempty": {k: len(v) for k, v in LI.items()},
        "ir_valid": valid,
        "equiv": "NOT_DETERMINED (sin equivalencia universal demostrada)",
        "mem_pred": mem_repr,
        "mem_pred_summary": mem_s_repr,
        "mem_pred_plt": mem_p_repr,
        "ir_valid_mem": valid_mem,
    }
