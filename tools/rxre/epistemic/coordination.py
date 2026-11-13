"""Ledger coordinación PREPARED→EFFECT_APPLIED→CONFIRMED (extracción, stdlib)."""
from __future__ import annotations
import hashlib, json
_LEDGER: dict = {}

def prepare(operation_id: str) -> None:
    if not operation_id:
        raise ValueError("operation_id requerido")
    _LEDGER[operation_id] = {"state": "PREPARED", "effects": {}}

def record_effect(operation_id: str, effect_id: str, evidence_digest: str) -> None:
    if operation_id not in _LEDGER:
        raise ValueError("operation no preparada")
    if not effect_id or not evidence_digest:
        raise ValueError("effect_id/evidence_digest requeridos")
    _LEDGER[operation_id]["effects"][effect_id] = evidence_digest
    _LEDGER[operation_id]["state"] = "EFFECT_APPLIED"

def confirm(operation_id: str) -> None:
    if operation_id not in _LEDGER:
        raise ValueError("operation no encontrada")
    _LEDGER[operation_id]["state"] = "CONFIRMED"

def reconcile(operation_id: str, ledger_state: str, effect_evidence: dict) -> str:
    """Pura, sin efectos (misma semántica que contracts.coordination_adapter)."""
    if not operation_id:
        return "NEEDS_REVIEW"
    ev = effect_evidence or {}
    effect_exists = ev.get("effect_exists", False)
    effect_verified = ev.get("effect_verified", False)
    identity_match = ev.get("identity_match", False)
    digest_match = ev.get("digest_match", False)
    scope_match = ev.get("scope_match", False)
    contradiction = ev.get("contradiction", False)
    if contradiction:
        return "NEEDS_REVIEW"
    if ledger_state == "CONFIRMED":
        if effect_exists and effect_verified and identity_match and digest_match and scope_match:
            return "CONFIRMED"
        if effect_exists and not (effect_verified and identity_match and digest_match and scope_match):
            return "NEEDS_REVIEW"
        if not effect_exists:
            return "NEEDS_REVIEW"
        return "INDETERMINATE"
    if ledger_state == "EFFECT_APPLIED":
        if effect_exists and effect_verified and identity_match and digest_match and scope_match:
            return "CONFIRMED"
        if not effect_exists:
            return "NEEDS_REVIEW"
        return "INDETERMINATE"
    if ledger_state == "PREPARED":
        if effect_exists and effect_verified and identity_match and digest_match and scope_match:
            return "CONFIRMED"
        if not effect_exists:
            return "RETRY_SAFE" if ev.get("absence_demonstrated", False) else "INDETERMINATE"
        return "INDETERMINATE"
    if effect_exists and effect_verified and identity_match and digest_match and scope_match:
        return "CONFIRMED"
    if not effect_exists and ev.get("absence_demonstrated", False):
        return "RETRY_SAFE"
    return "INDETERMINATE"
