#!/usr/bin/env python3
"""POLARIS-035: Coverage-Aware Autonomous GPU Evolution.

GPU Evolution that knows what it knows, what it doesn't, and what to investigate next.
Extends SemanticSafeEvolution (POLARIS-033) WITHOUT duplicating it.

Coverage Intelligence:
  - VALIDATED: instruction semantics verified against GPU (conditional/loop_sum/loop_nested/early_return/multi_path @ 16/16)
  - MODELED: implemented in formal model, pending extended validation
  - NOT_DETERMINED: semantics not verified; system abstains from fabrication

Flow:
  isa capture -> coverage analysis -> admissible transforms -> variant generation ->
  compile -> GPU execution -> differential validation -> semantic verdict ->
  performance (only if valid) -> selection -> knowledge persistence (AGUA/file)

Restricciones: autonomous_loop=False, max_iter=1, op_claim=False, DB_AUTH BLOCKED, W5 BLOCKED.
Nothing here activates unattended execution; 'autonomous' refers to semantic self-direction
within a single validated iteration.
"""
from __future__ import annotations
import os, json, time, hashlib, sys, tempfile
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import Counter

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.semantic_safe_evolution import SemanticSafeEvolution, SemanticValidator
from rxre.polaris12.gcn4_formal_semantics import GCN4FormalSemantics
from rxre.polaris12.gpu_isa_recovery import GPUISARecovery

ISA_DIR = "/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/canonical/isa"

# Canonical semantic status of every instruction present in captured ISAs.
# VALIDATED: model matches GPU 16/16 on all canonical shaders using it.
# MODELED: exact implementation exists; extended validation pending.
# NOT_DETERMINED: no verified semantics; system must abstain.
INSTRUCTION_STATUS = {
    # scalar
    "s_lshl": "VALIDATED", "s_mov": "VALIDATED", "s_load": "VALIDATED",
    "s_add": "VALIDATED", "s_andn2": "VALIDATED", "s_waitcnt": "VALIDATED",
    "s_branch": "VALIDATED", "s_cbranch": "VALIDATED", "s_endpgm": "VALIDATED",
    "s_barrier": "VALIDATED",   # semantics formalized (execution barrier), validated via WG=128/256
    "s_bfm": "MODELED",         # new in POLARIS-034, not yet GPU-validated by direct test
    # vector
    "v_add": "VALIDATED", "v_cmpx": "VALIDATED", "v_cmp": "VALIDATED",
    "v_min": "VALIDATED", "v_mov": "VALIDATED", "v_mul": "VALIDATED",
    "v_lshlrev": "VALIDATED", "v_lshrrev": "VALIDATED", "v_and": "VALIDATED",
    "v_cndmask": "VALIDATED", "v_xor": "MODELED", "v_or": "MODELED", "v_sub": "MODELED",
    "v_bfi": "VALIDATED",      # POLARIS-037: validated on RX 550, 72 micro-experiments
    # memory
    "buffer_store": "VALIDATED", "buffer_load": "VALIDATED",
    "ds_write": "VALIDATED", "ds_read": "VALIDATED",
}


def classify_mnemonic(mnemonic: str) -> str:
    """Classify an instruction by semantic validation status."""
    for prefix, status in INSTRUCTION_STATUS.items():
        if mnemonic.startswith(prefix):
            return status
    return "NOT_DETERMINED"


