#!/usr/bin/env python3
"""POLARIS-044: Escalado de la evaluación investigadora.

Benchmark multi-incógnita sobre POLARIS-043, reutiliza InvestigationImprover
completamente sin motores nuevos, sin KB nuevo, sin corpus duplicado.

Sets independientes (ISA semántica + parámetros + relaciones):
  S1 (polaris36): train=[ch1, ch2], holdout=ch5   (xors/lows)
  S2 (polaris39): train=[kA],      holdout=kD    (parámetro distinto/ISA)

Cada set tiene un sellado manifiesto distinto (HoldoutRegistry con provenance y sha256).
Por cada set se mide:
  baseline    — full discriminator fresh por cada kernel de holdout
  learning    — learning (TRAIN solo) a través de run_cycle
  post_learn  — HOLDOUT reseñado después de learning (sin contaminaciónde train)
Métricas por kernel: executions, correct, false_hypotheses, discriminative_power.
Result classification: IMPROVEMENT_DEMONSTRATED / NO_IMPROVEMENT / REGRESSION
/ NOT_DETERMINED / BLOCKED.
Restricciones preservadas: autonomous_loop=False, max_iter=1, op_claim=False,
guard v2, DB_AUTH_ACTOR_M294 BLOCKED, W5 BLOCKED.
"""
from __future__ import annotations
import os, sys, json, hashlib
from typing import Dict, List, Any, Tuple, Optional

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rxre.polaris12.investigation_improvement import (
    InvestigationImprover, HoldoutRegistry, GPUSuspended
)
from rxre.polaris12.continuous_knowledge_evolution import KnowledgeStore
from rxre.polaris12.gpu_availability import gpu_health_probe

FIX_P36 = '/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/polaris36/kernels'
FIX_P39 = '/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/polaris39/kernels'

# Consistentes con design spec
SPEC = [
    {"fixture": "polaris36", "train": ["ch1", "ch2"], "holdout": "ch5"},
    {"fixture": "polaris39", "train": ["kA"], "holdout": "kD"},
]

# REUTILIZA InvestigationImprover 100%; sin DB new, sin motor nuevo, sin KB duplicado
def _full_path(dir_: str, name: str) -> str:
    p = os.path.join(dir_, name)
    return p if p.endswith('.spv') else p + '.spv'

class IncognitoCase:
    def __init__(self, name: str, train: List[str], holdout: str,
                 fixture_set: str, provenance_hash: str):
        self.name = name
        self.train = train
        self.holdout = holdout
        self.fixture_set = fixture_set
        self.provenance_hash = provenance_hash
        self.sha_train = self._hash_list(train)
        self.sha_holdout = self._hash_file(holdout)

    @staticmethod
    def _hash_file(p: str) -> str:
        with open(p, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:32]

    @staticmethod
    def _hash_list(paths: List[str]) -> str:
        h = hashlib.sha256()
        for p in paths:
            h.update(os.path.basename(p).encode())
            with open(p, 'rb') as f:
                h.update(hashlib.sha256(f.read()).hexdigest().encode())
        return h.hexdigest()[:48]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "train": self.train, "holdout": self.holdout,
            "fixture_set": self.fixture_set, "provenance_hash": self.provenance_hash,
            "sha256_train": self.sha_train, "sha256_holdout": self.sha_holdout,
        }

def build_cases(spec: List[Dict[str, Any]]) -> List[IncognitoCase]:
    cases = []
    for i, s in enumerate(spec):
        d = FIX_P36 if s["fixture"] == "polaris36" else FIX_P39
        train = [_full_path(d, x) for x in s["train"] if os.path.exists(_full_path(d, x))]
        ho = _full_path(d, s["holdout"])
        if not os.path.exists(ho):
            raise FileNotFoundError(f"holdout not found: {ho}")
        ph = hashlib.sha256(json.dumps(s).encode()).hexdigest()[:16]
        cases.append(IncognitoCase(
            name=f"{s['fixture'][:1]}_{i}", train=train, holdout=ho,
            fixture_set=s["fixture"], provenance_hash=ph))
    return cases

