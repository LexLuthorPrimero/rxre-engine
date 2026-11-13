#!/usr/bin/env python3
"""RXRE-210 — Puerta de autorización explícita finding -> TIERRA.
No conecta automáticamente; requiere invocación explícita.
"""
from rxre.contracts.transition_policy import política_transición
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra

# The authorization gate is the combination of the policy (pure decision)
# and the pre-integration hook (isolated, disabled by default). The gate
# REJECTS any attempt that lacks explicit_enable or violates the rules.

# No new logic is invented: all 10 rules are enforced by the policy,
# and the hook enforces isolation. This file serves as the explicit
# authorization contract: if a caller does not pass explicit_enable=True,
# and does not supply resolver_refs (when required) and contradiction_statements
# (when required), the transition is REJECTED.

__all__ = ["autorizacion_transicion"]

def autorizacion_transicion(
    db_path: str,
    finding: dict,
    resolver_refs,
    contradiction_statements=None,
    explicit_enable: bool = False,
) -> dict:
    """Puerta de autorización. Llama a política + preintegración aislada.
    Rechaza si no se activa explícitamente."""
    if explicit_enable is not True:
        return {"decision": "REJECT", "reason": "autorización requiere explicit_enable=True (booleano exacto); recibido %r (%s)" % (explicit_enable, type(explicit_enable).__name__), "claim_id": None}
    # Delegar en política (pura) y luego en preintegración aislada
    pol = política_transición(finding, resolver_refs=resolver_refs, contradiction_statements=contradiction_statements)
    if pol["decision"] == "ACCEPT":
        return preintegrate_finding_to_tierra(db_path, finding, resolver_refs=resolver_refs, contradiction_statements=contradiction_statements, explicit_enable=True)
    else:
        return {**pol, "status": "blocked", "decision": pol["decision"]}
