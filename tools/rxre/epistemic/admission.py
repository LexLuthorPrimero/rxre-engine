"""Admisión centralizada (extracción admission_tierra, sin deps)."""
from __future__ import annotations
VALID_PROVENANCES = {"EXPLICIT"}
class AdmitResult:
    def __init__(self, allowed, reason, scope_provenance):
        self.allowed = allowed; self.reason = reason; self.scope_provenance = scope_provenance

def admit_claim(statement, object_hash, scope, scope_provenance, producer_id=None, producer_capability=None, result_id=None, request_id=None, evidence_refs=None, resolver_refs=None):
    if not isinstance(statement, str) or not statement.strip():
        return AdmitResult(False, "statement vacío", "UNKNOWN")
    if not isinstance(object_hash, str) or not object_hash.strip():
        return AdmitResult(False, "object_hash vacío", "UNKNOWN")
    if not isinstance(scope, str) or not scope.strip():
        return AdmitResult(False, "scope vacío", "UNKNOWN")
    if scope_provenance not in VALID_PROVENANCES:
        return AdmitResult(False, f"scope_provenance {scope_provenance!r} no es EXPLICIT", scope_provenance or "UNKNOWN")
    refs = evidence_refs or []
    if not isinstance(refs, list):
        return AdmitResult(False, "evidence_refs no es lista", scope_provenance)
    if refs and resolver_refs is None:
        return AdmitResult(False, "referencias sin resolver", scope_provenance)
    for r in refs:
        if not isinstance(r, str) or not r.strip():
            return AdmitResult(False, f"referencia inválida: {r!r}", scope_provenance)
        if resolver_refs is not None and not resolver_refs(r):
            return AdmitResult(False, f"referencia inexistente: {r}", scope_provenance)
    if result_id is not None and (not isinstance(result_id, str) or not result_id.strip()):
        return AdmitResult(False, "result_id inválido", scope_provenance)
    return AdmitResult(True, "admitido", scope_provenance)
