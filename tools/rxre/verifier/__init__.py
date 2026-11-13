"""IndependentVerifier — verificación independiente confinada para RXRE.

Integración de RXRE-VERIFIER-001: contrato `verify()`, backend bwrap,
integridad de paquete, sellado temporal, auditoría de sesión.
No sustituye a contratos de seguridad ni a TIERRA; complementa el flujo
INVESTIGACIÓN -> EVIDENCIA SELLADA -> VERIFIER -> DICTAMEN.
"""
from .independent_verifier import (
    verify, VerificationRequest, VerificationResult, CaseSpec,
    EXECUTION_RUNNING, EXECUTION_OK, EXECUTION_BLOCKED,
    EPISTEMIC_PROVEN, EPISTEMIC_PARTIAL, EPISTEMIC_NOT_DETERMINED,
    EPISTEMIC_BLOCKED, EPISTEMIC_ABSTAINED,
)
from . import acceptance_policy
__all__ = ["verify", "VerificationRequest", "VerificationResult", "CaseSpec",
           "EXECUTION_RUNNING", "EXECUTION_OK", "EXECUTION_BLOCKED",
           "EPISTEMIC_PROVEN", "EPISTEMIC_PARTIAL", "EPISTEMIC_NOT_DETERMINED",
           "EPISTEMIC_BLOCKED", "EPISTEMIC_ABSTAINED", "acceptance_policy"]
