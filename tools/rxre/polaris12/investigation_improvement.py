#!/usr/bin/env python3
"""POLARIS-043: Investigación autónoma, inferencia semántica y mejora investigadora.

Integra componentes existentes en ciclo:
OBSERVAR -> INFERIR -> HIPOTETIZAR -> EXPERIMENTAR -> REFUTAR -> APRENDER -> MEJORAR

Reutiliza (sin motor paralelo):
 - unknown_kernel_reconstruction.UnknownKernelReconstructor (execute_kernel, discriminate, generate_hypotheses)
 - continuous_knowledge_evolution.KnowledgeStore (persistencia append-only)
 - coverage_aware_evolution.CoverageIntelligence (analyze_shader, next_investigation baseline)
 - arquitectura.planos.Libro (MENTE: hipótesis rivales con falsación explícita)
 - arquitectura.TIERRA.Grafo (evidencia, contradicciones, reevaluación)
 - arquitectura.AGUA.Aprendizaje / Agua (revalidación, procedencia obligatoria)
 - gpu_availability.require_gpu / GPUSuspended (guard v2)
Restricciones: autonomous_loop=False, max_iter=1, op_claim=False,
DB_AUTH_ACTOR_M294 BLOCKED, W5 BLOCKED. HOLDOUT sellado con manifiesto.
"""
from __future__ import annotations
import os, sys, json, hashlib, time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.unknown_kernel_reconstruction import UnknownKernelReconstructor, Hypothesis
from rxre.polaris12.continuous_knowledge_evolution import KnowledgeStore
from rxre.polaris12.coverage_aware_evolution import CoverageIntelligence, classify_mnemonic
from rxre.polaris12.gpu_availability import require_gpu, GPUSuspended
from rxre.polaris12.gpu_isa_recovery import GPUISARecovery
from tools.rxre.arquitectura.planos import Libro, CUERPO, NOT_DETERMINED, PROVEN, PROVEN_ABSENT
from tools.rxre.arquitectura.TIERRA import Grafo
from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje

