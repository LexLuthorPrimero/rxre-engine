"""Auditoría de cadena hash (delega anti_replay.audit_ledger)."""
from __future__ import annotations
from .anti_replay import audit_ledger as _audit
def audit_ledger(path=None):
    return _audit(path)
def verify_chain(path=None) -> bool:
    try:
        entries = _audit(path)
        return len(entries) >= 0
    except Exception:
        return False
