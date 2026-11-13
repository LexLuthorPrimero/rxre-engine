#!/usr/bin/env python3
"""POLARIS-041: Autonomous Reverse Engineering Across Unknown Systems.

Investigates GPU programs that RXRE has never seen, WITHOUT building a
parallel engine, integrating POLARIS-036..040 capability:
  - discovery / static analysis: universal_program_re machinery
    (SPIRVModule, discover_program, build_dependency_graph,
     recognize_patterns, KnowledgeStore)
  - knowledge reuse: AGUA (KnowledgeStore) — persist + rehydrate + cross-target
  - honesty: anything not verifiable stays NOT_DETERMINED / ABSTAINED

Two genuinely unprepared systems of opposite nature:
  A. Mesa demos (real-world GLSL ≤120, OpenGL compatibility profile) at
     /usr/share/mesa-demos — assets only, no installed demo binary; cannot be
     lowered to SPIR-V by glslang (Vulkan: builtins removed; OpenGL SPIR-V:
     requires GLSL ≥330 + layout(location=)). Evidence recorded statically.
  B. SPIRV-Tools graphicsfuzz corpora (arbitrary compiled SPIR-V, 88 Fragment,
     87/88 valid) — unknown provenance by construction.

NO GPU dispatches are performed by this mission: static analysis is sufficient
for the findings; semantic claims without GPU evidence stay NOT_DETERMINED.
Physical execution, if ever needed, goes through require_gpu() like everywhere.
"""
from __future__ import annotations
import os, sys, json, glob, hashlib, subprocess, re
from typing import Dict, Any, List
from datetime import datetime

ROOT = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rxre.polaris12.continuous_knowledge_evolution import KnowledgeStore
from rxre.polaris12 import universal_program_re as upr
from rxre.polaris12.gpu_availability import require_gpu

MESA_DEMOS = "/usr/share/mesa-demos"
GRAPHICSFUZZ = "/home/lucas/Escritorio/rxre/KytyPS5-Source/3rdparty/SPIRV-Tools/test/fuzzers/corpora/spv"
KB = "/tmp/rxre_knowledge_p041.json"


def sha256_hex(path: str, n: int = 16) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:n]


def glsl_features(text: str) -> Dict[str, Any]:
    """Evidence-based feature presence metrics (not a semantic model).
    Comments (// ...) are stripped before scanning: they are not code."""
    code = "\n".join(line.split("//", 1)[0] for line in text.splitlines())
    feats = {
        "has_texture_calls": len(re.findall(r"texture2D|textureCube|texture\s*\(", code)),
        "has_sampler2D": len(re.findall(r"sampler2D|samplerCube", code)),
        "uniforms": len(re.findall(r"^\s*uniform\s", code, re.M)),
        "varyings": len(re.findall(r"^\s*varying\s", code, re.M)),
        "if_branches": len(re.findall(r"\bif\s*\(", code)),
        "for_loops": len(re.findall(r"\bfor\s*\(", code)),
        "while_loops": len(re.findall(r"\bwhile\s*\(", code)),
        "const_iterations": re.findall(r"for\s*\([^)]*?=\s*0[^)]*?<\s*(\d+(?:\.0)?)f?", code),
        "compat_profile_markers": sorted(set(
            m for m in ("gl_Vertex", "ftransform", "gl_ModelViewProjectionMatrix",
                        "gl_ModelViewMatrix", "gl_NormalMatrix", "gl_TexCoord",
                        "gl_MultiTexCoord0", "gl_Color", "gl_FrontColor",
                        "gl_FragColor", "gl_Normal", "gl_Position")
            if m in code)),
    }
    # Numeric loop bounds found literally
    feats["loop_literal_bounds"] = [int(x.split('.')[0]) for x in feats["const_iterations"]]
    return feats


def profile_verdict(features: Dict[str, Any]) -> Dict[str, Any]:
    """Vulkan cannot host compatibility-profile GLSL without rewrite."""
    markers = features["compat_profile_markers"]
    compat = bool(markers)
    return {
        "profile": "opengl_compatibility" if compat else "modern_glsl_like",
        "vulkan_spirv_viable": False if compat else "unknown",
        "reason": ("uses compat-profile builtins not lowerable to SPIR-V for Vulkan: "
                   + ", ".join(markers)) if compat else "no compat markers detected; still needs evidence before claiming Vulkan viability",
    }