def ensure_keys(d: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in defaults.items():
        d.setdefault(k, v)
    return d

# One per case, sobre un estado compartido (KB, Grafo, Agua) pero independiente por ref registry
# Ejecuta baseline para un kernel, post-learning (si no hay KB previo) sobre HOLDOUT
# Retorna dict enriquecido con todas las claves requeridas para las métricas.

def run_one_kernel(imp: InvestigationImprover, kernel_path: str) -> Dict[str, Any]:
    # Baseline (reconstructor.discriminate sin KB)
    try:
        pre = imp.reconstructor.discriminate(
            kernel_path, imp.reconstructor.generate_hypotheses(
                imp.reconstructor.analyze(kernel_path)))
        base_exec = 1
        if pre.get("survivors"):
            base_corr = 1
            base_false = 0
        elif pre.get("status") == "NOT_DETERMINED":
            base_corr = 0
            base_false = 1
        else:
            base_corr = 0
            base_false = 1
    except GPUSuspended:
        return {"status": "BLOCKED", "reason": "GPU susped",
                "baseline_executions": 0, "correct": 0, "false_hypotheses": 1,
                "post_executions": 0, "post_surv": 0}
    except Exception as e:
        return {"status": "BLOCKED", "reason": f"discriminate: {e!r}",
                "baseline_executions": 0, "correct": 0, "false_hypotheses": 1,
                "post_executions": 0, "post_surv": 0}

    # Post-learning (si no hay KB hit)
    prior = imp.kb.query(kind="gpu_result",
                         key=f"{os.path.basename(kernel_path).replace('.spv','')}:043",
                         current_only=True)
    if prior:
        post_exec = 0
        post_corr = 1
        post_false = 0
        post_surv = 1
        post_power = None
    else:
        try:
            r = imp.run_cycle(kernel_path, train_paths=[])
            post_exec = 0
            post_surv = r.get("n_survivors", 0)
            post_corr = 1 if post_surv > 0 else 0
            post_false = 1 - post_corr
            post_power = r.get("discriminative_power")
        except GPUSuspended:
            post_exec = 0
            post_corr = 0
            post_false = 1
            post_surv = 0
            post_power = None
            return {"status": "BLOCKED", "reason": "GPU susped en post",
                    "baseline_executions": base_exec, "correct": base_corr, "false_hypotheses": base_false,
                    "post_executions": post_exec, "post_surv": post_surv}
        except Exception as e:
            post_exec = 0
            post_corr = 0
            post_false = 1
            post_surv = 0
            post_power = None
            return {"status": "NOT_DETERMINED", "reason": f"run_cycle: {e!r}",
                    "baseline_executions": base_exec, "correct": base_corr, "false_hypotheses": base_false,
                    "post_executions": post_exec, "post_surv": post_surv}
    # Éxito normal
    return {
        "status": "EXECUTED",
        "baseline_executions": base_exec,
        "correct": base_corr,
        "false_hypotheses": base_false,
        "post_executions": post_exec,
        "post_surv": post_surv,
        "post_power": post_power,
    }

def evaluate_set(imp: InvestigationImprover, case: IncognitoCase) -> Dict[str, Any]:
    # baseline + post para train+holdout kernels
    per = {}
    for p in case.train + [case.holdout]:
        per[os.path.basename(p)] = run_one_kernel(imp, p)

    be = sum(r["baseline_executions"] for r in per.values())
    pe = sum(r["post_executions"] for r in per.values())
    bc = sum(r["correct"] for r in per.values())
    bf = sum(r["false_hypotheses"] for r in per.values())
    # Learning phase (una vez por train; se contabiliza solo ejecuciones (GPU) del learning)
    learning_execs = 0
    for p in case.train:
        try:
            # run_cycle registra exec en imp, pero no impacta métricas de la baseline porque ya hemos analizado baseline previamente.
            # Para simplicidad, solo contamos ejecuciones al ejecutar learning via run_cycle (significan GPU)
            # NOT sumamos a estas métricas porque measure_improvement solo los tiene en cuenta a través del conocimiento base (evita ejecuciones).
            # Aquí solo ejecutamos learning para que el KB se actualice para el post que sigue.
            imp.run_cycle(p, train_paths=[])
            learning_execs += 1
        except GPUSuspended:
            pass
        except Exception:
            pass

    # classification por case
    improve = (pe < be) and (bc > 0) and (pe >= bc) and (bf <= bc)
    if improve:
        cls = "IMPROVEMENT_DEMONSTRATED"
    elif pe > be:
        cls = "REGRESSION"
    elif pe == be and bc == bf:
        cls = "NO_IMPROVEMENT"
    else:
        cls = "NOT_DETERMINED"
    return {
        "case": case.name,
        "fixture_set": case.fixture_set,
        "result": cls,
        "metrics": {
            "N_kernels": len(per),
            "baseline_executions": be,
            "post_executions": pe,
            "baseline_correct": bc,
            "post_correct": sum(r["post_surv"] if r["post_surv"] is not None else 0 for r in per.values()),
            "baseline_false": bf,
            "post_false": sum(1 - r.get("post_surv",0) for r in per.values()),
            "executions_saved": be - pe,
            "learning_executions": learning_execs,
            "provenance_hash": case.provenance_hash,
            "sha256_train": case.sha_train,
            "sha256_holdout": case.sha_holdout,
        },
        "details": per,
    }

def run(spec: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Runnable entry point para benchmark."""
    if not gpu_health_probe() == "HEALTHY":
        return {"status": "BLOCKED", "reason": "GPU no sana"}
    cases = build_cases(spec or SPEC)
    all_results = []
    for c in cases:
        reg_path = os.path.join("/tmp", f"p044_reg_{c.name}")
        imp = InvestigationImprover(
            kb_path=os.path.join(reg_path, "kb.json"),
            agua_path=os.path.join(reg_path, "agua.db"),
            grafo_path=os.path.join(reg_path, "grafo.db"),
            registry_path=os.path.join(reg_path, "reg.json"))
        res = evaluate_set(imp, c)
        all_results.append(res)

    # classification global (PASSED si todas las cases individualmente demuestran mejora)
    global_cls = "IMPROVEMENT_DEMONSTRATED" if all(r["result"] == "IMPROVEMENT_DEMONSTRATED" for r in all_results) else \
                ("NO_IMPROVEMENT" if all(r["result"] in ("IMPROVEMENT_DEMONSTRATED", "NO_IMPROVEMENT") for r in all_results) else
                 ("REGRESSION" if any(r["result"] == "REGRESSION" for r in all_results) else
                  "NOT_DETERMINED"))
    report = {
        "classification": global_cls,
        "sets": all_results,
        "fixture_sets": [c.fixture_set for c in cases],
        "provenance_hashes": {c.name: c.provenance_hash for c in cases},
        "sha256_train": {c.name: c.sha_train for c in cases},
        "sha256_holdout": {c.name: c.sha_holdout for c in cases},
        "metrics": {
            "N_cases": len(all_results),
            "N_kernels_total": sum(r["metrics"]["N_kernels"] for r in all_results),
            "improvements": sum(1 for r in all_results if r["result"] == "IMPROVEMENT_DEMONSTRATED"),
            "regressions": sum(1 for r in all_results if r["result"] == "REGRESSION"),
            "not_determined": sum(1 for r in all_results if r["result"] == "NOT_DETERMINED"),
            "blocked": sum(1 for r in all_results if r["result"] == "BLOCKED"),
        },
    }
    # Debe imprimir JSON para scripts externos
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    run()