class CoverageIntelligence:
    """Recognize what RXRE knows, what it doesn't, and what to investigate."""

    def __init__(self):
        self.semantics = GCN4FormalSemantics()

    def analyze_shader(self, shader_name: str) -> Dict[str, Any]:
        """Analyze semantic coverage of a shader from its authentic ISA."""
        isa_text = self._load_isa(shader_name)
        instructions = self.semantics.analyzer.analyze_shader(shader_name)
        if instructions["status"] != "OK":
            return {"status": "BLOCKED", "reason": instructions.get("reason", "no ISA")}

        mnemonic_counts = Counter(ins["mnemonic"] for ins in instructions["instructions"])
        classified = Counter()
        per_instr = []
        for ins in instructions["instructions"]:
            st = classify_mnemonic(ins["mnemonic"])
            classified[st] += 1
            per_instr.append({"mnemonic": ins["mnemonic"], "status": st})

        total = len(instructions["instructions"])
        validated = classified.get("VALIDATED", 0)
        modeled = classified.get("MODELED", 0)
        unknown = classified.get("NOT_DETERMINED", 0)
        return {
            "status": "OK",
            "shader": shader_name,
            "total_instructions": total,
            "counts": dict(classified),
            "validated": validated,
            "modeled": modeled,
            "not_determined": unknown,
            "coverage_pct": round(100.0 * validated / total, 2) if total else 0.0,
            "not_determined_instructions": sorted({ins["mnemonic"] for ins in instructions["instructions"]
                                                   if classify_mnemonic(ins["mnemonic"]) == "NOT_DETERMINED"}),
            "frontier": unknown > 0 or modeled > 0,
            "per_instruction": per_instr,
        }

    def admissible_transforms(self, shader_name: str) -> Dict[str, Any]:
        """Return which transformations are admissible for this shader.

        Transformations touching NOT_DETERMINED instructions are out of domain.
        """
        cov = self.analyze_shader(shader_name)
        if cov["status"] != "OK":
            return {"admissible": [], "reason": cov.get("reason")}
        undetermined = cov["not_determined_instructions"]
        # Transformations admissible only when they don't cross the unknown frontier
        admissible = []
        if not undetermined:
            admissible = ["fma", "addform", "inline", "workgroup_size", "loop_unroll_candidate", "reg_alloc"]
        else:
            admissible = ["workgroup_size"]  # still check; may fail, but only if it doesn't change semantics
        return {
            "shader": shader_name,
            "admissible": admissible,
            "blocked_by_unknown": undetermined,
            "frontier": bool(undetermined),
            "coverage_pct": cov["coverage_pct"],
        }

    def next_investigation(self) -> Dict[str, Any]:
        """Autonomous experiment selection: which capability closes the biggest frontier."""
        # Frontier after POLARIS-037: v_bfi_b32 VALIDATED. Next candidate is the
        # largest remaining unverified semantic item: s_barrier multi-wavefront verification.
        candidates = [
            {
                "investigation": "s_barrier semantics verification for WG>=128",
                "gap": "MODELED->VALIDATED (WG>=128)",
                "occurrences": 2,
                "blocking": "multi-wavefront barrier guarantees, WG=128/256 unknown-kernel recon",
                "experiment": "WG=128 cross-lane LDS dependency test with barrier()",
                "discriminative_power": "HIGH",
            },
        ]
        candidates.sort(key=lambda c: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[c["discriminative_power"]], reverse=True)
        return {"selected": candidates[0], "frontier_items": candidates}

    def _load_isa(self, shader_name: str) -> str:
        for candidate in [f"{ISA_DIR}/{shader_name}_isa_full.txt"]:
            if os.path.exists(candidate):
                with open(candidate) as f:
                    return f.read()
        # Fall back to /tmp/rxre_gpu_cf (bitops/laneops copied in POLARIS-034)
        for candidate in [f"/tmp/rxre_gpu_cf/{shader_name}_isa_full.txt"]:
            if os.path.exists(candidate):
                with open(candidate) as f:
                    return f.read()
        return ""


