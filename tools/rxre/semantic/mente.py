#!/usr/bin/env python3
"""MENTE — motor mínimo de hipótesis rivales y experimentos discriminantes (etapa 1).

Objetivo de este módulo (NO es comprensión semántica general):
1. Recibir hipótesis rivales FALSABLES sobre un dominio, cada una con predicción y coste.
2. Elegir, de una familia de entradas candidatas, las que MAXIMIZAN el contraste
   entre predicciones (poder discriminante), sin ejecutar el objetivo antes de tiempo.
3. Ejecutar el objetivo UNA VEZ con el input elegido y observar.
4. Actualizar el estado epistémico: hipótesis contradicha => REFUTED; la observación
   nunca equivale a PROVEN; lo que no se discrimina queda NOT_DETERMINED.

Invariantes:
- Las predicciones se registran ANTES de observar (sellado causal).
- Si ninguna entrada discrimina: todo NOT_DETERMINED; no se afirma nada.
- Un discriminante no decidido (excepción del candidato) se excluye con evidencia.
- El módulo no conoce el código fuente del objetivo: solo su comportamiento.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

RUNNER = subprocess.run

@dataclass
class RivalHypothesis:
    id: str
    property_name: str
    claim: str
    predict: Callable[[bytes], Any]          # predicción pre-registrada
    domain: Dict[str, Any]
    epistemic_status: str = "NOT_DETERMINED"
    discriminating_failures: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def predicted_for(self, x: bytes):
        try:
            return {"ok": True, "value": self.predict(x)}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

def _hash(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def select_discriminating_inputs(hypotheses: List[RivalHypothesis],
                                 candidates: List[bytes]) -> List[Dict[str, Any]]:
    """Devuelve candidatos ordenados por número de pares rivales que discrepan allí."""
    scored = []
    for x in candidates:
        preds = []
        for h in hypotheses:
            r = h.predicted_for(x)
            if not r["ok"]:
                r2 = None
            else:
                try:
                    r2 = json.dumps(r["value"], sort_keys=True, default=str)
                except Exception:
                    r2 = str(r["value"])
            preds.append((h.id, r2))
        disagree = 0
        for i in range(len(preds)):
            for j in range(i + 1, len(preds)):
                vi, vj = preds[i][1], preds[j][1]
                if vi is None or vj is None:
                    continue  # predicción fallida: sin evidencia, no descuenta
                if vi != vj:
                    disagree += 1
        if disagree:
            scored.append({"input": x, "disagreeing_pairs": disagree, "predictions": preds})
    scored.sort(key=lambda d: (-d["disagreeing_pairs"], str(d["input"])))
    return scored

def run_target(binary_path: str, x: bytes, timeout: float = 10.0,
               args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Ejecución controlada del objetivo; sin red/dev/mem, artefacto tratado como opaco."""
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    try:
        p = RUNNER([binary_path] + (args or []) + [x],
                   input=None, capture_output=True, timeout=timeout, env=env)
        return {"ok": True, "returncode": p.returncode,
                "stdout": p.stdout.decode("utf-8", errors="replace").strip(),
                "stderr": p.stderr.decode("utf-8", errors="replace").strip()}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

def _fmt_input(x):
    if isinstance(x, (bytes, bytearray)):
        return x.decode("utf-8", errors="replace")
    return str(x)

