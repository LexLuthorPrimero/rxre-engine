#!/usr/bin/env python3
"""POLARIS-027: GPU Control Flow Complexity — Shaders with dynamic branching,
loops, barriers, and multi-path execution on RX 550 (Polaris12/GFX8).

Extends M58 (SPIR-V pipeline) and POLARIS-026 (differential validation) to
handle shaders with control flow complexity beyond simple arithmetic.

Reutiliza: M58 pipeline, differential_validator, GPU Evolution Engine, ROUTER.
Restricciones: DB_AUTH BLOCKED, W5 BLOCKED (dynamic GPU access requires root),
autonomous_loop=False, max_iter=1, op_claim=False.

Shader categories:
  1. CONDITIONAL: if/else branches based on input data
  2. LOOP: for/while loops with dynamic iteration counts
  3. BARRIER: workgroup synchronization (barrier())
  4. NESTED: nested control flow (loops inside conditionals)
  5. MULTI_PATH: multiple execution paths with early returns
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math, random
from typing import Dict, Any, List, Optional, Tuple

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline
from rxre.polaris12.differential_validator import RXDifferentialValidator

# GLSL shader templates with control flow complexity
SHADER_TEMPLATES = {
    "conditional": """#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    uint val = idx;
    if (val < 32u) {
        data[idx] = val * 2u;
    } else if (val < 48u) {
        data[idx] = val + 100u;
    } else {
        data[idx] = val - 48u;
    }
}
""",
    "loop_sum": """#version 450
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
""",
    "loop_nested": """#version 450
layout(local_size_x = 32) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    uint result = 0u;
    for (uint i = 0u; i < 8u; i++) {
        for (uint j = 0u; j < 4u; j++) {
            if ((i + j) % 2u == 0u) {
                result += i * j;
            } else {
                result -= 1u;
            }
        }
    }
    data[idx] = result + idx;
}
""",
    "barrier_sync": """#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 0) buffer Input { uint indata[]; };
layout(set = 0, binding = 1) buffer Output { uint outdata[]; };

shared uint shared_buf[64];

void main() {
    uint idx = gl_LocalInvocationID.x;
    shared_buf[idx] = indata[gl_GlobalInvocationID.x];
    barrier();
    // Reverse reduction
    if (idx < 32u) {
        shared_buf[idx] += shared_buf[idx + 32u];
    }
    barrier();
    if (idx == 0u) {
        outdata[gl_WorkGroupID.x] = shared_buf[0];
    }
}
""",
    "early_return": """#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx >= 100u) {
        return;
    }
    uint val = idx;
    if (val == 0u) {
        data[idx] = 999u;
        return;
    }
    data[idx] = val * val;
}
""",
    "multi_path": """#version 450
layout(local_size_x = 64) in;
layout(set = 0, binding = 1) buffer Output { uint data[]; };

