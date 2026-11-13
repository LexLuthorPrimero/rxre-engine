#!/usr/bin/env python3
"""POLARIS-029: GCN4 Deep Semantic Reconstruction.

Analyzes GFX8 ISA at the semantic level: def-use chains, data dependencies,
control flow (divergence/reconvergence), synchronization, memory operations.

Produces functional semantic representations, not just instruction classification.

Reutiliza: gpu_isa_recovery (ISA capture), M58, differential_validator,
gpu_control_flow, GPU Evolution Engine.

Restricciones: DB_AUTH BLOCKED, W5 BLOCKED, autonomous_loop=False, max_iter=1, op_claim=False.
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math, random, re
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, OrderedDict

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.polaris12.gpu_isa_recovery import GPUISARecovery

SHADERS = ["conditional", "loop_sum", "loop_nested", "barrier_sync", "early_return", "multi_path"]
SPV_DIR = "/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/canonical"
ISA_DIR = "/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/canonical/isa"


class GCN4SemanticAnalyzer:
    """Deep semantic analysis of GFX8 ISA instructions."""

    # GFX8 instruction categories
    INSTR_CATEGORIES = {
        "s_lshl": "scalar_shift",
        "s_mov": "scalar_move",
        "s_load": "scalar_memory_load",
        "s_waitcnt": "synchronization",
        "s_cbranch": "conditional_branch",
        "s_branch": "unconditional_branch",
        "s_andn2": "scalar_bitwise",
        "s_bfm": "scalar_bitfield",
        "v_add": "vector_arithmetic",
        "v_cmpx": "vector_compare_predicate",
        "v_lshlrev": "vector_shift",
        "v_mov": "vector_move",
        "buffer_store": "global_memory_store",
        "buffer_load": "global_memory_load",
        "ds_write": "lds_write",
        "ds_read": "lds_read",
        "s_endpgm": "program_end",
    }

    def __init__(self, output_dir: str = "/tmp/rxre_polaris29"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results = {}

    def parse_isa(self, isa_text: str) -> List[Dict[str, Any]]:
        """Parse ISA text into structured instructions."""
        instructions = []
        current_bb = None
        for line in isa_text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Basic block header
            m = re.match(r'^(BB\d+):', line)
            if m:
                current_bb = m.group(1)
                continue
            # Instruction line: "mnemonic operands ; hex"
            # Format: "s_lshl_b32 s3, s3, 6                                        ; 8e038603"
            parts = line.split(';')
            instr_part = parts[0].strip()
            hex_part = parts[1].strip() if len(parts) > 1 else ""
            if not instr_part:
                continue
            # Parse mnemonic and operands
            tokens = instr_part.split()
            if not tokens:
                continue
            mnemonic = tokens[0]
            operands_str = " ".join(tokens[1:]) if len(tokens) > 1 else ""
            # Parse operands (comma-separated, but registers may have ranges like s[4:7])
            operands = [o.strip() for o in operands_str.split(',') if o.strip()]
            # Categorize
            category = self._categorize(mnemonic)
            # Extract registers
            defs, uses = self._extract_defs_uses(mnemonic, operands)
            instructions.append({
                "bb": current_bb,
                "mnemonic": mnemonic,
                "operands": operands,
                "operands_str": operands_str,
                "hex": hex_part,
                "category": category,
                "defs": defs,
                "uses": uses,
            })
        return instructions

    def _categorize(self, mnemonic: str) -> str:
        """Categorize an instruction by mnemonic."""
        for prefix, cat in self.INSTR_CATEGORIES.items():
            if mnemonic.startswith(prefix):
                return cat
        return "unknown"

    def _extract_defs_uses(self, mnemonic: str, operands: List[str]) -> Tuple[List[str], List[str]]:
        """Extract defined and used registers from an instruction."""
        defs = []
        uses = []
        # Patterns for register extraction
        reg_pattern = re.compile(r'[vs]\d+|\[s\d+:\w+\]|\[v\d+:\w+\]')

        if mnemonic.startswith("s_lshl") or mnemonic.startswith("s_mov") or mnemonic.startswith("s_load"):
            # First operand is dest
            if operands:
                defs.append(operands[0])
            for o in operands[1:]:
                if re.match(r'^[vs]\d+$', o) or '[' in o:
                    uses.append(o)
        elif mnemonic.startswith("v_add") or mnemonic.startswith("v_cmpx") or mnemonic.startswith("v_lshlrev") or mnemonic.startswith("v_mov"):
            if operands:
                defs.append(operands[0])
            for o in operands[1:]:
                if re.match(r'^[vs]\d+$', o) or '[' in o or 'vcc' in o:
                    uses.append(o)
        elif mnemonic.startswith("buffer_store"):
            # store: value, addr, sreg, offset
            for o in operands:
                if re.match(r'^[vs]\d+$', o) or '[' in o:
                    uses.append(o)
        elif mnemonic.startswith("buffer_load") or mnemonic.startswith("ds_read") or mnemonic.startswith("ds_write"):
            if operands and ('v[' in operands[0] or re.match(r'^[vs]\d+$', operands[0])):
                # First may be dest for read
                if mnemonic.startswith("ds_read") or mnemonic.startswith("buffer_load"):
                    defs.append(operands[0])
            for o in operands[1:] if len(operands) > 1 else []:
                if re.match(r'^[vs]\d+$', o) or '[' in o:
                    uses.append(o)
            # Also check remaining operands
            for o in operands:
                if o not in defs and (re.match(r'^[vs]\d+$', o) or '[' in o):
                    if o not in uses:
                        uses.append(o)
        elif mnemonic.startswith("s_andn2") or mnemonic.startswith("s_bfm"):
            if operands:
                defs.append(operands[0])
            for o in operands[1:]:
                if re.match(r'^[vs]\d+$', o) or '[' in o or 'exec' in o:
                    uses.append(o)
        elif mnemonic.startswith("s_cbranch") or mnemonic.startswith("s_branch"):
            # Branch: uses vcc or exec
            for o in operands:
                if 'exec' in o or 'vcc' in o:
                    uses.append(o)
        elif mnemonic.startswith("s_waitcnt"):
            pass  # no register defs/uses
        elif mnemonic.startswith("s_endpgm"):
            pass
        return defs, uses

    def build_defuse(self, instructions: List[Dict]) -> Dict[str, Any]:
        """Build def-use chains for all registers."""
        # Map: register -> list of instruction indices that define it
        defs = defaultdict(list)
        # Map: register -> list of instruction indices that use it
        uses = defaultdict(list)

        for i, instr in enumerate(instructions):
            for r in instr["defs"]:
                defs[r].append(i)
            for r in instr["uses"]:
                uses[r].append(i)

        # Build chains: for each def, find uses that depend on it
        chains = []
        for reg, def_indices in defs.items():
            for di in def_indices:
                # Find uses after this def, before next def of same reg
                next_def = None
                for ndi in def_indices:
                    if ndi > di:
                        next_def = ndi
                        break
                dependent_uses = [ui for ui in uses[reg] if ui > di and (next_def is None or ui < next_def)]
                chains.append({
                    "register": reg,
                    "def_instr": di,
                    "def_mnemonic": instructions[di]["mnemonic"],
                    "use_instrs": dependent_uses,
                    "use_mnemonics": [instructions[ui]["mnemonic"] for ui in dependent_uses],
                })

        return {
            "defs": {k: v for k, v in defs.items()},
            "uses": {k: v for k, v in uses.items()},
            "chains": chains,
            "num_chains": len(chains),
        }

    def analyze_control_flow(self, instructions: List[Dict]) -> Dict[str, Any]:
        """Analyze control flow: basic blocks, branches, merge points, divergence."""
        # Group by basic block
        blocks = OrderedDict()
        current_bb = None
        for i, instr in enumerate(instructions):
            bb = instr["bb"]
            if bb not in blocks:
                blocks[bb] = []
            blocks[bb].append(i)

        # Identify branch instructions
        branches = []
        for i, instr in enumerate(instructions):
            if instr["category"] in ("conditional_branch", "unconditional_branch"):
                branches.append({
                    "instr_idx": i,
                    "bb": instr["bb"],
                    "mnemonic": instr["mnemonic"],
                    "target": instr["operands"][0] if instr["operands"] else None,
                    "type": "conditional" if instr["category"] == "conditional_branch" else "unconditional",
                })

        # Identify merge points (blocks targeted by multiple branches)
        targets = defaultdict(int)
        for b in branches:
            if b["target"]:
                targets[b["target"]] += 1
        merge_points = [t for t, c in targets.items() if c > 1]

        # Identify divergence points (conditional branches)
        divergence_points = [b for b in branches if b["type"] == "conditional"]

        # Identify reconvergence (blocks after conditional that are merge points)
        reconvergence = []
        for mp in merge_points:
            reconvergence.append(mp)

        return {
            "num_basic_blocks": len(blocks),
            "basic_blocks": {k: len(v) for k, v in blocks.items()},
            "branches": branches,
            "num_branches": len(branches),
            "conditional_branches": len(divergence_points),
            "merge_points": merge_points,
            "reconvergence_points": reconvergence,
            "divergence_count": len(divergence_points),
        }

    def analyze_synchronization(self, instructions: List[Dict]) -> Dict[str, Any]:
        """Analyze synchronization: waitcnt, barriers, LDS dependencies."""
        waitcnts = []
        lds_ops = []
        global_mem_ops = []
        for i, instr in enumerate(instructions):
            if instr["mnemonic"].startswith("s_waitcnt"):
                waitcnts.append({"instr_idx": i, "bb": instr["bb"], "operands": instr["operands_str"]})
            if instr["category"] in ("lds_write", "lds_read"):
                lds_ops.append({"instr_idx": i, "bb": instr["bb"], "mnemonic": instr["mnemonic"], "operands": instr["operands_str"]})
            if instr["category"] in ("global_memory_load", "global_memory_store"):
                global_mem_ops.append({"instr_idx": i, "bb": instr["bb"], "mnemonic": instr["mnemonic"], "operands": instr["operands_str"]})

        # Analyze waitcnt dependencies: which memory ops are before each waitcnt
        waitcnt_deps = []
        for w in waitcnts:
            wi = w["instr_idx"]
            # Find memory ops before this waitcnt in the same or preceding blocks
            preceding_mem = [m for m in (lds_ops + global_mem_ops) if m["instr_idx"] < wi]
            waitcnt_deps.append({
                "waitcnt_idx": wi,
                "preceding_memory_ops": len(preceding_mem),
                "types": list(set(m["mnemonic"].split('_')[0] for m in preceding_mem)),
            })

        return {
            "waitcnt_count": len(waitcnts),
            "waitcnts": waitcnts,
            "lds_op_count": len(lds_ops),
            "lds_ops": lds_ops,
            "global_mem_op_count": len(global_mem_ops),
            "global_mem_ops": global_mem_ops,
            "waitcnt_dependencies": waitcnt_deps,
        }

    def analyze_memory(self, instructions: List[Dict]) -> Dict[str, Any]:
        """Analyze memory access patterns."""
        loads = [i for i, ins in enumerate(instructions) if "load" in ins["category"]]
        stores = [i for i, ins in enumerate(instructions) if "store" in ins["category"]]
        lds = [i for i, ins in enumerate(instructions) if "lds" in ins["category"]]

        # Identify address registers
        addr_regs = set()
        for i in loads + stores:
            for r in instructions[i]["uses"]:
                if r.startswith('v') or r.startswith('s'):
                    addr_regs.add(r)

        return {
            "load_count": len(loads),
            "store_count": len(stores),
            "lds_count": len(lds),
            "load_instrs": [{"idx": i, "mnemonic": instructions[i]["mnemonic"]} for i in loads],
            "store_instrs": [{"idx": i, "mnemonic": instructions[i]["mnemonic"]} for i in stores],
            "lds_instrs": [{"idx": i, "mnemonic": instructions[i]["mnemonic"]} for i in lds],
        }

    def build_semantic_graph(self, instructions: List[Dict], defuse: Dict, cf: Dict, sync: Dict) -> Dict[str, Any]:
        """Build a semantic graph connecting instructions, registers, memory, and control flow."""
        nodes = []
        edges = []

        for i, instr in enumerate(instructions):
            nodes.append({
                "id": f"i{i}",
                "type": "instruction",
                "mnemonic": instr["mnemonic"],
                "category": instr["category"],
                "bb": instr["bb"],
                "defs": instr["defs"],
                "uses": instr["uses"],
            })

        # Edges: def-use
        for chain in defuse["chains"]:
            edges.append({
                "from": f"i{chain['def_instr']}",
                "to": f"i{ui}",
                "type": "def_use",
                "register": chain["register"],
            } for ui in chain["use_instrs"])

        # Edges: control flow
        for b in cf["branches"]:
            edges.append({
                "from": f"i{b['instr_idx']}",
                "to": b["target"],
                "type": "control_flow",
                "branch_type": b["type"],
            })

        # Edges: synchronization (waitcnt -> preceding memory)
        for w in sync["waitcnt_dependencies"]:
            edges.append({
                "from": f"i{w['waitcnt_idx']}",
                "to": "memory_ops",
                "type": "synchronization",
                "preceding_ops": w["preceding_memory_ops"],
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def generate_semantic_summary(self, shader_name: str, instructions: List[Dict],
                                  defuse: Dict, cf: Dict, sync: Dict, mem: Dict) -> Dict[str, Any]:
        """Generate a high-level semantic summary."""
        categories = defaultdict(int)
        for ins in instructions:
            categories[ins["category"]] += 1

        return {
            "shader": shader_name,
            "total_instructions": len(instructions),
            "instruction_categories": dict(categories),
            "basic_blocks": cf["num_basic_blocks"],
            "conditional_branches": cf["conditional_branches"],
            "merge_points": cf["merge_points"],
            "divergence_points": cf["divergence_count"],
            "def_use_chains": defuse["num_chains"],
            "registers_defined": len(defuse["defs"]),
            "registers_used": len(defuse["uses"]),
            "waitcnt_count": sync["waitcnt_count"],
            "lds_operations": sync["lds_op_count"],
            "global_loads": mem["load_count"],
            "global_stores": mem["store_count"],
            "lds_accesses": mem["lds_count"],
        }

    def analyze_shader(self, shader_name: str) -> Dict[str, Any]:
        """Full semantic analysis of a shader's ISA."""
        # Load ISA
        isa_path = os.path.join(ISA_DIR, f"{shader_name}_isa_full.txt")
        if not os.path.exists(isa_path):
            return {"status": "BLOCKED", "reason": "ISA file not found"}

        with open(isa_path) as f:
            isa_text = f.read()

        # Extract disassembly section
        in_disasm = False
        disasm_lines = []
        for line in isa_text.splitlines():
            if "disasm:" in line.lower():
                in_disasm = True
                continue
            if in_disasm:
                if "DEVICE:" in line or "RESULTS:" in line or "..." in line or "Compute Shader" in line:
                    in_disasm = False
                    continue
                if line.strip():
                    disasm_lines.append(line)
        disasm_text = "\n".join(disasm_lines)

        # Parse
        instructions = self.parse_isa(disasm_text)
        if not instructions:
            return {"status": "BLOCKED", "reason": "No instructions parsed"}

        # Analyze
        defuse = self.build_defuse(instructions)
        cf = self.analyze_control_flow(instructions)
        sync = self.analyze_synchronization(instructions)
        mem = self.analyze_memory(instructions)
        graph = self.build_semantic_graph(instructions, defuse, cf, sync)
        summary = self.generate_semantic_summary(shader_name, instructions, defuse, cf, sync, mem)

        return {
            "status": "OK",
            "instructions": instructions,
            "defuse": defuse,
            "control_flow": cf,
            "synchronization": sync,
            "memory": mem,
            "semantic_graph": graph,
            "summary": summary,
        }

    def run_full_analysis(self) -> Dict[str, Any]:
        """Run full semantic analysis on all shaders."""
        results = {}
        for shader in SHADERS:
            print(f"\n=== {shader} ===")
            result = self.analyze_shader(shader)
            if result["status"] == "OK":
                s = result["summary"]
                print(f"  instr={s['total_instructions']} bb={s['basic_blocks']} cond_br={s['conditional_branches']} "
                      f"merge={len(s['merge_points'])} chains={s['def_use_chains']} regs={s['registers_defined']}/{s['registers_used']} "
                      f"waitcnt={s['waitcnt_count']} lds={s['lds_operations']} loads={s['global_loads']} stores={s['global_stores']}")
            else:
                print(f"  {result['status']}: {result.get('reason', '')}")
            results[shader] = result

        return {
            "shaders": results,
            "total": len(SHADERS),
            "analyzed": sum(1 for r in results.values() if r["status"] == "OK"),
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED", "autonomous_loop=False", "max_iter=1", "op_claim=False"],
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get aggregate summary."""
        summary = {
            "shaders": {},
            "total_instructions": 0,
            "total_defuse_chains": 0,
            "total_basic_blocks": 0,
            "total_conditional_branches": 0,
            "total_lds_operations": 0,
            "total_global_loads": 0,
            "total_global_stores": 0,
        }
        for shader, r in self.results.items():
            if r["status"] == "OK":
                s = r["summary"]
                summary["shaders"][shader] = s
                summary["total_instructions"] += s["total_instructions"]
                summary["total_defuse_chains"] += s["def_use_chains"]
                summary["total_basic_blocks"] += s["basic_blocks"]
                summary["total_conditional_branches"] += s["conditional_branches"]
                summary["total_lds_operations"] += s["lds_operations"]
                summary["total_global_loads"] += s["global_loads"]
                summary["total_global_stores"] += s["global_stores"]
        return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="POLARIS-029: GCN4 Deep Semantic Reconstruction")
    parser.add_argument("--output", default="/tmp/rxre_polaris29", help="Output directory")
    parser.add_argument("--shader", default=None, help="Specific shader")
    args = parser.parse_args()

    analyzer = GCN4SemanticAnalyzer(output_dir=args.output)

    if args.shader:
        result = analyzer.analyze_shader(args.shader)
        # Save detailed result
        out_path = os.path.join(args.output, f"{args.shader}_semantic.json")
        # Remove instructions with too much detail for JSON (keep summary)
        save_result = {k: v for k, v in result.items() if k != "instructions"}
        save_result["instruction_count"] = len(result.get("instructions", []))
        with open(out_path, 'w') as f:
            json.dump(save_result, f, indent=2, default=str)
        print(json.dumps(save_result, indent=2, default=str))
    else:
        result = analyzer.run_full_analysis()
        analyzer.results = result["shaders"]
        summary = analyzer.get_summary()
        # Save summary
        with open(os.path.join(args.output, "polaris29_summary.json"), 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(json.dumps(result, indent=2, default=str))
        print("\n=== SUMMARY ===")
        print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
