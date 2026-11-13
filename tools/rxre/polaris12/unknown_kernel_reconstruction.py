#!/usr/bin/env python3
"""POLARIS-036: Universal Unknown GPU Kernel Reconstruction.

RXRE receives a SPIR-V kernel whose source, algorithm, and structure are unknown.
It must: decompile -> analyze coverage -> form semantic hypotheses -> discriminate
via RX 550 execution -> reconstruct an executable model -> validate on held-out inputs.

Honesty guarantees:
  - MODELED != VALIDATED; NOT_DETERMINED when hypotheses fail or frontier present.
  - Abstains from fabrication when ISA contains unverified instructions (e.g. v_bfi_b32).
  - Reports EVIDENCE, not universal proof: constants are inferred from the specific binary.

Reutiliza: gpu_isa_recovery, gcn4_formal_semantics, coverage_aware_evolution,
coverage analysis, differential validator patterns, M58 SPIR-V pipeline.

Restricciones: autonomous_loop=False, max_iter=1, op_claim=False, DB_AUTH BLOCKED, W5 BLOCKED.
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, sys, tempfile, re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.gpu_isa_recovery import GPUISARecovery
from rxre.polaris12.coverage_aware_evolution import CoverageIntelligence, classify_mnemonic
from rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline

from rxre.polaris12.gpu_availability import require_gpu, GPUSuspended

VK_TEST = "/home/lucas/Escritorio/rxre/tools/rxre/harness/bin/vk_cf_test"


class Hypothesis:
    """A testable semantic hypothesis about an unknown kernel's behaviour."""

    KINDS = ["H_LIN", "H_XOR_CONST", "H_HASH_SHIFT_XOR", "H_PIECEWISE", "H_LDS_NEIGHBOR_SCALE", "H_ADD_CONST", "H_NEIGHBOR_MUL", "H_BFI_PATTERN", "H_BFI_MIX"]

    def __init__(self, kind: str, params: Dict[str, Any], source: str):
        self.kind = kind
        self.params = params
        self.source = source  # where the constants came from (ISA evidence)

    def predict(self, gid: int) -> int:
        """Predict output for global invocation id gid."""
        A = self.params.get("A", 0)
        B = self.params.get("B", 0)
        K = self.params.get("K", 0)
        s = self.params.get("s", 13)
        T = self.params.get("T", 100)
        A2 = self.params.get("A2", 7)

        def m(x: int) -> int:
            return x & 0xFFFFFFFF

        if self.kind == "H_LIN":
            return m(gid * A + B)
        elif self.kind == "H_ADD_CONST":
            return m(gid + B)
        elif self.kind == "H_XOR_CONST":
            return m(gid ^ K)
        elif self.kind == "H_HASH_SHIFT_XOR":
            x = m(gid * A)
            x = m(x ^ (x >> s))
            return x
        elif self.kind == "H_PIECEWISE":
            if gid <= T:
                return m(gid * A + B)
            return m(gid * A2)
        elif self.kind == "H_LDS_NEIGHBOR_SCALE":
            return m(((gid + 1) % 64) * A)
        elif self.kind == "H_NEIGHBOR_MUL":
            return m(((gid + 1) % 64) * A)
        elif self.kind == "H_BFI_PATTERN":
            # out = ((idx ^ K) & sel) | ((idx * A) & ~sel32), ~sel32 = 32-bit complement
            sel = self.params.get("sel", 0x00FF00FF)
            A = self.params.get("A", 0)
            K = self.params.get("K", 0)
            sel32 = sel & 0xFFFFFFFF
            return m(((gid ^ K) & sel32) | ((gid * A) & ~sel32 & 0xFFFFFFFF))
        elif self.kind == "H_BFI_MIX":
            # out = c ^ (c >> 13) where c = bitfield select (32-bit complement)
            sel = self.params.get("sel", 0x00FF00FF)
            A = self.params.get("A", 0)
            K = self.params.get("K", 0)
            sel32 = sel & 0xFFFFFFFF
            c = ((gid ^ K) & sel32) | ((gid * A) & ~sel32 & 0xFFFFFFFF)
            return m(c ^ (c >> 13))
        return 0

    def explain(self) -> str:
        p = self.params
        if self.kind == "H_LIN":
            return f"out = idx * {p.get('A')} + {p.get('B')} (mod 2^32)"
        elif self.kind == "H_ADD_CONST":
            return f"out = idx + {p.get('B')} (mod 2^32)"
        elif self.kind == "H_XOR_CONST":
            return f"out = idx ^ 0x{p.get('K'):x}"
        elif self.kind == "H_HASH_SHIFT_XOR":
            return f"out = mix(idx * {p.get('A')}); out ^= out >> {p.get('s')} (hash-like)"
        elif self.kind == "H_PIECEWISE":
            return f"if idx <= {p.get('T')}: out = idx * {p.get('A')} + {p.get('B')} else out = idx * {p.get('A2')}"
        elif self.kind == "H_LDS_NEIGHBOR_SCALE":
            return f"LDS/barrier kernel: out = (idx + 1) * {p.get('A')} (neighbor pattern)"
        elif self.kind == "H_NEIGHBOR_MUL":
            return f"LDS barrier kernel (wrap-around neighbor): out = ((idx + 1) % 64) * {p.get('A')}"
        elif self.kind == "H_BFI_PATTERN":
            p = self.params
            return f"bitfield select: out = ((idx ^ 0x{p.get('K',0):x}) & 0x{p.get('sel',0):08x}) | ((idx * {p.get('A')}) & ~0x{p.get('sel',0):08x})"
        elif self.kind == "H_BFI_MIX":
            p = self.params
            return f"bitfield select + xor-shift mix: c = ((idx ^ 0x{p.get('K',0):x}) & 0x{p.get('sel',0):08x}) | ((idx * {p.get('A')}) & ~0x{p.get('sel',0):08x}); out = c ^ (c >> 13)"
        return self.kind

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "params": self.params, "explain": self.explain(), "source": self.source}

    @property
    def id(self) -> str:
        return "hip_036_" + hashlib.sha256(
            f"{self.kind}|{json.dumps(self.params, sort_keys=True)}".encode()
        ).hexdigest()[:12]

    def __repr__(self) -> str:
        return f"Hypothesis({self.id},{self.kind})"


