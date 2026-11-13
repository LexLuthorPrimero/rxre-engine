#!/usr/bin/env python3
"""POLARIS-040: Universal GPU Program Reverse Engineering.

Generalizes RXRE from single-kernel reconstruction to reverse engineering of
*unprepared* GPU programs: Vulkan applications with SPIR-V modules, GLSL sources,
and ELF binaries that load shaders at runtime.

Reutiliza (no duplica): POLARIS-036 UnknownKernelReconstructor, POLARIS-037
CoverageIntelligence/classify_mnemonic, POLARIS-038 KnowledgeStore +
ContinuousKnowledgeEngine patterns, POLARIS-039 complex-kernel methodology.

Hard honesty rules:
- spirv-val PASS is a STRUCTURAL fact, not semantic validation.
- ELF strings evidenced asset references, never behavior.
- RADV_DEBUG=asm capture is ISA evidence, never behavioral equivalence.
- Renders are captured with a headless harness; if the GPU graphics pipe is
  unavailable/wedged the engine REPORTS IT and never fabricates equivalence.
- No universal equivalence from finite samples; holdout discipline preserved.

Restricciones: autonomous_loop=False, max_iter=1, op_claim=False,
DB_AUTH_ACTOR_M294 BLOCKED, W5 BLOCKED. GPU not driven without explicit need;
this module performs CPU-side analysis + optional one-shot renders.
"""
from __future__ import annotations
import os, sys, json, hashlib, subprocess, re, time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

ROOT = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rxre.polaris12.continuous_knowledge_evolution import KnowledgeStore
from rxre.polaris12.coverage_aware_evolution import classify_mnemonic
from rxre.polaris12.gpu_availability import require_gpu, GPUSuspended