def mente_cycle(hypotheses: List[RivalHypothesis], candidates: List[bytes],
                target_binary: str, target_runner: Optional[Callable[[bytes], Any]] = None,
                target_args: Optional[List[str]] = None,
                mind_budget: int = 0) -> Dict[str, Any]:
    """Ciclo completo: registro → selección → ejecución discriminante → actualización."""
    report = {
        "target_sha256": _hash(target_binary) if os.path.isfile(target_binary) else None,
        "hypotheses": [h.id for h in hypotheses],
        "discriminating_candidates": [_fmt_input(c["input"])
                                      for c in select_discriminating_inputs(hypotheses, candidates)],
        "selected": None, "observation": None,
        "refuted": [], "surviving": [],
        "epistemic_status": "NOT_DETERMINED",
    }
    rivals = list(hypotheses)
    survivors = list(hypotheses)
    sequence = []

    ranked = select_discriminating_inputs(survivors, candidates)
    if not ranked:
        report = {
            "target_sha256": _hash(target_binary) if os.path.isfile(target_binary) else None,
            "hypotheses": [h.id for h in rivals],
            "discriminating_candidates": [],
            "selected": {"input": None, "arguments": target_args or [],
                         "disagreeing_pairs": None, "sequence": sequence},
            "observation": None,
            "rounds": 0,
            "observations": [],
            "refuted": [],
            "surviving": [h.id for h in survivors],
            "indeterminate": [],
            "epistemic_status": "NOT_DETERMINED",
            "limitacion": "ninguna entrada candidata discrimina entre las hipótesis en este dominio",
            "honesty_note": "El superviviente no ha sido verificado por un tercero; solo no fue refutado por este experimento en este dominio.",
        }
        return report

    rounds_used = 0
    used_inputs = set()
    refuted = []
    indeterminate = []
    observations = []
    last_obs = None
    obs_ok_final = True

    def _ripred(predictions_list, obs_ok):
        preds = []
        for pid, pred in predictions_list:
            if pred is not None:
                preds.append((pid, pred))
            else:
                preds.append((pid, None))
        return preds

    max_rounds = max(1, int(mind_budget or 0) + max(2, len(rivals)) * 4)
    while True:
        ranked = select_discriminating_inputs(survivors, candidates)
        ranked = [r for r in ranked if _fmt_input(r["input"]) not in used_inputs]
        if not ranked:
            break
        best = ranked[0]
        x = best["input"]
        used_inputs.add(_fmt_input(x))

        if target_runner is not None:
            obs_raw = target_runner(x)
            obs_ok = True
            obs = {"ok": True, "value": obs_raw}
        else:
            obs = run_target(target_binary, x, args=target_args)
            obs_ok = obs["ok"]

        observable = obs.get("value") if obs.get("value") is not None else obs.get("stdout") if obs.get("stdout") is not None else obs.get("returncode")
        observations.append({"input": _fmt_input(x), "value": observable})

        new_survivors = []
        for h in survivors:
            r = h.predicted_for(x)
            failed = r.get("ok") is False
            if failed:
                indeterminate.append(h.id)
                continue
            hv = json.dumps(r["value"], sort_keys=True, default=str)
            ov = None
            if obs_ok:
                try:
                    ov = json.dumps(observable, sort_keys=True, default=str)
                except Exception:
                    ov = str(observable)
            if obs_ok and hv == ov:
                new_survivors.append(h)
            elif obs_ok and hv != ov:
                h.discriminating_failures.append({"input": _fmt_input(x),
                                                  "predicted": r["value"],
                                                  "observed": observable})
                h.epistemic_status = "REFUTED"
                refuted.append(h.id)
            else:
                new_survivors.append(h)
                indeterminate.append(h.id)
        survivors = new_survivors
        last_obs = obs
        obs_ok_final = obs_ok
        rounds_used += 1
        if len(survivors) <= 1:
            break
        if rounds_used >= max_rounds:
            break

    report.update({
        "selected": {"input": _fmt_input(sorted(used_inputs, key=str)[0]) if used_inputs else None,
                     "arguments": target_args or [],
                     "disagreeing_pairs": None,
                     "sequence": sequence},
        "observation": last_obs,
        "rounds": rounds_used,
        "observations": observations,
        "refuted": refuted,
        "surviving": [h.id for h in survivors],
        "indeterminate": indeterminate,
        "epistemic_status": "UNKNOWN_WITHOUT_OBSERVED_EVIDENCE" if not obs_ok_final else (
            "NOT_DETERMINED" if survivors else "REFUTED_ALL"),
        "honesty_note": "El superviviente no ha sido verificado por un tercero; solo no fue refutado por este experimento en este dominio.",
    })
    if not obs_ok_final:
        report["limitacion"] = "target no ejecutable o obs fallida; no se afirma nada (fail-closed)"
    if len(survivors) == 1:
        report["limitacion"] = "único superviviente confirma consistencia en las observaciones, no equivalencia global"
    return report
