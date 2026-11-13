#!/usr/bin/env python3
"""POLARIS-038: Continuous Knowledge-Driven Evolution.

Closes the loop: investigate -> understand -> reconstruct -> validate ->
optimize -> learn -> investigate better.

Reuses: unknown_kernel_reconstruction (POLARIS-036), coverage_aware_evolution
(POLARIS-035), semantic_safe_evolution (POLARIS-033), GCN4FormalSemantics
(POLARIS-030). NO new parallel engines.

Knowledge store: append-only JSON with provenance; entries never silently
overwritten; supersession explicit. Survives restarts.

Restricciones: autonomous_loop=False, max_iter=1, op_claim=False,
DB_AUTH_ACTOR_M294 BLOCKED, W5 BLOCKED.
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, sys, tempfile, copy
from typing import Dict, Any, List, Optional
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.unknown_kernel_reconstruction import UnknownKernelReconstructor
from rxre.polaris12.coverage_aware_evolution import CoverageAwareEvolution, CoverageIntelligence, classify_mnemonic
from rxre.polaris12.gcn4_formal_semantics import GCN4FormalSemantics

KNOWLEDGE_PATH = "/tmp/rxre_knowledge_store.json"
JOURNAL_KINDS = {
    "instruction_semantics", "kernel_reconstruction", "evolution_result",
    "hypothesis_rejected", "gpu_result", "investigation_outcome",
    "program_discovery", "shader_module", "pipeline_structure",
    "dependency_edge", "gpu_render_capture", "gpu_availability",
}


class KnowledgeStore:
    """Append-only persistent knowledge with provenance."""

    def __init__(self, path: str = KNOWLEDGE_PATH):
        self.path = path
        self.entries = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def store(self, kind: str, key: str, payload: Dict[str, Any], provenance: Dict[str, Any]) -> str:
        """Store knowledge entry; never silently overwrite. Returns entry id."""
        assert kind in JOURNAL_KINDS, f"unknown kind {kind}"
        eid = hashlib.sha256(f"{kind}|{key}|{json.dumps(payload, sort_keys=True)}|{time.time()}".encode()).hexdigest()[:16]
        # Check identical entry already exists (dedup)
        for e in self.entries:
            if e["kind"] == kind and e["key"] == key and e["payload"] == payload:
                # augment provenance, keep original id
                return e["id"]
        entry = {
            "id": eid,
            "kind": kind,
            "key": key,
            "payload": payload,
            "provenance": provenance,
            "timestamp": datetime.now().isoformat(),
            "supersedes": None,
        }
        # Explicit supersession: new entry overrides older same key (old marked, kept)
        for e in self.entries:
            if e["kind"] == kind and e["key"] == key and e.get("superseded_by") is None:
                e["superseded_by"] = eid
                entry["supersedes"] = e["id"]
        self.entries.append(entry)
        self._save()
        return eid

    def query(self, kind: Optional[str] = None, key: Optional[str] = None, current_only: bool = False) -> List[Dict[str, Any]]:
        out = self.entries
        if kind:
            out = [e for e in out if e["kind"] == kind]
        if key:
            out = [e for e in out if e["key"] == key]
        if current_only:
            out = [e for e in out if e.get("superseded_by") is None]
        return out

    def count(self, kind: Optional[str] = None) -> int:
        return len(self.query(kind=kind, current_only=True))

    def rehydrate(self) -> Dict[str, int]:
        """Count recovered entries by kind (used on restart)."""
        kinds = {}
        for e in self.entries:
            if e.get("superseded_by") is None:
                kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        return kinds


class ContinuousKnowledgeEngine:
    """Integrated continuous cycle: investigate -> reconstruct -> validate -> evolve -> learn."""

    def __init__(self, knowledge_path: str = KNOWLEDGE_PATH):
        self.reconstructor = UnknownKernelReconstructor()
        # Instrument the reconstructor's GPU executions so reuse can be measured
        _orig_execute = self.reconstructor.execute_kernel
        def _counted_execute(*args, **kwargs):
            self.gpu_executions += 1
            return _orig_execute(*args, **kwargs)
        self.reconstructor.execute_kernel = _counted_execute

        self.coverage = CoverageIntelligence()
        self.evolution = CoverageAwareEvolution()
        self.semantics = GCN4FormalSemantics()
        self.knowledge = KnowledgeStore(knowledge_path)
        self.gpu_executions = 0
        self.knowledge_hits = 0
        self.knowledge_misses = 0

    # ---------- instrumented GPU execution counter ----------

    def _execute_kernel_counted(self, spv_path: str, num_elements: int = 64, has_input: bool = False):
        self.gpu_executions += 1
        return self.reconstructor.execute_kernel(spv_path, num_elements=num_elements, has_input=has_input)

    def _instruction_key(self, spv_path: str) -> str:
        """Stable identifier: set of mnemonics hash (kernel identity for reuse)."""
        isa = self.reconstructor.isa_recovery.capture_isa(os.path.basename(spv_path).replace(".spv", "")) \
            if False else None
        analysis = self.reconstructor.analyze(spv_path)
        mnems = sorted(analysis.get("mnemonics", []))
        return hashlib.sha256("|".join(mnems).encode()).hexdigest()[:16]

    # ---------- investigation with reuse ----------

    def investigate_kernel(self, spv_path: str, from_knowledge_exchange: Optional[Dict] = None) -> Dict[str, Any]:
        """Investigate an unknown kernel; reuse validated knowledge before anything else."""
        print("\n[KERNEL INVESTIGATION]", os.path.basename(spv_path))
        spv_hash = hashlib.sha256(open(spv_path, "rb").read()).hexdigest()[:16]

        # 1. Check knowledge: any reconstruction of this exact kernel previously?
        prior = self.knowledge.query(kind="kernel_reconstruction", key=spv_hash, current_only=True)
        if prior:
            self.knowledge_hits += 1
            payload = prior[-1]["payload"]
            print(f"  Knowledge HIT: prior reconstruction found ({prior[-1]['id']}); reusing WITHOUT re-execution")
            return {
                "status": "FROM_KNOWLEDGE",
                "kernel": os.path.basename(spv_path),
                "reconstruction": payload,
                "gpu_executions_added": 0,
                "knowledge_entry": prior[-1]["id"],
                "provenance": prior[-1]["provenance"],
            }

        # 2. Miss: investigate from scratch, counting GPU executions
        self.knowledge_misses += 1
        print("  Knowledge MISS: investigating from scratch")
        before = self.gpu_executions
        result = self.reconstructor.reconstruct(spv_path)
        added = self.gpu_executions - before

        # 3. Persist the outcome as knowledge (success or failure — both are valuable)
        if result["status"] == "RECONSTRUCTED":
            hip = result.get("best_hypothesis") or {}
            self.knowledge.store(
                kind="kernel_reconstruction",
                key=spv_hash,
                payload={
                    "status": "RECONSTRUCTED",
                    "hypothesis_kind": hip.get("kind"),
                    "hypothesis_params": hip.get("params"),
                    "explain": hip.get("explain"),
                    "gpu_results_first8": result.get("gpu_results", [])[:8],
                    "alternate_branch": result.get("alternate_branch"),
                    "evidence": result.get("evidence"),
                },
                provenance={
                    "device": "AMD Radeon RX 550 / 550 Series (RADV POLARIS12)",
                    "kernel_sha256": spv_hash,
                    "method": "POLARIS-036/037 pipeline (analyze -> hypothesize -> discriminate -> holdout)",
                    "gpu_executions": added,
                },
            )
            self.knowledge.store(
                kind="gpu_result", key=spv_hash,
                payload={"results_first8": result.get("gpu_results", [])[:8], "count": len(result.get("gpu_results", []))},
                provenance={"device": "RX 550 RADV POLARIS12", "kernel_sha256": spv_hash},
            )
            # Explicit NOT_PROVEN: holdout match is domain evidence, not universal equivalence
            self.knowledge.store(
                kind="investigation_outcome", key=spv_hash,
                payload={"verdict": "RECONSTRUCTED", "domain": "idx 0-63 tested; holdout 16-63",
                         "universal_equivalence": "NOT_PROVEN", "alternate_branch": result.get("alternate_branch", {}).get("note", "")},
                provenance={"kernel_sha256": spv_hash})
        else:
            # Failure preserved too — knowledge about unknowns
            self.knowledge.store(
                kind="investigation_outcome", key=spv_hash,
                payload={"verdict": result["status"], "candidates_tested": result.get("hypotheses_tested", 0),
                         "survivors": 0,
                         "note": "No hypothesis survived holdout; uncertainty preserved."},
                provenance={"kernel_sha256": spv_hash, "method": "POLARIS-036/037"})

        return {
            "status": result["status"],
            "kernel": os.path.basename(spv_path),
            "reconstruction": result,
            "gpu_executions_added": added,
            "knowledge_entry": spv_hash,
            "provenance": {"kernel_sha256": spv_hash, "device": "RX 550 RADV POLARIS12"},
        }

    # ---------- guided evolution with accumulated knowledge ----------

    def guided_evolution(self, base_shader: str = "conditional") -> Dict[str, Any]:
        """Evolve base shader informed by validated coverage domain."""
        result = self.evolution.run_with_coverage(base_shader=base_shader)
        # Persist evolutionary evidence
        if result.get("status") == "OK":
            evo = result.get("evolution", {})
            self.knowledge.store(
                kind="evolution_result", key=base_shader,
                payload={"base_shader": base_shader, "best_variant": evo.get("best"),
                         "semantically_valid": evo.get("semantically_valid"),
                         "rejected": evo.get("rejected"),
                         "not_determined": evo.get("not_determined"),
                         "coverage_pct": result.get("coverage", {}).get("coverage_pct")},
                provenance={"device": "RX 550 RADV POLARIS12", "engine": "POLARIS-033/035"},
            )
        return result

    # ---------- semantic regression detector ----------

    def detect_regression(self, base_shader: str, variant_glsl: str, variant_id: str) -> Dict[str, Any]:
        """Any variant must match original semantics; divergence = REJECTED."""
        validator = self.evolution.validator
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="reg_")
        result = validator.validate_variant(base_shader, variant_glsl, variant_id, tmpdir)
        is_regression = (result.get("status") == "REJECTED")
        return {
            "variant_id": variant_id,
            "status": result.get("status"),
            "regression_detected": is_regression,
            "mismatches": result.get("mismatches", 0),
            "decision": "REJECT" if is_regression else "ACCEPT",
        }

    # ---------- full cycle ----------

    def run_cycle(self, spv_path: str, evolve_after: bool = True, base_shader: str = "conditional") -> Dict[str, Any]:
        """Full continuous cycle with knowledge reuse across stages."""
        print("=" * 70)
        print("CONTINUOUS KNOWLEDGE-DRIVEN EVOLUTION — POLARIS-038")
        print("=" * 70)
        print(f"Kernel: {spv_path}")
        print(f"Knowledge store: {self.knowledge.path} ({self.knowledge.count()} entries)")

        inv = self.investigate_kernel(spv_path)
        cycle = {"investigation": inv}

        if evolve_after:
            # Use validated domain informed by accumulated knowledge to evolve
            evo = self.guided_evolution(base_shader=base_shader)
            cycle["evolution"] = evo

        # Report knowledge state
        cycle["knowledge"] = {
            "hits": self.knowledge_hits,
            "misses": self.knowledge_misses,
            "gpu_executions": self.gpu_executions,
            "entries": self.knowledge.rehydrate(),
            "total_current": self.knowledge.count(),
        }
        print(f"\nKnowledge: hits={self.knowledge_hits}, misses={self.knowledge_misses}, "
              f"gpu_executions={self.gpu_executions}, entries={self.knowledge.rehydrate()}")
        return cycle


def main():
    import argparse
    parser = argparse.ArgumentParser(description="POLARIS-038: Continuous Knowledge-Driven Evolution")
    parser.add_argument("--kernel", default="/tmp/rxre_polaris36/kernels/ch8.spv")
    parser.add_argument("--evolve", action="store_true")
    parser.add_argument("--shader", default="conditional")
    args = parser.parse_args()

    engine = ContinuousKnowledgeEngine()
    cycle = engine.run_cycle(args.kernel, evolve_after=args.evolve, base_shader=args.shader)
    print("\n" + json.dumps(cycle, indent=2, default=str))


if __name__ == "__main__":
    main()
