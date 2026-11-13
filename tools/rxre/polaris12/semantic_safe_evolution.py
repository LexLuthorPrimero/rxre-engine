#!/usr/bin/env python3
"""POLARIS-033: Semantic-Safe GPU Evolution.

Connects GPU Evolution Engine with the formal semantic model (GCN4).
Variants are validated semantically before competing on performance.
Rejects variants with divergences; classifies non-validable as NOT_DETERMINED.

Reutiliza: gpu_evolution_engine, gcn4_formal_semantics, gpu_isa_recovery,
differential_validator, M58, ROUTER, TIERRA, AGUA.

Restricciones: DB_AUTH BLOCKED, W5 BLOCKED, autonomous_loop=False, max_iter=1, op_claim=False.
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, sys, tempfile, math, re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.gcn4_formal_semantics import GCN4FormalSemantics
from rxre.polaris12.gpu_isa_recovery import GPUISARecovery
from rxre.polaris12.gpu_evolution_engine import GPUShaderForge, GPUVariantTester, GPUEvolutionEngine

SHADERS = ["conditional", "loop_sum", "loop_nested", "barrier_sync", "early_return", "multi_path"]
SPV_DIR = "/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/canonical"
from rxre.polaris12.gpu_availability import require_gpu, GPUSuspended

VK_TEST = "/home/lucas/Escritorio/rxre/tools/rxre/harness/bin/vk_cf_test"


class SemanticValidator:
    """Validates shader variants against the formal semantic model."""

    def __init__(self):
        self.semantics = GCN4FormalSemantics()
        self.isa_recovery = GPUISARecovery()
        self.validation_results = []

    def validate_variant(self, base_shader: str, variant_glsl: str, variant_id: str,
                         tmpdir: str) -> Dict[str, Any]:
        """Validate a variant against the formal model.

        Steps:
        1. Compile variant to SPIR-V
        2. Execute on GPU
        3. Compare against formal model prediction for base shader
        4. Classify: SEMANTICALLY_VALID, REJECTED, or NOT_DETERMINED
        """
        # 1. Compile
        tester = GPUVariantTester()
        compile_result = tester.compile_variant(variant_glsl, variant_id, tmpdir)
        if not compile_result.get("compiled") or not compile_result.get("spirv_valid"):
            return {
                "variant_id": variant_id,
                "status": "COMPILE_FAILED",
                "reason": compile_result.get("reason", "unknown"),
                "semantic_valid": False,
            }

        spv_path = compile_result["spv_path"]

        # 2. Execute on GPU
        has_input = (base_shader == "barrier_sync")
        gpu_result = self.isa_recovery.execute_gpu(base_shader, has_input=has_input, num_elements=16)
        # Also execute the variant
        variant_gpu = self._execute_variant(spv_path, has_input=has_input, num_elements=16)

        # 3. Get formal model prediction for base shader
        model_result = self.semantics.execute_model(base_shader, num_elements=16)

        # 4. Compare variant GPU vs base model
        base_model_vals = model_result["results"]
        variant_gpu_vals = variant_gpu.get("results", [])
        n = min(len(base_model_vals), len(variant_gpu_vals))
        matches = sum(1 for i in range(n) if base_model_vals[i] == variant_gpu_vals[i])
        mismatches = [(i, base_model_vals[i], variant_gpu_vals[i]) for i in range(n) if base_model_vals[i] != variant_gpu_vals[i]]

        # 5. Classify
        if len(mismatches) == 0 and n > 0:
            status = "SEMANTICALLY_VALID"
            semantic_valid = True
        elif len(mismatches) > 0:
            status = "REJECTED"
            semantic_valid = False
        else:
            status = "NOT_DETERMINED"
            semantic_valid = False

        result = {
            "variant_id": variant_id,
            "base_shader": base_shader,
            "status": status,
            "semantic_valid": semantic_valid,
            "base_model": base_model_vals[:8],
            "variant_gpu": variant_gpu_vals[:8],
            "matches": matches,
            "mismatches": len(mismatches),
            "total_compared": n,
            "mismatch_details": mismatches[:5],
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }
        self.validation_results.append(result)
        return result

    def _execute_variant(self, spv_path: str, has_input: bool = False, num_elements: int = 16) -> Dict[str, Any]:
        """Execute a variant shader on GPU."""
        import subprocess, os
        env = os.environ.copy()
        require_gpu(f"semantic_safe_evolution:{spv_path}")
        proc = subprocess.run(
            [VK_TEST, spv_path, str(num_elements), "1" if has_input else "0"],
            capture_output=True, text=True, env=env, timeout=30)
        results = []
        for line in proc.stdout.splitlines():
            if line.startswith("RESULTS:"):
                results = [int(x) for x in line.replace("RESULTS:", "").split()]
        return {"results": results, "num_results": len(results)}

    def validate_all_variants(self, base_shader: str, variants: List[Dict], tmpdir: str) -> Dict[str, Any]:
        """Validate all variants against the formal model."""
        results = []
        for v in variants:
            result = self.validate_variant(base_shader, v["glsl"], v["id"], tmpdir)
            results.append(result)
        valid = [r for r in results if r["status"] == "SEMANTICALLY_VALID"]
        rejected = [r for r in results if r["status"] == "REJECTED"]
        nd = [r for r in results if r["status"] == "NOT_DETERMINED"]
        return {
            "base_shader": base_shader,
            "total_variants": len(variants),
            "semantically_valid": len(valid),
            "rejected": len(rejected),
            "not_determined": len(nd),
            "valid_variants": [r["variant_id"] for r in valid],
            "rejected_variants": [r["variant_id"] for r in rejected],
            "results": results,
        }


class SemanticSafeEvolution:
    """GPU Evolution Engine with semantic safety.

    Extends GPUEvolutionEngine with formal semantic validation.
    Variants must pass semantic validation before competing on performance.
    """

    def __init__(self):
        self.forge = GPUShaderForge()
        self.tester = GPUVariantTester()
        self.validator = SemanticValidator()
        self.semantics = GCN4FormalSemantics()
        self.results = []
        self.knowledge = []
        self.best_variant = None
        self.baseline_median = None
        self.iteration = 0
        self.max_iterations = 5
        self.evidence_dir = os.path.join(ROOT, 'evidence', 'semantic_safe_evolution')
        os.makedirs(self.evidence_dir, exist_ok=True)

    def run_evolution(self, base_shader: str = "conditional", max_variants: int = 8) -> Dict[str, Any]:
        """Run semantic-safe evolution on a base shader.

        Flow:
        1. Generate variants
        2. Compile each variant
        3. Validate semantically (model + GPU comparison)
        4. REJECT variants with divergences
        5. Classify non-validable as NOT_DETERMINED
        6. Measure performance only for valid variants
        7. Select best among valid variants
        """
        print("=" * 70)
        print("SEMANTIC-SAFE GPU EVOLUTION — POLARIS-033")
        print("=" * 70)
        print(f"\nBase shader: {base_shader}")
        print(f"Max variants: {max_variants}")

        self.iteration += 1

        # 1. Get base GLSL (from the shader template)
        # For now, use the conditional shader's GLSL
        base_glsl = self._get_base_glsl(base_shader)
        if base_glsl is None:
            return {"status": "FAILED", "reason": "No base GLSL"}

        # 2. Generate variants
        print("\n[1] Generating variants...")
        variants = self.forge.generate_variants(base_glsl)
        print(f"  Generated {len(variants)} unique variants")
        for v in variants:
            print(f"    - {v['id']}: {v.get('transforms', [])}")

        # 3. Compile all variants
        print("\n[2] Compiling variants...")
        tmpdir = tempfile.mkdtemp(prefix='sse_')
        compiled = []
        for v in variants:
            result = self.tester.compile_variant(v["glsl"], v["id"], tmpdir)
            if result.get("compiled") and result.get("spirv_valid"):
                compiled.append({"variant": v, "compile": result})
                print(f"  {v['id']}: COMPILED OK")
            else:
                print(f"  {v['id']}: COMPILE FAILED ({result.get('reason', 'unknown')})")

        # 4. Semantic validation
        print("\n[3] Semantic validation (model vs GPU)...")
        validation = self.validator.validate_all_variants(base_shader, variants, tmpdir)
        print(f"  Total: {validation['total_variants']}")
        print(f"  Semantically valid: {validation['semantically_valid']}")
        print(f"  Rejected: {validation['rejected']}")
        print(f"  Not determined: {validation['not_determined']}")
        for r in validation["results"]:
            print(f"    {r['variant_id']}: {r['status']} (matches={r['matches']}/{r['total_compared']})")

        # 5. Performance measurement (only for valid variants)
        print("\n[4] Performance measurement (valid variants only)...")
        valid_ids = set(validation["valid_variants"])
        perf_results = []
        for v in variants:
            if v["id"] not in valid_ids:
                print(f"  {v['id']}: SKIPPED (not semantically valid)")
                continue
            var_result = self.tester.compile_variant(v["glsl"], v["id"], tmpdir)
            if var_result.get("compiled") and var_result.get("spirv_valid"):
                var_exec = self.tester.execute_variant(var_result["spv_path"], count=1024, reps=5)
                var_ok, var_reason = self.tester.verify_correctness(var_exec)
                var_result.update(var_exec)
                var_result["correct"] = var_ok
                perf_results.append({"id": v["id"], "result": var_result, "variant": v})
                print(f"  {v['id']}: median={var_exec.get('median_exec', 'N/A')}, correct={var_ok}")

        # 6. Select best among valid variants
        print("\n[5] Selecting best variant...")
        valid_perf = [r for r in perf_results if r["result"].get("correct", False) and r["result"].get("median_exec")]
        if not valid_perf:
            print("  No valid variants with performance data")
            best = None
        else:
            valid_perf.sort(key=lambda r: r["result"]["median_exec"])
            best = valid_perf[0]
            print(f"  Best: {best['id']} (median={best['result']['median_exec']:.6f}s)")

        # 7. Persist evidence
        print("\n[6] Persisting evidence...")
        ev_data = {
            "iteration": self.iteration,
            "base_shader": base_shader,
            "variants_tested": len(variants),
            "semantically_valid": validation["semantically_valid"],
            "rejected": validation["rejected"],
            "not_determined": validation["not_determined"],
            "best_variant": best["id"] if best else "baseline",
            "restrictions": {
                "DB_AUTH": "BLOCKED",
                "autonomous_loop": False,
                "max_iter": 1,
                "op_claim": False,
            },
            "semantic_coverage": {
                "instructions": 24,
                "shaders": 6,
                "note": "Semantic validation limited to validated domain",
            },
        }
        ev_path = self._persist_evidence(f"sse_iter{self.iteration}", ev_data)
        print(f"  Evidence: {ev_path}")

        # Summary
        print("\n" + "=" * 70)
        print("SEMANTIC-SAFE EVOLUTION — SUMMARY")
        print("=" * 70)
        print(f"  Iteration: {self.iteration}")
        print(f"  Base shader: {base_shader}")
        print(f"  Variants tested: {len(variants)}")
        print(f"  Semantically valid: {validation['semantically_valid']}")
        print(f"  Rejected: {validation['rejected']}")
        print(f"  Not determined: {validation['not_determined']}")
        print(f"  Best: {best['id'] if best else 'baseline'}")
        print(f"  Semantic coverage: 24 instructions, 6 shaders")
        print("=" * 70)

        return {
            "iteration": self.iteration,
            "base_shader": base_shader,
            "variants_tested": len(variants),
            "semantically_valid": validation["semantically_valid"],
            "rejected": validation["rejected"],
            "not_determined": validation["not_determined"],
            "best": best["id"] if best else "baseline",
            "validation": validation,
            "evidence": ev_path,
        }

    def _get_base_glsl(self, shader_name: str) -> Optional[str]:
        """Get base GLSL for a shader name."""
        # Map shader names to GLSL templates
        templates = {
            "conditional": '''#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx < 32u) {
        data[idx] = idx * 2u;
    } else if (idx < 48u) {
        data[idx] = idx + 100u;
    } else {
        data[idx] = idx - 48u;
    }
}
''',
            "loop_sum": '''#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    uint sum = 0u;
    for (uint i = 0u; i < idx && i < 64u; i++) {
        sum += i;
    }
    data[idx] = sum;
}
''',
        }
        return templates.get(shader_name)

    def _persist_evidence(self, name, data):
        """Persist evidence to file."""
        ev_path = os.path.join(self.evidence_dir, f'{name}_{int(time.time())}.json')
        evidence = {
            'mission': 'SEMANTIC_SAFE_EVOLUTION',
            'timestamp': datetime.now().isoformat(),
            'iteration': self.iteration,
            'data': data,
            'restrictions': {'DB_AUTH': 'BLOCKED', 'autonomous_loop': False, 'max_iter': 1, 'op_claim': False},
            'source': 'real_gpu_experiment',
            'device': 'AMD Radeon RX 550 / 550 Series (RADV POLARIS12)',
        }
        with open(ev_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        return ev_path


if __name__ == '__main__':
    engine = SemanticSafeEvolution()
    result = engine.run_evolution(base_shader="conditional")
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
