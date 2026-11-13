"""M580 interproc reaching (super-graph). Intraproc M579 + CALL/RETURN edges."""
from tools.rxre.analysis.dataflow import use_def_maps, reaching_defs

def interproc_reaching(func_cfgs, call_edges, entry_of):
    # func_cfgs: {fname: (blocks, block_insns)}; call_edges: [(caller_block, callee_entry, callee_exits, return_block)]
    # Build supergraph maps
    all_ids = []
    succ = {}
    pred = {}
    gen_map = {}; kill_map = {}
    for fname, (blocks, block_insns) in func_cfgs.items():
        um, dm, gm, km = use_def_maps(block_insns)
        for b in blocks:
            bid = str(b["id"])
            all_ids.append(bid)
            succ.setdefault(bid, [])
            pred.setdefault(bid, [])
            gen_map[bid] = gm.get(bid, set())
            kill_map[bid] = km.get(bid, set())
        for b in blocks:
            bid = str(b["id"])
            for o in b.get("out_nodes", []):
                oid = str(o)
                succ.setdefault(bid, []).append(oid)
                pred.setdefault(oid, []).append(bid)
    # add interproc edges
    for (cb, ce, cexits, rb) in call_edges:
        cb, ce, rb = str(cb), str(ce), str(rb)
        succ.setdefault(cb, []).append(ce)
        pred.setdefault(ce, []).append(cb)
        for ex in cexits:
            ex = str(ex)
            succ.setdefault(ex, []).append(rb)
            pred.setdefault(rb, []).append(ex)
    entry = str(entry_of)
    # global entry: ensure all ids in maps
    for n in list(succ.keys()): pred.setdefault(n, [])
    IN, OUT = reaching_defs(succ, pred, entry, all_ids, gen_map, kill_map)
    return IN, OUT, succ, pred, all_ids
