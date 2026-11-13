"""Contratos y pruebas para impedir resultados inventados o mejoras sin validación"""
from __future__ import annotations
from typing import Dict, Any, List

REQUIRED_EVIDENCE_FIELDS = ["hash", "artifact_path", "timestamp"]
FORBIDDEN_CLAIMS = ["proven", "guaranteed", "impossible_to_fail"]  # without evidence

def validate_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Valida que evidencia sea verificable"""
    missing = [f for f in REQUIRED_EVIDENCE_FIELDS if f not in evidence]
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "note": "Evidence must be verifiable with provenance",
    }

def validate_improvement(claim: Dict[str, Any], measurements: List[Dict] = None) -> Dict[str, Any]:
    """Requiere mediciones reproducibles para mejoras"""
    measurements = measurements or []
    has_reproducible = any(m.get("reproducible", False) for m in measurements)
    has_baseline = any(m.get("baseline_comparison", False) for m in measurements)
    return {
        "allowed": has_reproducible and has_baseline and len(measurements) > 0,
        "reasons": [],
        "requirements": ["reproducible measurements", "baseline comparison", "evidence refs"],
    }

POLARIS_CONTRACTS = {
    "evidence_first": True,
    "no_invention": True,
    "no_hw_mod": True,
    "no_firmware_flash": True,
    "simulation_not_real": True,
    "improvement_requires_measurement": True,
    "reversible_changes": True,
}