void main() {
    uint idx = gl_GlobalInvocationID.x;
    uint result = 0u;
    switch (idx % 4u) {
        case 0u: result = idx + 1u; break;
        case 1u: result = idx * 2u; break;
        case 2u: result = idx - 1u; break;
        default: result = 0u; break;
    }
    // Additional conditional
    if (result > 50u) {
        result = result / 2u;
    }
    data[idx] = result;
}
""",
}


class GPUControlFlowAnalyzer:
    """Analyze GPU shaders with control flow complexity.

    Generates SPIR-V from GLSL templates, analyzes structure via M58,
    and prepares for differential validation and ISA analysis.
    """

    def __init__(self, output_dir: str = "/tmp/rxre_gpu_cf"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results = []

    def compile_shader(self, name: str, glsl_source: str) -> Dict[str, Any]:
        """Compile GLSL to SPIR-V using glslangValidator."""
        glsl_path = os.path.join(self.output_dir, f"{name}.comp")
        spv_path = os.path.join(self.output_dir, f"{name}.spv")

        with open(glsl_path, 'w') as f:
            f.write(glsl_source)

        result = subprocess.run(
            ["glslangValidator", "-V", "-o", spv_path, glsl_path],
            capture_output=True, text=True
        )

        return {
            "name": name,
            "glsl_path": glsl_path,
            "spv_path": spv_path,
            "compile_ok": result.returncode == 0,
            "stderr": result.stderr[:500] if result.returncode != 0 else "",
            "stdout": result.stdout[:500] if result.stdout else "",
        }

    def analyze_spv(self, spv_path: str) -> Dict[str, Any]:
        """Analyze SPIR-V structure using M58 pipeline."""
        try:
            pipeline = M58Pipeline(spv_path)
            if not pipeline.verify_integrity():
                return {"status": "BLOCKED", "reason": "integrity_failed"}
            if not pipeline.disassemble():
                return {"status": "BLOCKED", "reason": "disassembly_failed"}
            struct = pipeline.extract_structural()
            semantic = pipeline.build_semantic()
            return {
                "status": "OK",
                "struct": struct,
                "semantic": semantic,
                "hash": pipeline.hash,
            }
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)}

    def disassemble_spv(self, spv_path: str) -> str:
        """Get SPIR-V disassembly text."""
        result = subprocess.run(["spirv-dis", spv_path], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        return f"ERROR: {result.stderr}"

    def count_control_flow(self, disasm: str) -> Dict[str, int]:
        """Count control flow constructs in SPIR-V disassembly."""
        counts = {
            "branches": disasm.count("OpBranch"),
            "conditional_branches": disasm.count("OpBranchConditional"),
            "loops": disasm.count("OpLoopMerge"),
            "selections": disasm.count("OpSelectionMerge"),
            "labels": len(__import__("re").findall(r"%\d+ = OpLabel", disasm)),
            "function_calls": disasm.count("OpFunctionCall"),
            "barriers": disasm.count("OpControlBarrier") + disasm.count("OpMemoryBarrier"),
            "phi_nodes": disasm.count("OpPhi"),
            "switches": disasm.count("OpSwitch"),
        }
        return counts

    def generate_c_reference(self, name: str, glsl_source: str) -> str:
        """Generate a C reference implementation from GLSL source.

        This is a simplified translation for differential validation.
        In production, this would use the M58 C generation pipeline.
        """
        # For now, generate a placeholder that documents the shader
        return f"""/* C reference for {name} shader */
/* GLSL source preserved for reference */
/* Status: RECONSTRUCTED (control flow complexity) */
/* Note: Full C translation requires SPIR-V → C pipeline (M58) */
"""

    def analyze_all(self) -> Dict[str, Any]:
        """Compile and analyze all control flow shader templates."""
        results = {}
        for name, glsl in SHADER_TEMPLATES.items():
            compile_result = self.compile_shader(name, glsl)
            if compile_result["compile_ok"]:
                spv_analysis = self.analyze_spv(compile_result["spv_path"])
                disasm = self.disassemble_spv(compile_result["spv_path"])
                cf_counts = self.count_control_flow(disasm)
                results[name] = {
                    "compile_ok": True,
                    "spv_path": compile_result["spv_path"],
                    "spv_hash": spv_analysis.get("hash", "N/A") if spv_analysis.get("status") == "OK" else "N/A",
                    "spv_status": spv_analysis.get("status", "N/A"),
                    "control_flow": cf_counts,
                    "labels": spv_analysis.get("struct", {}).get("labels", 0) if spv_analysis.get("status") == "OK" else 0,
                    "stores": spv_analysis.get("struct", {}).get("stores", 0) if spv_analysis.get("status") == "OK" else 0,
                    "loads": spv_analysis.get("struct", {}).get("loads", 0) if spv_analysis.get("status") == "OK" else 0,
                }
            else:
                results[name] = {
                    "compile_ok": False,
                    "error": compile_result["stderr"][:300],
                }
            self.results.append({"name": name, **results[name]})

        return {
            "shaders": results,
            "total": len(SHADER_TEMPLATES),
            "compiled": sum(1 for r in results.values() if r.get("compile_ok")),
            "failed": sum(1 for r in results.values() if not r.get("compile_ok")),
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of control flow analysis."""
        total_cf = {}
        for r in self.results:
            if r.get("compile_ok"):
                cf = r.get("control_flow", {})
                for k, v in cf.items():
                    total_cf[k] = total_cf.get(k, 0) + v
        return {
            "shaders_analyzed": len(self.results),
            "total_control_flow_constructs": total_cf,
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GPU Control Flow Complexity Analyzer")
    parser.add_argument("--output", default="/tmp/rxre_gpu_cf", help="Output directory")
    parser.add_argument("--shader", default=None, help="Specific shader to analyze")
    args = parser.parse_args()

    analyzer = GPUControlFlowAnalyzer(output_dir=args.output)
    result = analyzer.analyze_all()

    print(json.dumps(result, indent=2, default=str))

    summary = analyzer.get_summary()
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
