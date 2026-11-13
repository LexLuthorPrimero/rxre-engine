#!/usr/bin/env python3
"""RXRE GPU Availability Guard v2 — detección fina, suspensión, reanudación por artefacto.

Estados (distinguidos por evidencia, no por heurística):
  HEALTHY       dispatch mínimo completo → RESULTS recibidos
  BUSY          timeout en probe SIN evidencia de hang (ocupada o lenta; suspechosa)
  WEDGED        timeout + evidencia de hang: sysfs gpu_busy_percent==100, o marcador
                RADV "GPU hang" en la salida del harness
  NOT_VALIDATED el GPU responde HEALTHY pero aún no se re-ejecutó trabajo tras una
                cuña conocida (recovery observed, work NOT re-validated)
  NOT_PRESENT   harness/dispositivo ausente o no abre
  UNKNOWN       respuesta inesperada

Reglas arquitectónicas (compilación ≠ ejecución):
- La investigación de compilación (ISA dump via RADV_DEBUG=asm en vkCreate*Pipelines)
  no requiere dispatch ni GPU sana: usar --no-run.
- La investigación de ejecución requiere GPU sana y un experimento que justifique
  la sumisión: gate `require_gpu()` (lanza GPUSuspended si no HEALTHY).
- Trabajo suspendido NO puede producir VALIDATED: require_gpu bloquea y
  run_guarded marca SUSPENDED/TIMEOUT sin tocar conocimiento.
- Reanudación POR ARTEFACTO Y EXPERIMENTO (nunca promoción global): el ledger
  solo limpia el artefacto que re-ejecutó con éxito tras HEALTHY.
- GPU_busy=0 o reboot no demuestran sanidad: probe funcional posterior es obligatorio.
"""
from __future__ import annotations
import os, sys, json, time, subprocess, hashlib, glob
from typing import Dict, Any, Callable, Optional
from datetime import datetime

ROOT = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

HARNESS = "/home/lucas/Escritorio/rxre/tools/rxre/harness/bin/vk_cf_test"
PROBE_SPV = "/home/lucas/Escritorio/rxre/tools/rxre/harness/fixtures/polaris39/kernels/kE.spv"
LEDGER_DEFAULT = "/tmp/rxre_gpu_availability_ledger.json"

HEALTHY, BUSY, WEDGED, NOT_VALIDATED, NOT_PRESENT, UNKNOWN = (
    "HEALTHY", "BUSY", "WEDGED", "NOT_VALIDATED", "NOT_PRESENT", "UNKNOWN")
ALL_STATES = (HEALTHY, BUSY, WEDGED, NOT_VALIDATED, NOT_PRESENT, UNKNOWN)


def hang_evidence(output: str = "") -> bool:
    """Evidence of a wedged GPU: driver marker or any card at 100% busy."""
    if output and ("GPU hang" in output or "radv: GPU hang" in output):
        return True
    for p in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        try:
            with open(p) as f:
                if f.read().strip() == "100":
                    return True
        except OSError:
            continue
    return False