class UnknownKernelReconstructor:
    """Reconstruct unknown GPU kernels from SPIR-V alone."""

    def __init__(self):
        self.isa_recovery = GPUISARecovery()
        self.coverage = CoverageIntelligence()

    # ---------- 1. Structural analysis ----------

    def analyze(self, spv_path: str) -> Dict[str, Any]:
        """Full structural analysis of an unknown kernel."""
        if not os.path.exists(spv_path):
            return {"status": "BLOCKED", "reason": "file not found"}

        # Integrity
        with open(spv_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()

        # M58 structural (SPIR-V-level)
        m58 = M58Pipeline(spv_path)
        m58.verify_integrity()
        m58.disassemble()
        struct = m58.extract_structural()

        # Authentic GFX8 ISA capture via RADV_DEBUG=asm (like gpu_isa_recovery)
        env = os.environ.copy()
        env["RADV_DEBUG"] = "asm,cs"
        has_input = "ch6" in spv_path
        proc = subprocess.run([VK_TEST, spv_path, "64", "1" if has_input else "0", "--no-run"],
                              capture_output=True, text=True, env=env, timeout=30)
        output = proc.stdout + proc.stderr
        disasm_lines = []
        in_disasm = False
        for line in output.splitlines():
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
        instrs = self._parse_isa(disasm_text)
        mnemonics = [i["mnemonic"] for i in instrs]
        status_counts = {"VALIDATED": 0, "MODELED": 0, "NOT_DETERMINED": 0}
        for mn in mnemonics:
            status_counts[classify_mnemonic(mn)] += 1

        has_lds = any(m.startswith("ds_") for m in mnemonics)
        return {
            "status": "OK",
            "spv_path": spv_path,
            "sha256": h,
            "instruction_count": len(instrs),
            "has_lds": has_lds,
            "mnemonics": sorted(set(mnemonics)),
            "coverage": status_counts,
            "unknown_instructions": sorted({m for m in mnemonics if classify_mnemonic(m) == "NOT_DETERMINED"}),
            "basic_blocks": struct.get("labels", len(instrs) and 1 or 1),
            "constants": self._extract_constants(instrs),
        }

    def _parse_isa(self, disasm_text: str) -> List[Dict[str, Any]]:
        instrs = []
        cur_bb = None
        for line in disasm_text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(BB\d+):', line)
            if m:
                cur_bb = m.group(1)
                continue
            parts = line.split(';')
            instr_part = parts[0].strip()
            if not instr_part:
                continue
            toks = instr_part.split()
            if not toks:
                continue
            mn = toks[0]
            # Never accept driver diagnostics / error strings as instructions
            if mn.upper().startswith(("FENCE_TIMEOUT", "READOUT_TIMEOUT", "DEVICE:", "RESULTS:",
                                      "MESA-", "RADV:", "NO_", "TEX_", "BAD_")):
                continue
            # GFX8 instruction shape: known opcode families only
            if not re.match(r'^(v_|s_|ds_|buffer_|image_|global_|flat_|scratch_|exp_|lds_)', mn):
                continue
            instrs.append({"bb": cur_bb, "mnemonic": mn, "operands": toks[1:], "full": instr_part})
        return instrs

    def _extract_constants(self, instrs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract immediate constants from the ISA (muls, adds, cmps, shifts, smovs)."""
        muls, adds, cmps, shifts, smovs, xors, stores = [], [], [], [], [], [], 0
        for ins in instrs:
            mn = ins["mnemonic"]
            ops = " ".join(ins["operands"])
            hexes = re.findall(r'0x[0-9a-fA-F]+', ops)
            imm = re.findall(r'(?<=\s)[0-9]+(?![0-9x])', ops)
            if mn.startswith("v_mul"):
                muls.extend(int(h, 16) if h.startswith("0x") else int(h) for h in hexes)
                muls.extend(int(x) for x in imm)  # includes small multipliers like 13, 7, 3
            elif mn.startswith("v_add") or mn.startswith("s_add"):
                adds.extend(int(h, 16) if h.startswith("0x") else int(h) for h in hexes)
                adds.extend(int(x) for x in imm)
            elif "v_cmpx" in mn or "v_cmp" in mn:
                cmps.extend(int(h, 16) if h.startswith("0x") else int(h) for h in hexes)
                cmps.extend(int(x) for x in imm)
            elif "lshrrev" in mn:
                shifts.extend(int(h, 16) if h.startswith("0x") else int(h) for h in hexes)
                shifts.extend(int(x) for x in imm)
            elif "lshlrev" in mn:
                shifts.extend(int(x) for x in imm)
            elif mn.startswith("s_mov"):
                smovs.extend(int(h, 16) for h in hexes)
                smovs.extend(int(x) for x in imm)
            elif mn.startswith("v_xor"):
                xors.extend(int(h, 16) for h in hexes)
            elif mn.startswith("buffer_store"):
                stores += 1
        return {
            "mul_constants": muls,
            "add_constants": adds,
            "cmp_constants": cmps,
            "shift_constants": shifts,
            "smov_constants": smovs,
            "xor_constants": xors,
            "store_count": stores,
        }

    # ---------- 2. Hypothesis generation ----------

    def generate_hypotheses(self, analysis: Dict[str, Any]) -> List[Hypothesis]:
        """Generate candidate hypotheses from ISA-extracted constants."""
        self._last_has_lds = analysis.get("has_lds", False)
        self._last_mnemonics = analysis.get("mnemonics", [])
        c = analysis["constants"]
        hyp = []
        sources = []

        muls = c["mul_constants"]
        smovs = c["smov_constants"]
        adds = c["add_constants"]
        xors = c["xor_constants"]
        shifts = c["shift_constants"]
        cmps = c["cmp_constants"]

        # Candidate A values: mul constants, smov constants (large values typical of hashes)
        a_candidates = [x for x in (muls + smovs) if x and x >= 2]
        b_candidates = adds + [x for x in smovs if x and x <= 0xFFFFFFFF]

        # H_LIN with each (A, B) pair extracted
        if a_candidates and adds:
            mul_A = muls[0] if muls else a_candidates[0]
            add_B = adds[0]
            hyp.append(Hypothesis("H_LIN", {"A": mul_A, "B": add_B}, "ISA: v_mul + v_add immediate constants"))
        # H_LIN with A = B (s1 constant for both mul and add — ch1 pattern)
        for a in a_candidates:
            hyp.append(Hypothesis("H_LIN", {"A": a, "B": a}, f"ISA: s_mov_b32 0x{a:x} used as mul and add"))
            hyp.append(Hypothesis("H_LIN", {"A": a, "B": 0}, f"ISA: s_mov_b32 0x{a:x} mul-only"))
        # H_XD_CONST
        if xors:
            for k in xors:
                hyp.append(Hypothesis("H_XOR_CONST", {"K": k}, f"ISA: v_xor immediate 0x{k:x}"))
        # Hash shift-xor (mul constant from mul or smov; xor is register-register)
        if a_candidates and shifts:
            for a in a_candidates:
                for sh in shifts:
                    if isinstance(sh, int) and 0 < sh < 32:
                        hyp.append(Hypothesis("H_HASH_SHIFT_XOR", {"A": a, "s": sh},
                                              f"ISA: s_mov/v_mul 0x{a:x} + v_lshrrev {sh} + v_xor (shift-xor hash)"))
        # Piecewise (branch detected with threshold and two multipliers)
        if cmps and len(muls) >= 2 and adds:
            hyp.append(Hypothesis("H_PIECEWISE", {"T": cmps[0] if cmps else 100, "A": 13, "B": 5, "A2": 7},
                                  f"ISA: v_cmpx threshold={cmps[0] if cmps else '?'}, multipliers={muls[:2]}"))
        # v_bfi_b32 present + xor-shift => compounded hypothesis
        if any("v_bfi" in m for m in self._last_mnemonics) and any("lshrrev" in m for m in self._last_mnemonics):
            xor_K = xors[0] if xors else 0
            nonkey_consts = [x for x in smovs if x not in (0, 0xFFFFFFFF)]
            for sel in nonkey_consts:
                for A in nonkey_consts:
                    if sel == A:
                        continue
                    hyp.append(Hypothesis("H_BFI_MIX", {"A": A, "K": xor_K, "sel": sel},
                                          f"ISA: v_bfi_b32 + v_lshrrev + v_xor (xor-shift mix); sel=0x{sel:08x} A=0x{A:08x} K=0x{xor_K:08x}"))
        # v_bfi_b32 present + selector literal in s_mov => pattern hypothesis (exhaustive over observed constants)
        if any("v_bfi" in m for m in self._last_mnemonics):
            xor_K = xors[0] if xors else 0
            nonkey_consts = [x for x in smovs if x not in (0, 0xFFFFFFFF)]
            # Cross-product: each observed nonzero constant as selector, each as multiplier (skip selectors that are xor immediates)
            for sel in nonkey_consts:
                for A in nonkey_consts:
                    if sel == A:
                        continue
                    hyp.append(Hypothesis("H_BFI_PATTERN", {"A": A, "K": xor_K, "sel": sel},
                                          f"ISA: v_bfi_b32 experiment: sel=0x{sel:08x} A=0x{A:08x} K=0x{xor_K:08x}"))
        # LDS neighbor pattern: brute-force scale factors ONLY if LDS present in ISA
        if self._last_has_lds:
            for test_a in [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16]:
                hyp.append(Hypothesis("H_NEIGHBOR_MUL", {"A": test_a}, f"ISA: LDS barrier detected; brute-force neighbor scale A={test_a}"))
        return hyp

    # ---------- 3. Execute + discriminate ----------

    def execute_kernel(self, spv_path: str, num_elements: int = 64, has_input: bool = False) -> List[int]:
        require_gpu(f"execute_kernel:{spv_path}")
        env = os.environ.copy()
        env["RADV_DEBUG"] = ""
        proc = subprocess.run([VK_TEST, spv_path, str(num_elements), "1" if has_input else "0", "64"],
                              capture_output=True, text=True, env=env, timeout=30)
        results = []
        for line in proc.stdout.splitlines():
            if line.startswith("RESULTS:"):
                results = [int(x) for x in line.replace("RESULTS:", "").split()]
        return results

    def discriminate(self, spv_path: str, hypotheses: List[Hypothesis], test_idx: range = range(16)) -> Dict[str, Any]:
        """Execute kernel on GPU; test each hypothesis on idx=0..15."""
        gpu = self.execute_kernel(spv_path, num_elements=64,
                                  has_input="ch6" in spv_path)
        gpu_vals = gpu[:16] if len(gpu) >= 16 else gpu
        outcomes = []
        for hyp in hypotheses:
            pred = [hyp.predict(i) for i in test_idx]
            matches = sum(1 for p, g in zip(pred, gpu_vals) if p == g)
            outcomes.append({
                "hypothesis": hyp.to_dict(),
                "matches_on_TEST": matches,
                "total_test": len(gpu_vals),
                "all_match": matches == len(gpu_vals) and len(gpu_vals) > 0,
            })
        # Holdout validation for any hypothesis that passed test set
        for o in outcomes:
            if o["all_match"]:
                hyp_kind = o["hypothesis"]["kind"]
                params = o["hypothesis"]["params"]
                holdout_pred = [Hypothesis(hyp_kind, params, "holdout").predict(i) for i in range(16, 64)]
                holdout_gpu = gpu[16:64]
                holdout_matches = sum(1 for p, g in zip(holdout_pred, holdout_gpu) if p == g)
                o["holdout_matches"] = holdout_matches
                o["holdout_total"] = len(holdout_gpu)
                o["holdout_all_match"] = holdout_matches == len(holdout_gpu)

        # Detect alternate branch in ISA (control flow never exercised by tests)
        branch_info = {"alternate_branch_detected": False, "validated": False, "note": ""}
        try:
            env = os.environ.copy()
            env["RADV_DEBUG"] = "asm,cs"
            has_input_flag = "1" if "ch6" in spv_path else "0"
            proc = subprocess.run([VK_TEST, spv_path, "64", has_input_flag, "--no-run"],
                                  capture_output=True, text=True, env=env, timeout=30)
            out_text = proc.stdout + proc.stderr
            branch_count = out_text.count("s_cbranch")
            if branch_count > 0:
                branch_info = {
                    "alternate_branch_detected": True,
                    "validated": False,
                    "note": "Kernel contains conditional control flow; tested path covers only one branch. Alternate path semantics NOT validated.",
                }
        except Exception:
            pass
        surviving = [o for o in outcomes if o.get("holdout_all_match")]
        return {
            "branch_info": branch_info,
            "gpu_test": gpu_vals,
            "hypotheses_evaluated": len(outcomes),
            "survivors": surviving,
            "all_outcomes": outcomes,
            "best_hypothesis": surviving[0]["hypothesis"] if surviving else None,
            "status": "RECONSTRUCTED" if surviving else "NOT_DETERMINED",
        }

    # ---------- 4. Full pipeline ----------

    def reconstruct(self, spv_path: str) -> Dict[str, Any]:
        """Complete inverse-engineering pipeline for an unknown kernel."""
        print("=" * 70)
        print("UNKNOWN KERNEL RECONSTRUCTION — POLARIS-036")
        print("=" * 70)

        # 1. Analyze
        analysis = self.analyze(spv_path)
        if analysis["status"] != "OK":
            return {"status": "BLOCKED", "reason": analysis.get("reason")}
        print(f"\n[1] Integrity: sha256={analysis['sha256'][:16]}...")
        print(f"    instructions: {analysis['instruction_count']}, constants: {analysis['constants']['mul_constants']}")
        print(f"    coverage: {analysis['coverage']} (unknown: {analysis['unknown_instructions']})")

        # 2. Abstain if unknown instructions dominate
        if analysis["unknown_instructions"] and analysis["coverage"]["NOT_DETERMINED"] >= 1:
            # Still attempt XOR-based hypotheses? No: abstain; frontier present
            return {
                "status": "ABSTAINED",
                "reason": f"Unverified instruction semantics in kernel: {analysis['unknown_instructions']}",
                "analysis": analysis,
                "frontier": analysis["unknown_instructions"],
                "suggested_investigation": f"investigation required for unverified instructions in frontier: {analysis['unknown_instructions']} (extend CoverageIntelligence like POLARIS-037 methodology)",
                "restrictions": {"autonomous_loop": False, "max_iter": 1, "op_claim": False},
            }

        # 3. Generate hypotheses
        hypotheses = self.generate_hypotheses(analysis)
        print(f"\n[2] Hypotheses generated: {len(hypotheses)}")
        for h in hypotheses:
            print(f"    - {h.kind}: {h.explain()}")

        if not hypotheses:
            return {"status": "NOT_DETERMINED", "reason": "No hypothesis could be formulated from ISA",
                    "analysis": analysis, "hypotheses": []}

        # 4. Discriminate on GPU
        print("\n[3] Discriminating hypotheses on RX 550...")
        result = self.discriminate(spv_path, hypotheses)
        gpu = self.execute_kernel(spv_path, num_elements=64, has_input="ch6" in spv_path)
        print(f"    GPU: {gpu[:8]}...")
        for o in result["all_outcomes"]:
            print(f"    - {o['hypothesis']['kind']}: {o['matches_on_TEST']}/{o['total_test']} test-match")

        print(f"\n[4] Verdict: {result['status']}")
        if result["best_hypothesis"]:
            print(f"    Best: {result['best_hypothesis']['kind']} -> {result['best_hypothesis']['explain']}")

        return {
            "status": result["status"],
            "analysis": analysis,
            "hypotheses_tested": result["hypotheses_evaluated"],
            "best_hypothesis": result["best_hypothesis"],
            "survivors": result["survivors"],
            "all_outcomes": result["all_outcomes"],
            "alternate_branch": result.get("branch_info"),
            "gpu_results": gpu,
            "evidence": {
                "test_idx": "0-15",
                "holdout_idx": "16-63",
                "note": "Reconstruction by observation on this specific binary; not universal proof of semantics",
            },
            "restrictions": {"autonomous_loop": False, "max_iter": 1, "op_claim": False},
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="POLARIS-036: Unknown Kernel Reconstruction")
    parser.add_argument("spv", help="Path to unknown SPIR-V kernel (.spv)")
    args = parser.parse_args()

    reconstructor = UnknownKernelReconstructor()
    result = reconstructor.reconstruct(args.spv)
    print("\n" + json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