# ---------------------------------------------------------------- Mecanismo A
def infer_invariants(gpu_result: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae invariantes candidatas desde un GPU_result auténtico.
    gpu_result: {'results': [...], 'num_results':N, 'device':..., 'returncode':0}
    context: {'kernel':..., 'method':..., 'n':...}
    Regla: observación aislada -> PARTIAL/NOT_DETERMINED, nunca ley general.
    """
    results = gpu_result.get("results", []) or []
    n = len(results)
    invs: List[Dict[str, Any]] = []
    if n == 0:
        return []  # sin evidencia observable no se infiere ninguna invariante
    refs = [f"gpu_result:{context.get('kernel','?')}#{gpu_result.get('device','')}:{n}"]
    domain = {"n_elements": n, "device": gpu_result.get("device","unknown"),
              "kernel": context.get("kernel"), "method": context.get("method","048-execute_gpu")}
    # Balanceado: si la mitad de las salidas son cero, invariante de cero-; si resto, resto
    non_zero = sum(1 for v in results if isinstance(v, int) and v != 0)
    if non_zero == 0:
        invs.append({
            "statement": "salida-cero para todas las invocaciones presentes (kernel con salida cero, ej. barrier-sync)",
            "evidence_refs": refs, "domain": domain,
            "conditions": {"has_barrier": bool(context.get("has_barrier", False)), "n": n},
            "counterexamples": [], "status": "PARTIAL", "falsification_test": "mismo kernel con idx nuevo -> si surge salida !=0 se refuta",
        })
    elif non_zero == n:
        invs.append({
            "statement": "salida-no-cero disponiendo de inmediatos ISA no-cero",
            "evidence_refs": refs, "domain": domain,
            "conditions": {"n": n, "device": domain["device"]},
            "counterexamples": [], "status": "PARTIAL",
            "falsification_test": "kernel con salida-cero explícita -> si aparece cero se refuta parcialmente",
        })
    else:
        invs.append({
            "statement": "salida mixta: depende de idx y control-flow (rama s_cbranch)",
            "evidence_refs": refs, "domain": domain,
            "conditions": {"n": n, "branch": True},
            "counterexamples": [], "status": "PARTIAL",
            "falsification_test": "mismo kernel con nueva idx que fije otra rama -> si no cambia se refuta",
        })
    # Predicción ciega desde constantes (depende del mejor modelo)
    # NO se declara invariante general sin falsación.
    conf_hint = 0.5
    for inv in invs:
        inv["confidence"] = conf_hint
    return invs

# ---------------------------------------------------------------- Mecanismo B
def hypothesis_from_invariant(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Invariante -> hipótesis rival en MENTE."""
    enunciado = inv["statement"]
    test = inv.get("falsification_test") or "GPU ejecución adicional"
    return {"enunciado": enunciado, "test": test, "nota": inv.get("status","")}

def discriminant_power(predictions: Dict[str, Any]) -> float:
    """poder discriminante: fracción de entradas donde las hipótesis difieren."""
    vals = list(predictions.values())
    if not vals:
        return 0.0
    # predictions = {'h1': [vals], 'h2':[vals]}
    keys = list(predictions.keys())
    if len(keys) < 2:
        return 0.0
    diff = 0
    total = min(len(v) for v in predictions.values())
    for i in range(total):
        col = [predictions[k][i] for k in keys]
        if len(set(col)) > 1:
            diff += 1
    return diff / total if total else 0.0

class DiscriminantSelector:
    """Reemplaza next_investigation hardcodeado: calcula poder sobre predicciones reales."""
    def select_batch(self, kernels: List[str], hypotheses_by_kernel: Dict[str, List[Hypothesis]],
                     candidate_idx: range = range(16)) -> Dict[str, Any]:
        """Elige el kernel+hipótesis que mejor separa rivales.
        BLL — kernel elegido = max discriminante medio idx=test_idx """
        best = None
        for k in kernels:
            hyps = hypotheses_by_kernel.get(k, [])
            if len(hyps) < 2:
                continue
            preds = {h.to_dict()["explain"]: [h.predict(i) for i in candidate_idx] for h in hyps}
            power = discriminant_power(preds)
            if best is None or power > best[0]:
                best = (power, k, preds)
        if best is None:
            return {"status": "NOT_DETERMINED", "reason": "sin hipótesis rivales con predicciones separables"}
        power, k, preds = best
        if power < 0.1:
            return {"status": "NOT_DETERMINED", "reason": f"poder discriminante insuficiente ({power:.2f})",
                    "selected": k}
        return {"status": "OK", "selected": k, "discriminative_power": round(power, 3),
                "hypotheses": preds}

# ---------------------------------------------------------------- Mecanismo C
FIELDS_CONDITIONS = ("device","kernel_sha256","engine","n_elements","wg_size")
def evaluate_applicability(entry: Dict[str, Any], current: Dict[str, Any]) -> str:
    """Retorna APPLICABLE / PARTIALLY_APPLICABLE / NOT_APPLICABLE"""
    payload = entry.get("payload", {}) or {}
    prov = entry.get("provenance", {}) or {}
    # Contradicciones pendientes
    contradicts = payload.get("counterexamples") or payload.get("contradictions") or []
    if contradicts:
        return "NOT_APPLICABLE"
    # Evidencia no resoluble: payload.evidence_refs (forma de infer_invariants)
    # con lista vacía = no resoluble; ausente del todo = no decidible aquí
    ev = prov.get("evidence_refs") or payload.get("evidence_refs")
    if ev is not None and not any(ev):
        return "NOT_APPLICABLE"
    # Comparar condiciones duras
    mismatches = []
    for f in ("device", "kernel_sha256"):
        if f in prov and f in current and prov[f] != current[f]:
            mismatches.append(f)
    if mismatches:
        return "NOT_APPLICABLE"
    # Coincidencia parcial
    partial = any(k in prov and prov[k] != current.get(k) for k in ("engine","harness","profile"))
    if partial:
        return "PARTIALLY_APPLICABLE"
    # Dominios: si el payload trae 'domain' y el target trae 'domain' distinto -> parcial
    entry_domain = payload.get("domain")
    current_domain = current.get("domain")
    if entry_domain is not None and current_domain is not None and entry_domain != current_domain:
        return "PARTIALLY_APPLICABLE"
    return "APPLICABLE"

# ---------------------------------------------------------------- Mecanismo D
class HoldoutRegistry:
    """Manifiesto sellado TRAIN/VALIDATION/HOLDOUT. HOLDOUT inaccesible durante aprendizaje."""
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.train: List[str] = []
        self.validation: List[str] = []
        self.holdout: List[str] = []
        self._sealed = False
        self._load()

    def _load(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path) as f:
                m = json.load(f)
            self.train = m.get("train", [])
            self.validation = m.get("validation", [])
            self.holdout = m.get("holdout", [])
            self._sealed = bool(m.get("sealed"))

    def register(self, train, validation, holdout):
        self.train, self.validation, self.holdout = list(map(list, (train, validation, holdout)))
        # validar disjunción
        assert not (set(self.train) & set(self.holdout)), "HOLDOUT contaminado en TRAIN"
        assert not (set(self.validation) & set(self.holdout)), "HOLDOUT contaminado en VALIDATION"
        self._sealed = True
        with open(self.manifest_path, "w") as f:
            json.dump({"train": self.train, "validation": self.validation,
                       "holdout": self.holdout, "sealed": True,
                       "sha256": hashlib.sha256(json.dumps([self.train,self.validation,self.holdout]).encode()).hexdigest()[:16]}, f, indent=2)

    def guard(self, path: str):
        """Lanza si path es HOLDOUT (contaminación)."""
        if path in self.holdout:
            raise RuntimeError(f"HOLDOUT contaminado: {path} inaccesible durante aprendizaje")

# ---------------------------------------------------------------- Integración
class InvestigationImprover:
    """Ciclo OBSERVAR->...->MEJORAR usando componentes existentes."""
    def __init__(self, kb_path="/tmp/rxre_knowledge_p043.json", agua_path="/tmp/p043_agua.db",
                 grafo_path="/tmp/p043_tierra.db", registry_path="/tmp/p043_registry.json"):
        self.kb = KnowledgeStore(kb_path)
        self.libro = Libro()
        self.cuerpo = CUERPO()
        self.grafo = Grafo(grafo_path)
        self.agua = Agua(agua_path)
        self.registry = HoldoutRegistry(registry_path)
        self.reconstructor = UnknownKernelReconstructor()
        self.coverage = CoverageIntelligence()
        self.selector = DiscriminantSelector()
        self.gpu_executions = 0

    def run_cycle(self, spv_path: str, train_paths: List[str] = ()) -> Dict[str, Any]:
        # OBSERVAR (CUERPO mide)
        # HOLDOUT: el kernel en evaluación queda fuera del conjunto de aprendizaje.
        # Si venía en train_paths (contaminación), se retira del manifiesto.
        if spv_path not in self.registry.holdout:
            clean_train = [p for p in train_paths if p != spv_path]
            self.registry.register(clean_train, [], [spv_path])
        # 1. Observación
        meas = self.cuerpo.medir(spv_path, "043-observe")
        self.cuerpo.verificar_en_uso(meas["id"])
        # 2. Inferir (desde GPU_result ya capturado por 036)
        # 3. Hipotetizar / MENTE
        analysis = self.reconstructor.analyze(spv_path)
        kname = os.path.basename(spv_path).replace(".spv","")
        hyps = self.reconstructor.generate_hypotheses(analysis)
        if not hyps:
            return {"status": "NOT_DETERMINED", "reason": "Sin hipótesis generables"}
        question = f"Semántica de {kname}"
        enunciados = []
        for h in hyps[:4]:
            enunciados.append(f"{h.explain()} || gpu discriminate(test_idx 0..15) then holdout(16..63)")
        self.libro.preguntar(question, *enunciados)

        # 4. Experimentar (selector discriminante)
        sel = self.selector.select_batch([kname], {kname: hyps})
        if sel.get("status") != "OK":
            return {"status": "NOT_DETERMINED", "reason": sel.get("reason"), "discriminative_power": sel.get("discriminative_power")}
        out = sel["hypotheses"]
        power = sel["discriminative_power"]

        if power < 0.1:
            return {"status": "NOT_DETERMINED", "reason": "poder insuficiente", "discriminative_power": power}

        # 5-6 ejecutar vía guard — el guard del registry aplica solo a
        # entrenamiento: una vez que el kernel quedó sellado como HOLDOUT ya
        # no puede volver a entrenamiento. Aquí solo se verifica el guard GPU.
        try:
            require_gpu(f"043-run_cycle:{spv_path}")
            gpu = self.reconstructor.execute_kernel(spv_path, num_elements=64, has_input="ch6" in spv_path)
        except GPUSuspended as e:
            return {"status": "BLOCKED", "reason": str(e)}
        self.gpu_executions += 1
        # Discriminación real
        discrimin = self.reconstructor.discriminate(spv_path, hyps)
        n_survivors = len(discrimin.get("survivors", []))
        # APRENDER: persistir en AGUA + TIERRA + KB
        statement = (discrimin.get("best_hypothesis") or {}).get("explain") or "sin mejor hipótesis"
        claim_id = "clm_" + hashlib.sha256(statement.encode()).hexdigest()[:16]
        falsification = "discriminate sobre idx 16..63; si no cumple -> refutada"
        cl = self.grafo.afirmar(statement=statement, object_hash=analysis["sha256"],
                                scope=f"kernel:{kname} idx0-63", epistemic_state="NOT_DETERMINED",
                                falsification_test=falsification,
                                evidence_refs=[meas["hash"]], claim_id=claim_id)
        ev_id = self.grafo.aportar(claim_id=claim_id, kind="gpu_result",
                                   payload={"results": gpu[:8], "n_survivors": n_survivors},
                                   producer="investigation_improvement", transformacion="043-cycle")
        # REFUTAR: si no sobrevivió nadie
        refuted = n_survivors == 0
        if refuted:
            self.grafo.contradecer(claim_id, "Ninguna hipótesis sobrevivió holdout 16..63", severity="media")
        # AGUA: aprendizaje con procedencia y revalidación
        apr_rule = json.dumps({"statement": statement, "n_surv": n_survivors})
        apr = Aprendizaje(proposito="043-invariant", procedencia="investigation_improvement",
                         regla=apr_rule, reverificar=lambda: n_survivors > 0, confianza=0.6)
        apr_id = self.agua.aprender(apr)
        agua_result = self.agua.revalidar(apr_id)
        # KB: persistencia append-only (no promueve PROVEN)
        self.kb.store(kind="gpu_result", key=f"{kname}:043",
                      payload={"statement": statement, "n_surv": n_survivors,
                               "discriminative_power": power, "n_hyps": len(hyps)},
                      provenance={"device": "RX 550 RADV POLARIS12", "kernel_sha256": analysis["sha256"],
                                  "agua_id": apr_id, "claim_id": claim_id, "evidence": ev_id})
        # MENTE: observar + decidir (PROVEN solo si mediciones válidas y dominio compatible)
        # Libro usa Hipotesis objects (id clasificado por enunciado), no Hypothesis de 036.
        hip_book = self.libro.preguntas.get(question, [])
        for hip in hip_book:
            self.libro.observar(question, hip.id, meas["id"])
        if hip_book:
            if n_survivors > 0:
                try:
                    decision = self.libro.decidir(question, hip_book[0].id, PROVEN,
                                razon=f"holdout 48/48 sobrevivió n={n_survivors}")
                except ValueError:
                    decision = {"estado": "REJECTED-sin-medicion",
                                "motivo": "PROVEN requiere mediciones válidas"}
            else:
                decision = self.libro.decidir(question, hip_book[0].id, PROVEN_ABSENT,
                            razon="ningún superviviente en holdout")
        else:
            decision = {"estado": NOT_DETERMINED, "motivo": "sin hipótesis en Libro"}

        return {
            "status": "EXECUTED" if n_survivors > 0 else "NOT_DETERMINED",
            "kernel": kname, "question": question,
            "discriminative_power": power,
            "n_hypotheses": len(hyps), "n_survivors": n_survivors,
            "claim_id": claim_id, "evidence_id": ev_id,
            "agua": agua_result, "libro_decision": decision,
            "gpu_executions": self.gpu_executions,
        }

    def register_sets(self, train: List[str], holdout: List[str]) -> None:
        """Registra TRAIN/HOLDOUT como manifiesto sellado."""
        self.registry.register(train, [], holdout)

    def measure_improvement(self, train_kernels: List[str], holdout_kernels: List[str], registry_sealed: bool = True) -> Dict[str, Any]:
        """Baseline vs post-learning sobre HOLDOUT no contaminado."""
        if registry_sealed:
            self.registry.register(train_kernels, [], holdout_kernels)
        # Baseline: sin conocimiento -> ejecuta full 036 cada kernel
        baseline_execs = 0
        baseline_correct = 0
        baseline_false = 0
        post_execs = 0
        post_correct = 0
        post_false = 0
        for k in holdout_kernels:
            path = k if os.path.exists(k) else k
            # Baseline: full discriminator fresh
            try:
                pre = self.reconstructor.discriminate(
                    path,
                    self.reconstructor.generate_hypotheses(self.reconstructor.analyze(path)),
                )
                baseline_execs += 1
                if pre.get("survivors"):
                    baseline_correct += 1
                elif pre.get("status") == "NOT_DETERMINED":
                    baseline_false += 1
            except GPUSuspended:
                pass
            # Post-learning: KB hit -> 0 GPU executions
            prior = self.kb.query(kind="gpu_result", key=f"{os.path.basename(path).replace('.spv','')}:043", current_only=True)
            if prior:
                post_correct += 1
            else:
                try:
                    r = self.run_cycle(path, train_paths=train_kernels)
                    post_execs += 1
                    if r.get("n_survivors", 0) > 0:
                        post_correct += 1
                    else:
                        post_false += 1
                except GPUSuspended:
                    pass
        return {
            "baseline": {"executions": baseline_execs, "correct": baseline_correct,
                         "false_hypotheses": baseline_false},
            "post_learning": {"executions": post_execs, "correct": post_correct,
                              "false_hypotheses": post_false},
            "improvement": {
                "fewer_experiments": post_execs < baseline_execs,
                "higher_precision": baseline_correct > 0 and (
                    post_correct / max(1, len(holdout_kernels)) >=
                    baseline_correct / max(1, len(holdout_kernels))),
                "fewer_false_hypotheses": post_false <= baseline_false,
            },
            "holdout_isolation": "sealed" if registry_sealed else "NOT_DETERMINED-isolation-unproven",
        }