def gpu_health_probe(timeout_s: int = 12, spv: str = PROBE_SPV,
                     harness: str = HARNESS,
                     evidence_fn: Optional[Callable[[str], bool]] = None) -> str:
    """One minimal dispatch (probe only — status, never an experiment result).
    Never raises."""
    if not os.path.isfile(harness) or not os.path.isfile(spv):
        return NOT_PRESENT
    evidence_fn = evidence_fn or hang_evidence
    try:
        r = subprocess.run([harness, spv, "4", "0", "2"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout_s, errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if "RESULTS:" in (r.stdout or ""):
            return HEALTHY
        if "FENCE_TIMEOUT" in out or "READOUT_TIMEOUT" in out or r.returncode != 0:
            return WEDGED if evidence_fn(out) else BUSY
        return UNKNOWN
    except subprocess.TimeoutExpired:
        return WEDGED if evidence_fn("timeout") else BUSY
    except Exception:
        return NOT_PRESENT


class GPUSuspended(RuntimeError):
    """Raised when physical GPU execution is attempted without HEALTHY state."""


class SuspensionLedger:
    """Persistent record of artifacts suspended until per-artifact re-validation."""

    def __init__(self, path: str = LEDGER_DEFAULT):
        self.path = path
        self.suspended: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self.suspended = json.load(f)
            except Exception:
                self.suspended = {}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.suspended, f, indent=2, sort_keys=True)

    def key(self, artifact_kind: str, artifact_id: str) -> str:
        return hashlib.sha256(f"{artifact_kind}|{artifact_id}".encode()).hexdigest()[:16]

    def mark(self, artifact_kind: str, artifact_id: str, reason: str):
        k = self.key(artifact_kind, artifact_id)
        self.suspended[k] = {"kind": artifact_kind, "id": artifact_id,
                             "reason": reason, "since": datetime.now().isoformat(),
                             "cleared": False}
        self._save()
        return k

    def clear_artifact(self, artifact_kind: str, artifact_id: str, reason: str = "gpu_recovered_and_rerun"):
        """Clear EXACTLY ONE artifact — never a global promotion."""
        k = self.key(artifact_kind, artifact_id)
        if k in self.suspended and not self.suspended[k].get("cleared"):
            self.suspended[k]["cleared"] = True
            self.suspended[k]["clear_reason"] = reason
            self.suspended[k]["cleared_at"] = datetime.now().isoformat()
            self._save()

    def active(self) -> list:
        return [v for v in self.suspended.values() if not v.get("cleared")]


class AvailabilityGuard:
    def __init__(self, knowledge_path: str = "/tmp/rxre_knowledge_store.json",
                 ledger_path: str = LEDGER_DEFAULT,
                 probe: Optional[Callable[[], str]] = None,
                 evidence_fn: Optional[Callable[[str], bool]] = None):
        from rxre.polaris12.continuous_knowledge_evolution import KnowledgeStore
        self.knowledge = KnowledgeStore(knowledge_path)
        self.ledger = SuspensionLedger(ledger_path)
        self.probe = probe or (lambda: gpu_health_probe(evidence_fn=evidence_fn))
        self.gpu_state = UNKNOWN
        self._wedge_seen = False
        self.events = 0

    def record(self, state: str, context: str):
        self.knowledge.store(
            kind="gpu_availability",
            key=hashlib.sha256(f"{state}|{time.time()}".encode()).hexdigest()[:16],
            payload={"state": state, "context": context,
                     "suspended_active": len(self.ledger.active())},
            provenance={"source": "gpu_availability.py",
                        "timestamp": datetime.now().isoformat()})
        self.events += 1

    EXECUTABLE = (HEALTHY, NOT_VALIDATED)

    def check(self, context: str = "probe") -> str:
        state = self.probe()
        if state in (WEDGED, BUSY):
            self._wedge_seen = True
            self.record(state, context)
        elif state == HEALTHY and self._wedge_seen:
            # Recovery observed but this work item not re-validated yet
            state = NOT_VALIDATED
            self.record(state, context)
        self.gpu_state = state
        return state

    def run_guarded(self, fn: Callable[[], Any], artifact_kind: str,
                    artifact_id: str) -> Dict[str, Any]:
        state = self.check("run_guarded")
        if state not in self.EXECUTABLE:
            self.ledger.mark(artifact_kind, artifact_id, f"gpu_{state}")
            return {"status": "SUSPENDED", "reason": f"gpu_{state}",
                    "artifact": artifact_id, "gpu_state": state}
        result = fn()
        # Per-artifact resume ONLY — this artifact re-executed healthy.
        self.ledger.clear_artifact(artifact_kind, artifact_id)
        self._wedge_seen = False
        return {"status": "EXECUTED", "result": result, "gpu_state": state}

    def summary(self) -> Dict[str, Any]:
        return {"gpu_state": self.gpu_state,
                "suspended_active": len(self.ledger.active()),
                "availability_events": self.events,
                "knowledge_total": self.knowledge.count()}


_GUARD: Optional[AvailabilityGuard] = None

def guard_singleton() -> AvailabilityGuard:
    """Process-wide guard (memoized probe: one probe per process unless wedged seen)."""
    global _GUARD
    if _GUARD is None:
        _GUARD = AvailabilityGuard(
            knowledge_path=os.environ.get("RXRE_KNOWLEDGE_STORE", "/tmp/rxre_knowledge_store.json"),
            ledger_path=os.environ.get("RXRE_GPU_LEDGER", LEDGER_DEFAULT))
    return _GUARD

def require_gpu(context: str = "gpu_execution") -> str:
    """Gate for ANY physical GPU submission.
    Raises GPUSuspended unless the probe passes (HEALTHY or NOT_VALIDATED —
    i.e., physically responsive; NOT_VALIDATED means recovery observed, work
    pending re-validation)."""
    state = guard_singleton().check(context)
    if state not in AvailabilityGuard.EXECUTABLE:
        guard_singleton().ledger.mark("gpu_execution", context, f"gpu_{state}")
        raise GPUSuspended(f"GPU_EXECUTION_BLOCKED state={state} context={context}")
    return state

def main():
    import argparse
    ap = argparse.ArgumentParser(description="RXRE GPU availability probe")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    guard = AvailabilityGuard()
    state = guard.check("cli_probe")
    out = {"state": state, **guard.summary()}
    print(json.dumps(out, indent=2) if args.json else f"GPU_STATE={state} suspended_active={out['suspended_active']}")


if __name__ == "__main__":
    main()