def glslang_probe(path: str) -> Dict[str, Any]:
    """Record authentic compiler verdicts (evidence, not opinion)."""
    results = {}
    for ext in (".vert", ".frag", ".comp", ".geom", ".tese", ".tesc", ".mesh"):
        if not path.endswith(ext):
            continue
        for args in (["-V"], ["--target-env", "opengl", "-G"]):
            r = subprocess.run(["glslangValidator"] + args + [path],
                               capture_output=True, text=True, errors="replace", timeout=60)
            results[" ".join(args)] = {
                "returncode": r.returncode,
                "spv_generated": r.returncode == 0,
                "stderr_head": (r.stderr or "")[:400],
            }
    return results


def parse_shtest(path: str) -> Dict[str, Any]:
    """The .shtest files ARE the pipeline descriptors (vs/fs + uniforms)."""
    out = {"vs": None, "fs": None, "uniforms": []}
    try:
        with open(path, errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                m = re.match(r"^vs\s+(\S+)", line)
                if m:
                    out["vs"] = m.group(1)
                    continue
                m = re.match(r"^fs\s+(\S+)", line)
                if m:
                    out["fs"] = m.group(1)
                    continue
                m = re.match(r"^uniform\s+(\S+)\s+(\S+)\s+(.*)$", line)
                if m:
                    out["uniforms"].append({"name": m.group(1), "type": m.group(2),
                                            "values": m.group(3).strip()})
    except OSError:
        pass
    return out


def discover_mesa_root(root: str = MESA_DEMOS) -> Dict[str, Any]:
    files = []
    glsl, shtest, assets = [], [], []
    for dirpath, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            try:
                size = os.path.getsize(p)
                sha = sha256_hex(p)
            except OSError:
                continue
            rec = {"relpath": os.path.relpath(p, root), "size": size, "sha256": sha}
            files.append(rec)
            if ext in (".vert", ".frag", ".geom", ".comp"):
                glsl.append(rec)
            elif fn.endswith(".shtest"):
                shtest.append(rec)
            else:
                assets.append(rec)
    return {"root": root, "glsl_sources": glsl, "shtest": shtest, "assets": assets,
            "counts": {"glsl": len(glsl), "shtest": len(shtest), "assets": len(assets),
                       "total": len(files)}}


class UnknownSystemsInvestigator:
    def __init__(self, knowledge_path: str = KB):
        self.knowledge = KnowledgeStore(knowledge_path)
        self.gpu_executions = 0
        self.knowledge_hits = 0
        self.knowledge_misses = 0

    # ---------- Target A: Mesa demos (real-world, compat profile) ----------

    def investigate_mesa_demos(self, root: str = MESA_DEMOS, label: str = "mesa-demos") -> Dict[str, Any]:
        print(f"\n[UNKNOWN SYSTEM A] {label} ({root})", file=sys.stderr)
        disc = discover_mesa_root(root)
        report = {"label": label, "root": root, "discovery": disc,
                  "shaders": [], "pairs": [], "verdicts": [],
                  "reuse": {"hits": 0, "misses": 0}}
        for rec in disc["glsl_sources"]:
            p = os.path.join(root, rec["relpath"])
            prior = self.knowledge.query(kind="program_discovery",
                                         key=f"mesa:{rec['sha256']}", current_only=True)
            if prior:
                self.knowledge_hits += 1
                analysis = prior[-1]["payload"]
                analysis["analysis_source"] = "FROM_KNOWLEDGE"
            else:
                self.knowledge_misses += 1
                text = open(p, errors="ignore").read()
                feats = glsl_features(text)
                verdict = profile_verdict(feats)
                compiler = glslang_probe(p)
                analysis = {
                    "path": rec["relpath"], "sha256": rec["sha256"],
                    "features": feats,
                    "profile_verdict": verdict,
                    "compiler_evidence": compiler,
                    "gpu_executable_via_vulkan": "NOT_DETERMINED",
                }
                self.knowledge.store(
                    kind="program_discovery", key=f"mesa:{rec['sha256']}",
                    payload=analysis,
                    provenance={"program": label, "method": "static GLSL analysis + glslangValidator probe",
                                "gpu_executed": False})
                analysis["analysis_source"] = "ANALYZED_NOW"
            report["shaders"].append(analysis)
        # Pipeline pairing from .shtest evidence
        for st in disc["shtest"]:
            p = os.path.join(root, st["relpath"])
            parsed = parse_shtest(p)
            if parsed["vs"] and parsed["fs"]:
                pair = {"shtest": st["relpath"], "vs": parsed["vs"], "fs": parsed["fs"],
                        "uniforms": parsed["uniforms"], "confidence": "high",
                        "evidence": "shtest_pipeline_descriptor"}
                report["pairs"].append(pair)
                # Persist each pair once per unique content
                pair_key = hashlib.sha256(json.dumps(pair, sort_keys=True).encode()).hexdigest()[:16]
                prior = self.knowledge.query(kind="pipeline_structure",
                                             key=f"mesa_pair:{pair_key}", current_only=True)
                if not prior:
                    self.knowledge.store(
                        kind="pipeline_structure", key=f"mesa_pair:{pair_key}",
                        payload=pair,
                        provenance={"program": label, "method": "shtest parse",
                                    "gpu_executed": False})
        report["discovery"]["counts"]["pipeline_pairs"] = len(report["pairs"])
        report["reuse"] = {"hits": self.knowledge_hits, "misses": self.knowledge_misses}
        return report

    # ---------- Target B: graphicsfuzz corpora (arbitrary SPIR-V) ----------

    def investigate_graphicsfuzz(self, corpora: str = GRAPHICSFUZZ,
                                  sample_n: int = 16, seed: str = "p041",
                                  label: str = "graphicsfuzz") -> Dict[str, Any]:
        print(f"\n[UNKNOWN SYSTEM B] {label} ({corpora})", file=sys.stderr)
        spv = sorted(glob.glob(os.path.join(corpora, "*.spv")))
        # Deterministic sample: sha256 order (never manual cherry-picking)
        keyed = sorted(spv, key=lambda p: hashlib.sha256((seed + p).encode()).hexdigest())
        sample = keyed[:sample_n]
        report = {"label": label, "corpora": corpora, "total_spv": len(spv),
                  "sample_n": len(sample), "modules": [], "stage_distribution": {},
                  "validation": {"valid": 0, "invalid": 0},
                  "coverage_buckets": {},
                  "invalid_files": [], "gpu_executions": 0,
                  "note": "static analysis only — zero GPU dispatches by design (fuzzed shaders may hit undefined paths; require_gpu never invoked)"}
        for p in sample:
            mod = upr.SPIRVModule(p)
            rep = {"name": mod.name, "sha256": mod.sha256,
                   "valid": mod.valid, "instruction_count": mod.instruction_count,
                   "entry_points": mod.entry_points,
                   "capabilities": mod.capabilities,
                   "top_opcodes": dict(list(mod.opcodes.items())[:8]),
                   "sample_ops": mod.sample_ops,
                   "branch_conditional": mod.branch_conditional}
            # Coverage classification of SPIR-V opcode families (honest static buckets)
            opcode_families = {
                "texture": ("OpImage",),
                "control_flow": ("OpBranch", "OpSelectionMerge", "OpLoopMerge", "OpSwitch", "OpReturn"),
                "composite": ("OpComposite", "OpVectorShuffle", "OpVectorExtract", "OpVectorInsert"),
                "integer_arith": ("OpIAdd", "OpISub", "OpIMul", "OpSNegate", "OpUAdd", "OpUSub", "OpUMul"),
                "float_arith": ("OpFAdd", "OpFSub", "OpFMul", "OpFDiv", "OpFNegate", "OpFFma", "OpFRem"),
                "comparison": ("OpSConvert", "OpFOrdCompare", "OpIOrdCompare", "OpSelect", "OpUClamp", "OpSClamp"),
                "conversion": ("OpConvert", "OpFToU", "OpFToS", "OpUToF", "OpSToF", "OpBitcast"),
                "arithmetic_misc": ("OpBitwiseNot", "OpAnd", "OpOr", "OpXor", "OpNot", "OpShift"),
                "memory_barrier": ("OpControlBarrier", "OpMemoryBarrier", "OpArrayCopy"),
                "infrastructure": ("OpLoad", "OpStore", "OpAccessChain", "OpPhi",
                                   "OpVariable", "OpConstant", "OpFunction", "OpLabel",
                                   "OpFunctionEnd", "OpSelectionMerge", "OpLoopMerge",
                                   "OpDecorate", "OpMemberDecorate", "OpName", "OpMemberName",
                                   "OpEntryPoint", "OpExecutionMode", "OpSource", "OpCapability",
                                   "OpMemoryModel", "OpType", "OpExtInst", "OpExtInstImport"),
            }
            bucket = {k: 0 for k in list(opcode_families) + ["unclassified"]}
            for mn in mod.opcodes:
                hit = None
                for fam, prefixes in opcode_families.items():
                    if any(mn.startswith(p) for p in prefixes):
                        hit = fam
                        break
                bucket[hit or "unclassified"] += 1
            rep["opcode_families"] = bucket
            report["modules"].append(rep)
            for stg in mod.stages():
                report["stage_distribution"][stg] = report["stage_distribution"].get(stg, 0) + 1
            report["validation"]["valid" if mod.valid else "invalid"] += 1
            if not mod.valid:
                report["invalid_files"].append(mod.name)
            for k, v in bucket.items():
                report["coverage_buckets"][k] = report["coverage_buckets"].get(k, 0) + v
            prior = self.knowledge.query(kind="shader_module", key=mod.sha256, current_only=True)
            if prior:
                self.knowledge_hits += 1
                rep["analysis_source"] = "FROM_KNOWLEDGE"
            else:
                self.knowledge_misses += 1
                self.knowledge.store(
                    kind="shader_module", key=mod.sha256, payload=rep,
                    provenance={"program": label, "path": os.path.basename(p),
                                "method": "spirv-val + spirv-dis static analysis",
                                "gpu_executed": False})
                rep["analysis_source"] = "ANALYZED_NOW"
        return report

    # ---------- Cross-target transfer measurement (never asserted, only measured) ----------

    def transfer_report(self) -> Dict[str, Any]:
        entries_mesa = self.knowledge.query(kind="program_discovery", current_only=True)
        entries_gf = self.knowledge.query(kind="shader_module", current_only=True)
        mesa = [e for e in entries_mesa if str(e.get("key", "")).startswith("mesa:")]
        gf = [e for e in entries_gf
              if (e.get("provenance") or {}).get("program") == "graphicsfuzz"]
        return {
            "mesa_program_discovery_entries": len(mesa),
            "graphicsfuzz_shader_module_entries": len(gf),
            "pipeline_structure_entries": len(self.knowledge.query(kind="pipeline_structure", current_only=True)),
            "total_knowledge": self.knowledge.count(),
            "knowledge_hits": self.knowledge_hits,
            "knowledge_misses": self.knowledge_misses,
            "gpu_executions": self.gpu_executions,
        }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="POLARIS-041: Unknown Systems Investigation")
    ap.add_argument("--mesa", action="store_true")
    ap.add_argument("--graphicsfuzz", action="store_true")
    ap.add_argument("--transfer", action="store_true")
    ap.add_argument("--sample", type=int, default=16)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    inv = UnknownSystemsInvestigator()
    out = {}
    if args.mesa:
        out["mesa"] = inv.investigate_mesa_demos()
    if args.graphicsfuzz:
        out["graphicsfuzz"] = inv.investigate_graphicsfuzz(sample_n=args.sample)
    if args.transfer:
        out["transfer"] = inv.transfer_report()
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for k, v in out.items():
            print(f"[{k}] fp={json.dumps({kk: vv for kk, vv in v.items() if kk in ('counts','total_spv','sample_n','validation','stage_distribution','gpu_executions')}, default=str)[:300]}")


if __name__ == "__main__":
    main()