HARNESS = "/home/lucas/Escritorio/rxre/tools/rxre/harness/bin/vk_headless_render"
SPIRV_MAGIC = b"\x03\x02\x23\x07"
ELF_MAGIC = b"\x7fELF"
GLSL_EXTS = (".vert", ".frag", ".comp", ".glsl", ".tese", ".tesc", ".geom")
HOST_EXTS = (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m")
BUILD_EXTS = (".cmake", ".pri", ".pro", ".build")
BUILD_NAMES = ("CMakeLists.txt", "meson.build", "Makefile", "configure.ac",
               "Cargo.toml", "package.json", "BUILD", "WORKSPACE")
DOC_EXTS = (".md", ".rst", ".txt")
STAGE_NAME = {0: "Vertex", 1: "TessControl", 2: "TessEval", 3: "Geometry",
              4: "Fragment", 5: "GLCompute", 6: "Kernel"}
SAMPLE_OPS = ("OpImageSampleImplicitLod", "OpImageSampleExplicitLod",
              "OpImageSampleProjImplicitLod", "OpImageSampleProjExplicitLod",
              "OpImageFetch", "OpImageRead", "OpImageTexelPointer")


def sha256_file(path: str, length: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def md5_file(path: str) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def _run(cmd: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, text=True, errors="replace")


# ---------------------------------------------------------------- SPIR-V analysis

class SPIRVModule:
    """Static analysis of a SPIR-V module (never executes it)."""

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.sha256 = sha256_file(path, 16)
        with open(path, "rb") as f:
            self.raw = f.read()
        self.is_spirv = self.raw[:4] == SPIRV_MAGIC
        self.version = int.from_bytes(self.raw[4:8], "little") if self.is_spirv else None
        val = _run(["spirv-val", path], timeout=30) if self.is_spirv else None
        self.valid = bool(val and val.returncode == 0)
        self.val_stderr = (val.stderr or "").strip() if val else "not a SPIR-V"
        self._dis = _run(["spirv-dis", path], timeout=30).stdout if self.is_spirv else ""
        self.entry_points = self._parse_entry_points()
        self.capabilities = re.findall(r"OpCapability (\w+)", self._dis)
        self.opcodes = self._histogram()
        self.decorations = self._parse_decorations()
        self.sample_ops = sum(self._dis.count(op) for op in SAMPLE_OPS)
        self.branch_conditional = len(re.findall(r"OpBranchConditional", self._dis))
        self.loop_merge = len(re.findall(r"OpLoopMerge", self._dis))
        self.selection_merge = len(re.findall(r"OpSelectionMerge", self._dis))
        self.instruction_count = len(re.findall(r"^\s+(?:%\w+\s*=\s*)?Op\w+", self._dis, re.M))
        self.function_names = re.findall(r'OpName %\w+ "([^"]+)"', self._dis)[:24]

    def _parse_entry_points(self) -> List[Dict[str, str]]:
        out = []
        for m in re.finditer(r'OpEntryPoint\s+(\w+)\s+%\w+\s+"([^"]*)"', self._dis):
            stage, name = m.group(1), m.group(2)
            out.append({"stage": stage, "name": name})
        return out

    def _histogram(self) -> Dict[str, int]:
        h = {}
        # spirv-dis emits SSA instruction lines like "\t%45 = OpISub ..." —
        # the opcode is NOT at line start; allow an optional "%%id = " prefix.
        for m in re.finditer(r"^\s+(?:%\w+\s*=\s*)?(Op\w+)", self._dis, re.M):
            h[m.group(1)] = h.get(m.group(1), 0) + 1
        return dict(sorted(h.items(), key=lambda kv: -kv[1]))

    def _parse_decorations(self) -> Dict[str, Any]:
        loc = re.findall(r"OpDecorate %\w+ Location (\d+)", self._dis)
        bind = re.findall(r"OpDecorate %\w+ Binding (\d+)", self._dis)
        dset = re.findall(r"OpDecorate %\w+ DescriptorSet (\d+)", self._dis)
        return {"locations": sorted(set(int(x) for x in loc)),
                "bindings": sorted(set(int(x) for x in bind)),
                "descriptor_sets": sorted(set(int(x) for x in dset))}

    def stages(self) -> List[str]:
        return [e["stage"] for e in self.entry_points]

    def report(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "is_spirv": self.is_spirv,
            "version": self.version,
            "valid_spirv_val": self.valid,
            "instruction_count": self.instruction_count,
            "entry_points": self.entry_points,
            "capabilities": sorted(set(self.capabilities)),
            "decorations": self.decorations,
            "sample_ops": self.sample_ops,
            "branch_conditional": self.branch_conditional,
            "loop_merge": self.loop_merge,
            "selection_merge": self.selection_merge,
            "function_names": self.function_names,
            "top_opcodes": dict(list(self.opcodes.items())[:12]),
        }


def spirv_modules_in(root: str) -> List[str]:
    out = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "rb") as f:
                    if f.read(4) == SPIRV_MAGIC:
                        out.append(p)
            except OSError:
                pass
    return sorted(out)


# ---------------------------------------------------------------- discovery

def _elf_strings(path: str, min_len: int = 5) -> List[str]:
    try:
        r = subprocess.run(["strings", "-n", str(min_len), path],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=60)
        return r.stdout.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []


def discover_program(roots) -> Dict[str, Any]:
    """Recursive, evidence-producing discovery over MULTIPLE roots.
    Each root may be a directory or an individual file. Never assumes semantics."""
    if isinstance(roots, str):
        roots = [roots]
    files = []
    apis = []
    root = roots[0]
    for root_i in roots:
        if os.path.isfile(root_i):
            walk_items = [(os.path.dirname(root_i), [], [os.path.basename(root_i)])]
            base = None  # relpath from file's own dir -> basename
        else:
            walk_items = os.walk(root_i)
            base = root_i
        for dirpath, dirnames, filenames in walk_items:
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                rel = p  # absolute path
                try:
                    with open(p, "rb") as f:
                        head = f.read(16)
                except OSError:
                    continue
                cat = "other"
                if head[:4] == SPIRV_MAGIC:
                    cat = "spirv_module"
                elif head[:4] == ELF_MAGIC:
                    cat = "elf_binary"
                elif fn.lower().endswith(GLSL_EXTS):
                    cat = "glsl_source"
                elif fn.lower().endswith(HOST_EXTS):
                    cat = "host_source"
                elif fn in BUILD_NAMES or fn.lower().endswith(BUILD_EXTS):
                    cat = "build_file"
                elif fn.lower().endswith(DOC_EXTS):
                    cat = "doc"
                files.append({"relpath": rel,
                              "category": cat,
                              "size": os.path.getsize(p),
                              "sha256": sha256_file(p, 16)})
    # API identification from host sources and ELF strings
    api_evidence = []
    for f in files:
        if f["category"] in ("host_source", "build_file", "doc"):
            try:
                with open(f["relpath"], "r", errors="ignore") as fh:
                    txt = fh.read()
            except OSError:
                continue
            for pat, name in [(r"vulkan(/|\.h)|vkCreateInstance", "Vulkan"),
                              (r"#include\s*<GL/", "OpenGL"),
                              (r"metal_cpp|MTLDevice|MTLRenderPassDescriptor", "Metal"),
                              (r"d3d11|D3D11CreateDevice", "Direct3D")]:
                if re.search(pat, txt):
                    api_evidence.append({"api": name, "via": f["relpath"]})
        elif f["category"] == "elf_binary":
            strs = _elf_strings(f["relpath"])
            for name, marker in [("Vulkan", "vkCreateInstance"), ("Vulkan", "vkCreateShaderModule"),
                                 ("Vulkan", "libvulkan")]:
                if any(marker in s for s in strs):
                    api_evidence.append({"api": name, "via": f["relpath"]})
                    break
    for e in api_evidence:
        if e["api"] not in apis:
            apis.append(e["api"])
    counts = {}
    for f in files:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    return {"root": root, "files": files, "counts": counts,
            "apis": sorted(set(apis)), "api_evidence": api_evidence}


def _find_asset_path(ref: str, root: str) -> Optional[str]:
    """Resolve a referenced asset (e.g. 'shaders/cube/cube_vert.spv') against
    candidate roots: root itself and one level of parents."""
    cands = [os.path.join(root, ref)]
    base = os.path.basename(root.rstrip("/"))
    if base in ("assets", "share"):
        cands.append(os.path.join(root, ref))
    # common layouts: <pkg>/assets/shaders/... and <pkg>/shaders/...
    cands.append(os.path.join(root, os.path.basename(ref)))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def build_dependency_graph(disc: Dict[str, Any]) -> Dict[str, Any]:
    """Evidence-based edges. Confidence is always reported."""
    spirv = {f["relpath"]: f for f in disc["files"] if f["category"] == "spirv_module"}
    edges = []
    used = set()

    # R1: quoted references in host source files
    for f in disc["files"]:
        if f["category"] not in ("host_source", "build_file"):
            continue
        try:
            with open(f["relpath"], "r", errors="ignore") as fh:
                txt = fh.read()
        except OSError:
            continue
        for m in re.finditer(r'"([^"]+\.(?:spv|vert|frag|comp))"', txt):
            ref = m.group(1)
            base = os.path.basename(ref)
            hits = [r for r in spirv if os.path.basename(r) == base]
            for h in hits:
                edges.append({"src": f["relpath"], "dst": h, "kind": "source_reference",
                              "confidence": "high"})
                used.add(h)

    # R2: ELF binaries referencing shader assets by relative path or basename
    roots = disc.get("roots", [disc.get("root")])
    asset_roots = [r for r in roots if os.path.isdir(r)] + [os.path.dirname(r) for r in roots]
    for f in disc["files"]:
        if f["category"] != "elf_binary":
            continue
        strs = _elf_strings(f["relpath"])
        strset = set(strs)
        for s in strset:
            if len(s) < 3 or len(s) > 200:
                continue
            for base_root in asset_roots:
                cand = os.path.normpath(os.path.join(base_root, s))
                if cand in spirv:
                    edges.append({"src": f["relpath"], "dst": cand,
                                  "kind": "elf_path_reference", "confidence": "high"})
                    used.add(cand)
        # basename match fallback
        for r in spirv:
            base = os.path.basename(r)
            if any(s == base or s.endswith("/" + base) for s in strset):
                if not any(e["dst"] == r and e["src"] == f["relpath"] for e in edges):
                    edges.append({"src": f["relpath"], "dst": r,
                                  "kind": "elf_string_reference", "confidence": "medium"})
                    used.add(r)
        # textures referenced by the binary
        for s in strset:
            if s.endswith((".png", ".jpg", ".tga")) and ("texture" in s or "res/" in s or "assets" in s):
                edges.append({"src": f["relpath"], "dst": s, "kind": "elf_asset_reference",
                              "confidence": "medium"})

    # Stage detection via minimal SPIR-V disassembly (no execution)
    stage_of: Dict[str, List[str]] = {}
    for r in spirv:
        try:
            dis = subprocess.run(["spirv-dis", r], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, timeout=30).stdout.decode("utf-8", "replace")
            stgs = re.findall(r"OpEntryPoint\s+(\w+)", dis)
            stage_of[r] = [STAGE_NAME.get({"Vertex": 0, "Fragment": 4, "GLCompute": 5,
                                           "Kernel": 6, "Geometry": 3, "TessControl": 1,
                                           "TessEval": 2}.get(s, -1), s) for s in stgs]
        except Exception:
            stage_of[r] = []

    elf_used = {e["dst"] for e in edges if e["kind"] in ("elf_path_reference", "elf_string_reference")}

    # R3: directory pairing by SPIR-V stage (Vertex + Fragment in same dir)
    by_dir: Dict[str, List[str]] = {}
    for r in spirv:
        by_dir.setdefault(os.path.dirname(r), []).append(r)
    pairs = []
    for d, members in by_dir.items():
        vs = [m for m in members if "Vertex" in stage_of.get(m, [])]
        fs = [m for m in members if "Fragment" in stage_of.get(m, [])]
        for v in vs:
            for fmod in fs:
                conf = "high" if (v in elf_used and fmod in elf_used) else "low"
                kind = "dir_pair" if conf == "low" else "elf_confirmed_pair"
                pairs.append({"vertex": v, "fragment": fmod,
                              "kind": kind, "confidence": conf})

    # R4: factory co-reference — referenced Vertex-stage x Fragment-stage,
    # over-approximation by design; over-match risk documented per pair.
    def stage_is(ref, want):
        return want in stage_of.get(ref, [])

    src_refs = [e for e in edges if e["kind"] == "source_reference"]
    vert_refs = sorted({e["dst"] for e in src_refs if stage_is(e["dst"], "Vertex")})
    frag_refs = sorted({e["dst"] for e in src_refs if stage_is(e["dst"], "Fragment")})
    # R4b: same-file co-reference upgrades to high (strongest source evidence)
    same_file_pairs = {}
    files_by_ref: Dict[str, List[str]] = {}
    for e in src_refs:
        files_by_ref.setdefault(e["dst"], []).append(e["src"])
    if vert_refs and frag_refs:
        for v in vert_refs:
            for fmod in frag_refs:
                srcs = set(files_by_ref.get(v, [])) & set(files_by_ref.get(fmod, []))
                same_file = bool(srcs)
                conf = "high" if same_file else "medium"
                kind = "source_coreference" if same_file else "factory_coreference"
                pairs.append({"vertex": v, "fragment": fmod,
                              "kind": kind, "confidence": conf,
                              "same_file": sorted(srcs)})

    # unreferenced extraction findings
    # Dedup pairs by (vertex, fragment); keep highest confidence
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    best: Dict[tuple, Dict[str, Any]] = {}
    for p in pairs:
        key = (p["vertex"], p["fragment"])
        cur = best.get(key)
        if cur is None or conf_rank[p["confidence"]] > conf_rank[cur["confidence"]]:
            best[key] = p
    pairs = sorted(best.values(), key=lambda p: (p["vertex"], p["fragment"]))

    unreferenced = sorted(set(spirv) - used)

    return {"nodes": len(spirv) + len([f for f in disc["files"] if f["category"] == "elf_binary"]),
            "edges": edges, "pipeline_pairs": pairs,
            "unreferenced_spirv": unreferenced,
            "spirv_modules": sorted(spirv)}


# ---------------------------------------------------------------- ISA capture & coverage

def recognize_patterns(mod: "SPIRVModule") -> List[str]:
    """Content-derived reusable pattern ids (never from program name)."""
    pats = []
    if "Vertex" in mod.stages():
        if any("VertexIndex" in l or "gl_VertexIndex" in l for l in mod._dis.splitlines()):
            pats.append("fullscreen_vertex_builtin")
        if mod.instruction_count <= 20:
            pats.append("trivial_vertex")
    if "Fragment" in mod.stages():
        if mod.sample_ops >= 1:
            pats.append("textured_fragment")
        if mod.sample_ops == 0 and mod.instruction_count <= 30:
            pats.append("simple_fragment")
        if mod.loop_merge >= 1:
            pats.append("looping_fragment")
    if mod.branch_conditional >= 1:
        pats.append("branching_control_flow")
    return sorted(set(pats))


def capture_isa(vert: str, frag: str, extra: Optional[List[str]] = None,
                timeout: int = 90) -> Optional[str]:
    """Compile-time GFX8 ISA dump via RADV_DEBUG=asm (CPU side; works even with
    a wedged graphics pipe). Returns the combined disassembly or None."""
    if not os.path.isfile(HARNESS):
        return None
    cmd = [HARNESS, vert, frag, "/tmp/_isa_probe.rgba", "--no-run"]
    if extra:
        cmd += extra
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, env={**os.environ, "RADV_DEBUG": "asm"},
                           errors="replace")
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        return out if "disasm:" in out else None
    except Exception:
        return None


