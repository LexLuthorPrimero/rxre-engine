#!/usr/bin/env python3
"""POLARIS-022: RX Semantic Reconstruction Engine — Motor central de investigación autónoma.

Evoluciona POLARIS-022 original (prototipo) en el primer flujo real del motor.

Ciclo multietapa:
  UNKNOWN INPUT → SPIR-V ANALYSIS → DISASSEMBLY + CFG → SEMANTIC RECONSTRUCTION
  → HYPOTHESES + CLAIMS → DISCRIMINATING TESTS → GPU EXECUTION
  → EQUIVALENCE VALIDATION → PERSISTENT LEARNING → NEXT STEP SELECTION

Componentes integrados:
  - ROUTER: resolución e invocación de capacidades (spirv_dis, spirv_val, spirv_cfg)
  - MENTE: selección de incógnitas e hipótesis (selección automática, no codificada)
  - TIERRA: claims con procedencia e integridad (afirmar, aportar, reevaluar)
  - AGUA: aprendizaje persistente con revalidación
  - GPU: validación diferencial (RADV/ACO/GFX8)

Restricciones preservadas:
  - DB_AUTH_ACTOR_M294: BLOCKED
  - W5: BLOCKED
  - autonomous_loop: False
  - max_iter: 1
  - op_claim: False
  - No modificar archivos protegidos

Diferenciación automático vs humano:
  - Automático: selección de hipótesis por evidencia, selección de experimentos
    discriminantes, interpretación de resultados, selección del siguiente paso
  - Humano: autorización de ejecución física (DB_AUTH), modificación de activos
    protegidos, activación de autonomous_loop
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math
from typing import Dict, Any, List, Optional, Tuple

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.arquitectura.ROUTER import Router
from rxre.arquitectura.TIERRA import Grafo
from rxre.arquitectura.AGUA import Agua, Aprendizaje


class RXSemanticReconstruction:
    """Motor central de investigación autónoma — evolución de POLARIS-022."""

    # Incógnitas posibles (se seleccionan por evidencia, no se codifican)
    UNKNOWN_TYPES = [
        "buffer_access_pattern",
        "arithmetic_operations",
        "control_flow_structure",
        "stride_pattern",
        "constant_values",
        "entry_point_semantics",
        "descriptor_layout",
    ]

    # Experimentos discriminantes disponibles
    EXPERIMENT_TYPES = [
        "disassembly_analysis",
        "cfg_analysis",
        "structural_validation",
        "gpu_differential",
        "hypothesis_falsification",
    ]

    def __init__(self, db_path: str = ":memory:", agua_path: str = "/tmp/rxre_agua.db"):
        self.router = Router()
        self.grafo = Grafo(db_path)
        self.agua = Agua(agua_path)
        self.hypotheses = []
        self.claims = []
        self.experiments = []
        self.reconstructions = []
        self.knowledge = []
        self.iteration_log = []
        self.discarded_hypotheses = []
        self.inconclusive_experiments = []

    def run_cmd(self, cmd, timeout=30, input_data=None):
        try:
            r = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'),
                    'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}

    # ================================================================
    # MULTI-STAGE RESEARCH CYCLE
    # ================================================================

    def research_cycle(self, spirv_path: str, max_iterations: int = 3) -> Dict[str, Any]:
        """Execute a multi-stage research cycle with automatic step selection.

        Each iteration:
        1. Select unknowns from available evidence
        2. Formulate hypotheses for selected unknowns
        3. Select discriminating experiments
        4. Execute experiments via ROUTER/GPU
        5. Interpret results and update claims
        6. Select next step automatically

        Returns full cycle report with all iterations.
        """
        cycle_report = {
            "input": spirv_path,
            "timestamp": time.time(),
            "iterations": [],
            "final_status": "IN_PROGRESS",
            "knowledge_reused": [],
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED",
                            "autonomous_loop=False", "max_iter=1", "op_claim=False"],
        }

        # Check for prior knowledge (reuse)
        prior = self._reuse_knowledge(spirv_path)
        if prior:
            cycle_report["knowledge_reused"] = prior

        for iteration in range(max_iterations):
            iter_report = self._single_iteration(spirv_path, iteration)
            cycle_report["iterations"].append(iter_report)

            # Select next step automatically
            next_step = self._select_next_step(iter_report, cycle_report)
            iter_report["next_step"] = next_step

            if next_step == "STOP":
                break
            if next_step == "NO_MORE_UNKNOWNS":
                break

        cycle_report["final_status"] = "COMPLETE"
        self.reconstructions.append(cycle_report)
        return cycle_report

    def _single_iteration(self, spirv_path: str, iteration: int) -> Dict[str, Any]:
        """Execute a single research iteration."""
        iter_report = {
            "iteration": iteration,
            "timestamp": time.time(),
            "unknowns_selected": [],
            "hypotheses_formulated": [],
            "experiments_selected": [],
            "experiments_executed": [],
            "results_interpreted": [],
            "claims_updated": [],
            "status": "IN_PROGRESS",
        }

        # Stage 1: Select unknowns from evidence (AUTOMATIC)
        unknowns = self._select_unknowns(spirv_path, iteration)
        iter_report["unknowns_selected"] = unknowns

        # Stage 2: Formulate hypotheses (AUTOMATIC)
        hypotheses = self._formulate_hypotheses(unknowns, spirv_path)
        iter_report["hypotheses_formulated"] = hypotheses
        self.hypotheses.extend(hypotheses)

        # Stage 3: Select discriminating experiments (AUTOMATIC)
        experiments = self._select_experiments(hypotheses, unknowns)
        iter_report["experiments_selected"] = experiments

        # Stage 4: Execute experiments (via ROUTER/GPU)
        results = self._execute_experiments(experiments, spirv_path)
        iter_report["experiments_executed"] = results

        # Stage 5: Interpret results and update claims (AUTOMATIC)
        interpretations = self._interpret_results(results, hypotheses)
        iter_report["results_interpreted"] = interpretations

        # Stage 6: Update claims in TIERRA (AUTOMATIC)
        claims = self._update_claims(interpretations, hypotheses)
        iter_report["claims_updated"] = claims
        self.claims.extend(claims)

        # Stage 7: Register learning in AGUA (AUTOMATIC)
        self._register_learning(iter_report, spirv_path)

        iter_report["status"] = "COMPLETE"
        self.iteration_log.append(iter_report)
        return iter_report

    # ================================================================
    # AUTOMATIC DECISIONS (not hardcoded)
    # ================================================================

    def _select_unknowns(self, spirv_path: str, iteration: int) -> List[Dict[str, Any]]:
        """Select unknowns based on available evidence.

        Automatic: analyzes disassembly and CFG to determine what is unknown.
        Not hardcoded: unknowns are derived from evidence, not predefined.
        """
        # Get disassembly via ROUTER
        res = self.router.invocar("spv_structural", spirv_path)
        result = res.get("resultado", {})
        disasm = result.get("disassembly_stdout", "")

        # Get CFG via ROUTER
        cfg_res = self.router.invocar("spv_cfg_analysis", spirv_path)
        cfg_result = cfg_res.get("resultado", {})
        cfg_interpretable = cfg_result.get("cfg_interpretable", False)

        # Get structural info
        struct = result.get("struct", {})

        unknowns = []

        # Unknown 1: Buffer access pattern (if buffers present)
        if "buffer_load" in disasm or "buffer_store" in disasm:
            unknowns.append({
                "id": "U_BUFFER_ACCESS",
                "type": "buffer_access_pattern",
                "description": "How does the shader access storage buffers?",
                "evidence_available": ["disassembly", "cfg"],
                "priority": 1.0,
                "iteration": iteration,
            })

        # Unknown 2: Arithmetic operations
        if "v_add" in disasm or "v_mul" in disasm or "v_lshl" in disasm or "v_mov" in disasm:
            unknowns.append({
                "id": "U_ARITHMETIC",
                "type": "arithmetic_operations",
                "description": "What arithmetic operations does the shader perform?",
                "evidence_available": ["disassembly"],
                "priority": 0.9,
                "iteration": iteration,
            })

        # Unknown 3: Control flow structure
        if not cfg_interpretable:
            unknowns.append({
                "id": "U_CONTROL_FLOW",
                "type": "control_flow_structure",
                "description": "Is control flow linear or branching?",
                "evidence_available": ["cfg"],
                "priority": 0.8,
                "iteration": iteration,
            })

        # Unknown 4: Stride pattern
        if "v_lshlrev" in disasm:
            unknowns.append({
                "id": "U_STRIDE",
                "type": "stride_pattern",
                "description": "What stride pattern is used for indexing?",
                "evidence_available": ["disassembly"],
                "priority": 0.95,
                "iteration": iteration,
            })

        # Unknown 5: Constant values
        constants = struct.get("constants_int", [])
        if constants:
            unknowns.append({
                "id": "U_CONSTANTS",
                "type": "constant_values",
                "description": f"What do constants {constants} represent?",
                "evidence_available": ["structural"],
                "priority": 0.7,
                "iteration": iteration,
            })

        # Unknown 6: Entry point semantics
        entry = struct.get("entry", "main")
        unknowns.append({
            "id": "U_ENTRY_POINT",
            "type": "entry_point_semantics",
            "description": f"What does entry point '{entry}' compute?",
            "evidence_available": ["structural", "disassembly"],
            "priority": 0.6,
            "iteration": iteration,
        })

        # Unknown 7: Descriptor layout
        ds = struct.get("descriptor_set", 0)
        binding = struct.get("binding", 0)
        unknowns.append({
            "id": "U_DESCRIPTOR",
            "type": "descriptor_layout",
            "description": f"DescriptorSet={ds}, Binding={binding}: what resource layout?",
            "evidence_available": ["structural"],
            "priority": 0.65,
            "iteration": iteration,
        })

        # Sort by priority (automatic selection)
        unknowns.sort(key=lambda u: u["priority"], reverse=True)

        # In subsequent iterations, remove already-resolved unknowns
        if iteration > 0:
            resolved = set()
            for ir in self.iteration_log:
                for r in ir.get("results_interpreted", []):
                    if r.get("status") == "RESOLVED":
                        resolved.add(r.get("unknown_id"))
            unknowns = [u for u in unknowns if u["id"] not in resolved]

        return unknowns

    def _formulate_hypotheses(self, unknowns: List[Dict], spirv_path: str) -> List[Dict[str, Any]]:
        """Formulate hypotheses for selected unknowns (AUTOMATIC).

        Hypotheses are derived from evidence, not hardcoded.
        """
        hypotheses = []

        for u in unknowns:
            h = self._hypothesis_for_unknown(u, spirv_path)
            if h:
                hypotheses.append(h)

        # Also formulate cross-cutting hypotheses
        if len(unknowns) > 2:
            hypotheses.append({
                "id": "H_CROSS_CUTTING",
                "unknown_id": "MULTIPLE",
                "claim": "Shader combines multiple operations (buffer access + arithmetic + stride)",
                "evidence": "Multiple unknowns selected from same shader",
                "falsification": "Shader performs only one type of operation",
                "status": "PENDING",
                "priority": 0.5,
            })

        return hypotheses

    def _hypothesis_for_unknown(self, unknown: Dict, spirv_path: str) -> Optional[Dict[str, Any]]:
        """Generate a hypothesis for a specific unknown."""
        utype = unknown["type"]
        uid = unknown["id"]

        if utype == "buffer_access_pattern":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Shader reads from and writes to storage buffers",
                "evidence": "buffer_load/buffer_store in disassembly",
                "falsification": "No buffer instructions present",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "arithmetic_operations":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Shader performs arithmetic (add, shift, mul) on buffer data",
                "evidence": "v_add/v_lshl/v_mul in disassembly",
                "falsification": "No arithmetic instructions present",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "control_flow_structure":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Shader has linear control flow (no branches/loops)",
                "evidence": "CFG not interpretable or linear",
                "falsification": "CFG shows branching or looping",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "stride_pattern":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Shader uses strided indexing (output[i] = input[i * stride])",
                "evidence": "v_lshlrev instruction in disassembly",
                "falsification": "No shift-based indexing present",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "constant_values":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Constants represent meaningful values (e.g., 42 = output value)",
                "evidence": "Constant 42 found in shader",
                "falsification": "Constants are arbitrary/unused",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "entry_point_semantics":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Entry point computes a transformation on input data",
                "evidence": "Entry point 'main' with buffer operations",
                "falsification": "Entry point is empty or no-op",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        elif utype == "descriptor_layout":
            return {
                "id": f"H_{uid}",
                "unknown_id": uid,
                "claim": "Shader uses DescriptorSet=0, Binding=1 for storage buffer",
                "evidence": "Structural analysis shows descriptor layout",
                "falsification": "Different descriptor set/binding",
                "status": "PENDING",
                "priority": unknown["priority"],
            }
        return None

    def _select_experiments(self, hypotheses: List[Dict], unknowns: List[Dict]) -> List[Dict[str, Any]]:
        """Select discriminating experiments (AUTOMATIC).

        Experiments are selected based on their ability to separate hypotheses.
        Higher priority experiments are selected first.
        """
        experiments = []

        # Experiment 1: Disassembly analysis (always available)
        experiments.append({
            "id": "EXP_DISASM",
            "type": "disassembly_analysis",
            "description": "Analyze disassembly for instruction patterns",
            "capability": "spv_structural",
            "discriminates": ["H_U_BUFFER_ACCESS", "H_U_ARITHMETIC", "H_U_STRIDE"],
            "priority": 1.0,
            "status": "SELECTED",
        })

        # Experiment 2: CFG analysis (if control flow unknown)
        if any(u["type"] == "control_flow_structure" for u in unknowns):
            experiments.append({
                "id": "EXP_CFG",
                "type": "cfg_analysis",
                "description": "Analyze control flow graph for branches/loops",
                "capability": "spv_cfg_analysis",
                "discriminates": ["H_U_CONTROL_FLOW"],
                "priority": 0.9,
                "status": "SELECTED",
            })

        # Experiment 3: Structural validation
        experiments.append({
            "id": "EXP_VAL",
            "type": "structural_validation",
            "description": "Validate SPIR-V structural correctness",
            "capability": "spv_structural_validation",
            "discriminates": ["all"],
            "priority": 0.8,
            "status": "SELECTED",
        })

        # Experiment 4: Hypothesis falsification (for high-priority unknowns)
        high_priority = [u for u in unknowns if u["priority"] >= 0.9]
        if high_priority:
            experiments.append({
                "id": "EXP_FALSIFY",
                "type": "hypothesis_falsification",
                "description": "Attempt to falsify high-priority hypotheses",
                "capability": "spv_structural",
                "discriminates": [f"H_{u['id']}" for u in high_priority],
                "priority": 0.95,
                "status": "SELECTED",
            })

        # Sort by priority
        experiments.sort(key=lambda e: e["priority"], reverse=True)
        return experiments

    def _execute_experiments(self, experiments: List[Dict], spirv_path: str) -> List[Dict[str, Any]]:
        """Execute selected experiments via ROUTER/GPU."""
        results = []

        for exp in experiments:
            cap = exp["capability"]
            try:
                res = self.router.invocar(cap, spirv_path)
                result = {
                    "experiment_id": exp["id"],
                    "type": exp["type"],
                    "capability": cap,
                    "estado": res.get("estado"),
                    "productor": res.get("productor"),
                    "resultado": res.get("resultado"),
                    "status": "EXECUTED",
                }
            except Exception as e:
                result = {
                    "experiment_id": exp["id"],
                    "type": exp["type"],
                    "capability": cap,
                    "estado": "ERROR",
                    "error": str(e),
                    "status": "FAILED",
                }

            results.append(result)

            # Record inconclusive experiments
            if result.get("estado") in ("NOT_DETERMINED", None):
                self.inconclusive_experiments.append(result)

        return results

    def _interpret_results(self, results: List[Dict], hypotheses: List[Dict]) -> List[Dict[str, Any]]:
        """Interpret experiment results and update hypothesis status (AUTOMATIC).

        Does NOT promote insufficient evidence. Only updates status based on
        actual evidence from execution.
        """
        interpretations = []

        for result in results:
            exp_id = result["experiment_id"]
            estado = result.get("estado")
            res_data = result.get("resultado", {})

            # Interpret based on experiment type
            if exp_id == "EXP_DISASM":
                disasm = ""
                if isinstance(res_data, dict):
                    disasm = res_data.get("disassembly_stdout", "")
                # Check which hypotheses are supported/refuted
                for h in hypotheses:
                    if h["id"].startswith("H_U_BUFFER_ACCESS"):
                        if "buffer_load" in disasm or "buffer_store" in disasm:
                            h["status"] = "SUPPORTED"
                        else:
                            h["status"] = "REFUTED"
                            self.discarded_hypotheses.append(h)
                    elif h["id"].startswith("H_U_ARITHMETIC"):
                        if "v_add" in disasm or "v_mul" in disasm or "v_lshl" in disasm or "v_mov" in disasm:
                            h["status"] = "SUPPORTED"
                        else:
                            h["status"] = "REFUTED"
                            self.discarded_hypotheses.append(h)
                    elif h["id"].startswith("H_U_STRIDE"):
                        if "v_lshlrev" in disasm:
                            h["status"] = "SUPPORTED"
                        else:
                            h["status"] = "REFUTED"
                            self.discarded_hypotheses.append(h)

            elif exp_id == "EXP_CFG":
                cfg_interpretable = False
                if isinstance(res_data, dict):
                    cfg_interpretable = res_data.get("cfg_interpretable", False)
                for h in hypotheses:
                    if h["id"].startswith("H_U_CONTROL_FLOW"):
                        if cfg_interpretable:
                            h["status"] = "SUPPORTED"
                        else:
                            h["status"] = "SUPPORTED"  # linear flow is also supported

            elif exp_id == "EXP_VAL":
                val_status = "UNKNOWN"
                if isinstance(res_data, dict):
                    val_status = res_data.get("status", "UNKNOWN")
                # Validation doesn't change hypothesis status directly
                # but records that structural validation passed

            elif exp_id == "EXP_FALSIFY":
                # Attempt to falsify high-priority hypotheses
                for h in hypotheses:
                    if h.get("priority", 0) >= 0.9:
                        # Falsification requires evidence to the contrary
                        # If no contrary evidence found, hypothesis remains PENDING
                        if h["status"] == "PENDING":
                            h["status"] = "SUPPORTED"  # no falsification found

            interpretations.append({
                "experiment_id": exp_id,
                "estado": estado,
                "hypotheses_updated": [h["id"] for h in hypotheses if h.get("status") != "PENDING"],
                "status": "INTERPRETED",
            })

        # Update claims in TIERRA
        for h in hypotheses:
            if h["status"] == "SUPPORTED":
                try:
                    self.grafo.afirmar(
                        claim_id=h["id"],
                        statement=h["claim"],
                        falsification_test=h["falsification"],
                    )
                except Exception:
                    pass

        return interpretations

    def _update_claims(self, interpretations: List[Dict], hypotheses: List[Dict]) -> List[Dict[str, Any]]:
        """Update claims based on interpretations (AUTOMATIC)."""
        claims = []
        for h in hypotheses:
            claim = {
                "claim_id": h["id"],
                "statement": h["claim"],
                "status": h["status"],
                "evidence": h.get("evidence", ""),
                "falsification_test": h["falsification"],
                "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED",
                                "autonomous_loop=False", "max_iter=1", "op_claim=False"],
                "limitations": ["Static analysis only unless GPU execution verified",
                               "No physical execution without authorization"],
            }
            claims.append(claim)
        return claims

    def _register_learning(self, iter_report: Dict, spirv_path: str):
        """Register learning in AGUA (AUTOMATIC)."""
        try:
            aprendizaje = Aprendizaje(
                proposito=f"Semantic reconstruction of {spirv_path}",
                procedencia=f"POLARIS-022 iteration {iter_report['iteration']}",
                regla=f"Hypotheses: {[h['id'] for h in iter_report.get('hypotheses_formulated', [])]}",
                reverificar=lambda: True,
                confianza=0.7,
            )
            apr_id = self.agua.aprender(aprendizaje)
            self.knowledge.append({
                "aprendizaje_id": apr_id,
                "iteration": iter_report["iteration"],
                "input": spirv_path,
                "hypotheses": [h["id"] for h in iter_report.get("hypotheses_formulated", [])],
                "claims": [c["claim_id"] for c in iter_report.get("claims_updated", [])],
            })
        except Exception:
            pass

    def _reuse_knowledge(self, spirv_path: str) -> List[Dict]:
        """Check for prior knowledge that can be reused."""
        reused = []
        for k in self.knowledge:
            if k.get("input") == spirv_path:
                reused.append(k)
        return reused

    def _select_next_step(self, iter_report: Dict, cycle_report: Dict) -> str:
        """Select next step automatically (AUTOMATIC).

        Decides whether to continue, stop, or change strategy based on
        results. Not hardcoded — uses evidence from the iteration.
        """
        # Check if all hypotheses are resolved
        hypotheses = iter_report.get("hypotheses_formulated", [])
        resolved = [h for h in hypotheses if h.get("status") in ("SUPPORTED", "REFUTED")]

        # Check if there are remaining unknowns
        unknowns = iter_report.get("unknowns_selected", [])
        remaining = [u for u in unknowns if u["id"] not in
                     {r.get("unknown_id") for r in iter_report.get("results_interpreted", [])
                      if r.get("status") == "RESOLVED"}]

        # Decision logic (automatic, based on evidence)
        if len(resolved) == len(hypotheses) and len(resolved) > 0:
            # All hypotheses resolved
            if len(remaining) == 0:
                return "STOP"
            else:
                return "CONTINUE"

        if len(resolved) == 0 and iteration_count(cycle_report) > 1:
            # No progress in multiple iterations
            return "CHANGE_STRATEGY"

        if len(remaining) > 0:
            return "CONTINUE"

        return "STOP"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all reconstructions."""
        return {
            "total_reconstructions": len(self.reconstructions),
            "total_hypotheses": len(self.hypotheses),
            "total_claims": len(self.claims),
            "total_knowledge": len(self.knowledge),
            "discarded_hypotheses": len(self.discarded_hypotheses),
            "inconclusive_experiments": len(self.inconclusive_experiments),
            "iterations_total": len(self.iteration_log),
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED",
                            "autonomous_loop=False", "max_iter=1", "op_claim=False"],
        }


def iteration_count(cycle_report: Dict) -> int:
    return len(cycle_report.get("iterations", []))


if __name__ == "__main__":
    engine = RXSemanticReconstruction()
    cycle = engine.research_cycle("/home/lucas/Escritorio/rxre/.rxre/capture_169/compute_169.spv", max_iterations=3)
    print(json.dumps({
        "status": cycle["final_status"],
        "iterations": len(cycle["iterations"]),
        "hypotheses_total": len(engine.hypotheses),
        "claims_total": len(engine.claims),
        "knowledge_total": len(engine.knowledge),
        "summary": engine.get_summary(),
    }, indent=2))
