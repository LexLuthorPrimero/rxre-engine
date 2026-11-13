"""Matriz de promoción (extracción de acceptance_policy, sin deps RXRE)."""
from __future__ import annotations
from .states import AcceptanceDecision
from .errors import PromotionDenied

_MAP = {
    "PROVEN": AcceptanceDecision.ACCEPT_WITH_DOMAIN,
    "PARTIAL": AcceptanceDecision.ACCEPT_LIMITED,
    "NOT_DETERMINED": AcceptanceDecision.WITHHOLD,
    "BLOCKED": AcceptanceDecision.DETACH,
    "ABSTAINED": AcceptanceDecision.ABSTAIN,
}

def guard_promotion(state, evidence=None):
    """Decisión pura fail-closed. evidence: dict|obj con execution_status, epistemic_status, integrity, session_audit, limitations.
    Retorna AcceptanceDecision; nunca promueve silenciosamente."""
    try:
        if evidence is None:
            return AcceptanceDecision.REJECT
        d = evidence if isinstance(evidence, dict) else getattr(evidence, "__dict__", None)
        if d is None:
            try:
                d = dict(evidence)
            except Exception:
                return AcceptanceDecision.REJECT
        st = state.value if hasattr(state, "value") else state
        if not isinstance(st, str) or st not in _MAP:
            return AcceptanceDecision.REJECT
        # execution gate
        es = d.get("execution_status")
        if es != "OK":  # fail-closed: ausente o distinto OK
            _es_val = es
            return AcceptanceDecision.DETACH if _es_val == "BLOCKED" else AcceptanceDecision.REJECT
        # seal/integrity gates (fail-closed)
        audit = d.get("session_audit") or {}
        if audit and audit.get("seal_before_reveal") is False:
            return AcceptanceDecision.REJECT
        if audit and audit.get("forbidden_clean") is False:
            return AcceptanceDecision.REJECT
        integ = (d.get("integrity") or {}).get("post_run") or {}
        if "ok" in integ and not integ.get("ok"):
            return AcceptanceDecision.REJECT
        if st == "PARTIAL":
            limits = list((d.get("verdict") or {}).get("limitations") or []) + list(d.get("limitations") or [])
            if not limits:
                return AcceptanceDecision.WITHHOLD
        return _MAP[st]
    except Exception:
        return AcceptanceDecision.REJECT
