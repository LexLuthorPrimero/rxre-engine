"""RXRE-CONTINUATION-249D — Control centralizado de admisión a TIERRA.

Única frontera de admisión para escrituras operacionales en TIERRA.
No modifica g.afirmar ni contratos protegidos. No escribe en DB.
Devuelve (allowed: bool, reason: str, scope_provenance: str).
"""
from __future__ import annotations

VALID_PROVENANCES = {"EXPLICIT"}


def admit_claim(statement, object_hash, scope, scope_provenance,
                producer_id=None, producer_capability=None,
                result_id=None, request_id=None, evidence_refs=None,
                resolver_refs=None):
    """Admisión centralizada. Devuelve (allowed, reason)."""
    if not isinstance(statement, str) or not statement.strip():
        return False, "statement vacío", "UNKNOWN"
    if not isinstance(object_hash, str) or not object_hash.strip():
        return False, "object_hash vacío", "UNKNOWN"
    if not isinstance(scope, str) or not scope.strip():
        return False, "scope vacío", "UNKNOWN"
    if scope_provenance not in VALID_PROVENANCES:
        return False, "scope_provenance %r no es EXPLICIT" % (scope_provenance,), scope_provenance or "UNKNOWN"
    refs = evidence_refs or []
    if not isinstance(refs, list):
        return False, "evidence_refs no es lista", scope_provenance
    if refs and resolver_refs is None:
        return False, "referencias sin resolver", scope_provenance
    for r in refs:
        if not isinstance(r, str) or not r.strip():
            return False, "referencia inválida: %r" % (r,), scope_provenance
        if resolver_refs is not None and not resolver_refs(r):
            return False, "referencia inexistente: %s" % r, scope_provenance
    # Vinculación productor/resultado (si se proporcionan)
    if result_id is not None and (not isinstance(result_id, str) or not result_id.strip()):
        return False, "result_id inválido", scope_provenance
    return True, "admitido", scope_provenance


def is_operational_write_allowed(*args, **kwargs):
    allowed, _, _ = admit_claim(*args, **kwargs)
    return allowed
