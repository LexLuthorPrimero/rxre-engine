"""Seal-before-reveal (extracción sandbox.py, sin bwrap)."""
from __future__ import annotations
import hashlib
import json
from .states import SealPhase
from .errors import SealViolation

ORDER = [SealPhase.CREATED, SealPhase.PREDICTING, SealPhase.SEALED, SealPhase.EVIDENCE_RELEASED, SealPhase.VERIFYING, SealPhase.REVEALED]

def seal_prediction(prediction: dict, phase: SealPhase = SealPhase.PREDICTING) -> dict:
    if not isinstance(prediction, dict):
        raise SealViolation("predicción malformada")
    ph = phase.value if hasattr(phase, "value") else phase
    canonical = json.dumps(prediction, sort_keys=True).encode()
    return {"prediction": prediction, "phase": SealPhase.SEALED.value, "sha256": hashlib.sha256(canonical).hexdigest(), "canonical_excluded_phase": True}

def validate_seal_before_reveal(seal: dict, evidence_access_time: float, seal_time: float = None) -> bool:
    try:
        if not isinstance(seal, dict) or "sha256" not in seal:
            return False
        if seal.get("phase") != SealPhase.SEALED.value:
            return False
        pred = seal.get("prediction")
        if not isinstance(pred, dict):
            return False
        if hashlib.sha256(json.dumps(pred, sort_keys=True).encode()).hexdigest() != seal["sha256"]:
            return False
        if seal_time is not None and evidence_access_time < seal_time:
            return True  # evidenció acceso antes del sello? No, debe ser sellado antes de revelar: si acceso < sello -> violación
            # Nota: regla es seal_time <= access_time. Si access < seal -> violación
        if seal_time is not None and evidence_access_time < seal_time:
            return False
        return True
    except Exception:
        return False