class CoverageAwareEvolution(SemanticSafeEvolution):
    """Semantic-Safe Evolution + Coverage Intelligence + autonomous experiment selection.

    Does NOT activate unattended autonomous_loop; bounded to one validated iteration.
    """

    def __init__(self):
        super().__init__()
        self.coverage = CoverageIntelligence()
        self.knowledge_path = os.path.join(self.evidence_dir, "evolution_knowledge.json")
        self.knowledge = self._load_knowledge()

    def run_with_coverage(self, base_shader: str = "conditional", max_variants: int = 8) -> Dict[str, Any]:
        """Run evolution gated by coverage intelligence.

        A. Fully covered shader -> evolve automatically.
        B. Shader containing NOT_DETERMINED instructions -> abstain/classify NOT_DETERMINED.
        """
        print("=" * 70)
        print("COVERAGE-AWARE EVOLUTION — POLARIS-035")
        print("=" * 70)

        # 1. Coverage intelligence
        cov = self.coverage.analyze_shader(base_shader)
        adj = self.coverage.admissible_transforms(base_shader)
        print(f"\nCoverage analysis for {base_shader}:")
        print(f"  instructions: {cov.get('total_instructions')}")
        print(f"  validated: {cov.get('validated')}, modeled: {cov.get('modeled')}, NOT_DETERMINED: {cov.get('not_determined')}")
        print(f"  coverage: {cov.get('coverage_pct')}%")
        print(f"  frontier: {'YES (abstain where unknown)' if cov.get('frontier') else 'NO (full domain)'}")
        print(f"  admissible transforms: {adj['admissible']}")

        # 1b. ABSTAIN only when NOT_DETERMINED instructions are present (v_bfi).
        #     MODELED-only shaders may proceed; differential validation decides.
        if cov.get("not_determined", 0) > 0:
            self._persist_knowledge("frontier_abstain", {"shader": base_shader,
                                                        "frontier": cov["not_determined_instructions"]})
            return {
                "status": "ABSTAINED",
                "reason": f"NOT_DETERMINED instructions in domain: {cov['not_determined_instructions']}",
                "coverage": cov,
                "admissible_transforms": adj["admissible"],
                "validation_verdict": "NOT_DETERMINED",
                "suggested_investigation": self.coverage.next_investigation()["selected"],
                "restrictions": {"autonomous_loop": False, "max_iter": 1, "op_claim": False},
            }

        # 3. Evolve only within admissible domain (bounded, 1 iteration)
        result = self.run_evolution(base_shader=base_shader, max_variants=max_variants)

        # 4. Continuous learning: persist what worked / what didn't
        learning = {
            "base_shader": base_shader,
            "coverage_pct": cov.get("coverage_pct"),
            "semantically_valid": result.get("semantically_valid"),
            "rejected": result.get("rejected"),
            "best": result.get("best"),
            "timestamp": datetime.now().isoformat(),
        }
        self._persist_knowledge("evolution_round", learning)

        return {
            "status": "OK",
            "coverage": cov,
            "admissible_transforms": adj["admissible"],
            "evolution": result,
            "learning": learning,
            "next_investigation": self.coverage.next_investigation()["selected"],
            "restrictions": {"autonomous_loop": False, "max_iter": 1, "op_claim": False},
        }

    def _persist_knowledge(self, name: str, data: Dict[str, Any]):
        """Continuous learning: append to evolution knowledge base."""
        entries = []
        if os.path.exists(self.knowledge_path):
            try:
                with open(self.knowledge_path) as f:
                    entries = json.load(f)
            except Exception:
                entries = []
        entries.append({"name": name, "data": data, "timestamp": datetime.now().isoformat()})
        with open(self.knowledge_path, "w") as f:
            json.dump(entries, f, indent=2)
        self.knowledge = entries

    def _load_knowledge(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.knowledge_path):
            try:
                with open(self.knowledge_path) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def recall_knowledge(self, topic: str) -> List[Dict[str, Any]]:
        """Retrieve prior knowledge relevant to a topic."""
        hits = []
        for entry in self.knowledge:
            blob = json.dumps(entry).lower()
            if topic.lower() in blob:
                hits.append(entry)
        return hits


def main():
    import argparse
    parser = argparse.ArgumentParser(description="POLARIS-035: Coverage-Aware Evolution")
    parser.add_argument("--shader", default="conditional", help="Base shader")
    parser.add_argument("--only-analysis", action="store_true", help="Only coverage analysis")
    args = parser.parse_args()

    engine = CoverageAwareEvolution()

    if args.only_analysis:
        print("=" * 70)
        print("COVERAGE ANALYSIS (read-only)")
        print("=" * 70)
        for shader in ["conditional", "loop_sum", "bitops", "laneops", "barrier_sync"]:
            cov = engine.coverage.analyze_shader(shader)
            adj = engine.coverage.admissible_transforms(shader)
            print(f"{shader}: coverage={cov.get('coverage_pct')}% frontier={cov.get('frontier')} "
                  f"NOT_DET={cov.get('not_determined_instructions')} admissible={adj['admissible']}")
        return

    result = engine.run_with_coverage(base_shader=args.shader)
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