def classify_isa_mnemonics(isa_text: str) -> Dict[str, Any]:
    mnems = sorted(set(re.findall(r"\b(v_[a-z_0-9]+|s_[a-z_0-9]+)", isa_text)))
    bucket = {"VALIDATED": [], "MODELED": [], "NOT_DETERMINED": []}
    for m in mnems:
        try:
            c = classify_mnemonic(m)
        except Exception:
            c = "NOT_DETERMINED"
        bucket.setdefault(c if c in bucket else "NOT_DETERMINED", []).append(m)
    return {"mnemonics": mnems,
            "validated": sorted(bucket["VALIDATED"]),
            "modeled": sorted(bucket["MODELED"]),
            "not_determined": sorted(bucket["NOT_DETERMINED"]),
            "counts": {k: len(v) for k, v in bucket.items()}}


def render_once(vert: str, frag: str, dump: str, tex: bool = False,
                draw: int = 3, timeout: int = 60) -> Dict[str, Any]:
    """One-shot headless render attempt. NEVER fabricates success."""
    require_gpu(f"render_once:{os.path.basename(frag)}")
    if not os.path.isfile(HARNESS):
        return {"ok": False, "reason": "harness missing"}
    cmd = [HARNESS, vert, frag, dump, "--draw", str(draw)]
    if tex:
        cmd.append("--tex")
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, errors="replace")
        err = (r.stderr or "")
        ok = "RENDER_OK" in err
        md5 = md5_file(dump) if ok and os.path.isfile(dump) else None
        gpu_hang = "GPU hang" in err or "FENCE_TIMEOUT" in err or "READOUT_TIMEOUT" in err
        return {"ok": ok, "md5": md5, "timed_out": gpu_hang,
                "device_wedged_evidence": gpu_hang,
                "stderr_tail": err.strip().splitlines()[-3:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "timed_out": True, "reason": "subprocess timeout"}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


# ---------------------------------------------------------------- orchestrator

class UniversalProgramRE:
    def __init__(self, knowledge_path: str = "/tmp/rxre_knowledge_u040.json"):
        self.knowledge = KnowledgeStore(knowledge_path)
        self.gpu_executions = 0
        self.knowledge_hits = 0
        self.knowledge_misses = 0

    def analyze_module(self, mod_path: str) -> Dict[str, Any]:
        return SPIRVModule(mod_path).report()

    def investigate_program(self, roots, label: str) -> Dict[str, Any]:
        if isinstance(roots, str):
            roots = [roots]
        root = roots[0]
        print(f"\n[PROGRAM INVESTIGATION] {label} (roots={roots})", file=sys.stderr)
        disc = discover_program(roots)
        disc["roots"] = roots
        graph = build_dependency_graph(disc)
        report: Dict[str, Any] = {
            "label": label, "root": root,
            "discovery": {"counts": disc["counts"], "apis": disc["apis"],
                          "api_evidence": disc["api_evidence"]},
            "graph": {"edges": graph["edges"],
                      "pipeline_pairs": graph["pipeline_pairs"],
                      "unreferenced_spirv": graph["unreferenced_spirv"]},
            "modules": [], "reuse": {"hits": 0, "misses": 0},
        }
        # persist discovery
        self.knowledge.store(
            kind="program_discovery",
            key=hashlib.sha256((root + label).encode()).hexdigest()[:16],
            payload={"label": label, "counts": disc["counts"], "apis": disc["apis"]},
            provenance={"root": root, "tool": "universal_program_re.py",
                        "date": datetime.now().isoformat()})
        # per-module analysis with knowledge reuse
        for r in graph["spirv_modules"]:
            mod = SPIRVModule(r)
            rep = mod.report()
            prior = self.knowledge.query(kind="shader_module", key=rep["sha256"],
                                         current_only=True)
            if prior:
                self.knowledge_hits += 1
                rep["analysis_source"] = "FROM_KNOWLEDGE"
            else:
                self.knowledge_misses += 1
                self.knowledge.store(
                    kind="shader_module", key=rep["sha256"],
                    payload=rep,
                    provenance={"program": label, "path": r,
                                "method": "spirv-val + spirv-dis static analysis",
                                "gpu_executed": False})
                rep["analysis_source"] = "ANALYZED_NOW"
            report["modules"].append(rep)
            # record content-derived patterns (evidence shared across programs)
            for pat in recognize_patterns(mod):
                prior_pat = self.knowledge.query(kind="instruction_semantics",
                                                 key=f"program_pattern:{pat}",
                                                 current_only=True)
                programs = set()
                for pe in prior_pat:
                    programs.update(pe["payload"].get("programs", []))
                programs.add(label)
                self.knowledge.store(
                    kind="instruction_semantics", key=f"program_pattern:{pat}",
                    payload={"pattern": pat, "programs": sorted(programs),
                             "occurrences": len(programs)},
                    provenance={"derived_from": rep["sha256"], "program": label})
        # persist aggregate pipeline structure
        pair_payload = {"pairs": graph["pipeline_pairs"],
                        "unreferenced": graph["unreferenced_spirv"]}
        self.knowledge.store(
            kind="pipeline_structure",
            key=hashlib.sha256(json.dumps(pair_payload, sort_keys=True).encode()).hexdigest()[:16],
            payload=pair_payload,
            provenance={"program": label, "method": "dir_pair + factory co-reference + ELF strings"})
        report["reuse"] = {"hits": self.knowledge_hits, "misses": self.knowledge_misses}
        return report

    def coverage_report(self, isa_captures: Dict[str, str]) -> Dict[str, Any]:
        out = {}
        for name, isa in isa_captures.items():
            if isa:
                out[name] = classify_isa_mnemonics(isa)
        return out

    def summary(self) -> Dict[str, Any]:
        return {"gpu_executions": self.gpu_executions,
                "knowledge_hits": self.knowledge_hits,
                "knowledge_misses": self.knowledge_misses,
                "store": self.knowledge.rehydrate()}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="POLARIS-040: Universal GPU Program RE")
    ap.add_argument("--root", required=True, action="append")
    ap.add_argument("--label", default="program")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    engine = UniversalProgramRE()
    rep = engine.investigate_program(args.root, args.label)
    if args.json:
        print(json.dumps(rep, indent=2))
        print("knowledge:", json.dumps(engine.summary()), file=sys.stderr)
    else:
        print(f"[{args.label}] modules={len(rep['modules'])} "
              f"apis={rep['discovery']['apis']} unreferenced={rep['graph']['unreferenced_spirv']}")
        print("knowledge:", json.dumps(engine.summary()))


if __name__ == "__main__":
    main()
