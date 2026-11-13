"""RXRE-CONTINUATION-252 — Adaptador de coordinación desacoplado.

Módulo independiente para coordinar operaciones multialmacén mediante
interfaces existentes y un ledger separado. No modifica contratos
protegidos ni activa integración productiva.

Estados: PREPARED → EFFECT_APPLIED → CONFIRMED
Resultados de reconciliación: CONFIRMED, RETRY_SAFE, NEEDS_REVIEW, INDETERMINATE
"""
from __future__ import annotations

import sqlite3, json, os, time, threading, hashlib

SCHEMA = """
CREATE TABLE IF NOT EXISTS coordination_transitions (
    operation_id TEXT NOT NULL,
    state TEXT NOT NULL,
    ts REAL NOT NULL,
    effect_id TEXT,
    evidence_digest TEXT,
    store TEXT,
    detail TEXT,
    PRIMARY KEY (operation_id, state)
);
"""

VALID_STATES = {"PREPARED", "EFFECT_APPLIED", "CONFIRMED", "RECOVERY_REQUIRED", "BLOCKED", "REJECTED"}

RECONCILIATION_RESULTS = {"CONFIRMED", "RETRY_SAFE", "NEEDS_REVIEW", "INDETERMINATE"}


def connect_ledger(path: str):
    """Abre o crea el ledger de coordinación. Retorna conexión."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(SCHEMA)
    c.commit()
    return c


def prepare(c, operation_id: str, effect_id: str = None, detail: dict = None):
    """Registra PREPARED. Idempotente por PK compuesta."""
    if not operation_id or not isinstance(operation_id, str):
        raise ValueError("operation_id inválido")
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "INSERT INTO coordination_transitions(operation_id,state,ts,effect_id,detail) VALUES(?,?,?,?,?)",
            (operation_id, "PREPARED", time.time(), effect_id, json.dumps(detail or {})),
        )
        c.execute("COMMIT")
    except sqlite3.IntegrityError:
        c.execute("ROLLBACK")
        # Ya existe PREPARED → idempotente, no error
    except Exception:
        c.execute("ROLLBACK")
        raise


def record_effect(c, operation_id: str, effect_id: str, evidence_digest: str,
                  store: str = None, detail: dict = None):
    """Registra EFFECT_APPLIED. Requiere PREPARED previo."""
    if not operation_id or not effect_id:
        raise ValueError("operation_id y effect_id obligatorios")
    # Verificar que PREPARED existe
    row = c.execute(
        "SELECT 1 FROM coordination_transitions WHERE operation_id=? AND state='PREPARED'",
        (operation_id,),
    ).fetchone()
    if not row:
        raise ValueError("PREPARED no existe para %s" % operation_id)
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "INSERT INTO coordination_transitions(operation_id,state,ts,effect_id,evidence_digest,store,detail) VALUES(?,?,?,?,?,?,?)",
            (operation_id, "EFFECT_APPLIED", time.time(), effect_id, evidence_digest, store, json.dumps(detail or {})),
        )
        c.execute("COMMIT")
    except sqlite3.IntegrityError:
        c.execute("ROLLBACK")
    except Exception:
        c.execute("ROLLBACK")
        raise


def confirm(c, operation_id: str, evidence_digest: str = None, detail: dict = None):
    """Registra CONFIRMED. Requiere EFFECT_APPLIED previo."""
    row = c.execute(
        "SELECT 1 FROM coordination_transitions WHERE operation_id=? AND state='EFFECT_APPLIED'",
        (operation_id,),
    ).fetchone()
    if not row:
        raise ValueError("EFFECT_APPLIED no existe para %s" % operation_id)
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "INSERT INTO coordination_transitions(operation_id,state,ts,evidence_digest,detail) VALUES(?,?,?,?,?)",
            (operation_id, "CONFIRMED", time.time(), evidence_digest, json.dumps(detail or {})),
        )
        c.execute("COMMIT")
    except sqlite3.IntegrityError:
        c.execute("ROLLBACK")
    except Exception:
        c.execute("ROLLBACK")
        raise


def get_status(c, operation_id: str) -> str:
    """Devuelve el estado más reciente del ledger para una operación."""
    row = c.execute(
        "SELECT state FROM coordination_transitions WHERE operation_id=? ORDER BY ts DESC LIMIT 1",
        (operation_id,),
    ).fetchone()
    return row[0] if row else None


def all_states(c, operation_id: str) -> list:
    """Devuelve todos los estados registrados para una operación."""
    return [r[0] for r in c.execute(
        "SELECT state FROM coordination_transitions WHERE operation_id=? ORDER BY ts",
        (operation_id,),
    ).fetchall()]


def reconcile(operation_id: str, ledger_state: str, effect_evidence: dict) -> str:
    """Función de decisión pura. No lee ni escribe.

    Parámetros:
        operation_id: identidad de la operación.
        ledger_state: estado actual del ledger (PREPARED, EFFECT_APPLIED, CONFIRMED, o None).
        effect_evidence: dict con claves:
            - 'effect_exists': bool (evidencia de que el efecto ocurrió)
            - 'effect_verified': bool (evidencia suficiente para confirmar)
            - 'identity_match': bool (identidad coincide)
            - 'digest_match': bool (digest coincide)
            - 'scope_match': bool (scope coincide)
            - 'contradiction': bool (hay contradicción)

    Retorna: CONFIRMED, RETRY_SAFE, NEEDS_REVIEW o INDETERMINATE.
    """
    if not operation_id:
        return "NEEDS_REVIEW"

    ev = effect_evidence or {}
    effect_exists = ev.get("effect_exists", False)
    effect_verified = ev.get("effect_verified", False)
    identity_match = ev.get("identity_match", False)
    digest_match = ev.get("digest_match", False)
    scope_match = ev.get("scope_match", False)
    contradiction = ev.get("contradiction", False)

    # Contradicción → NEEDS_REVIEW
    if contradiction:
        return "NEEDS_REVIEW"

    # CONFIRMED: requiere efecto verificado + identidad + digest + scope
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
            return "NEEDS_REVIEW"  # efecto ausente tras EFFECT_APPLIED → contradicción
        return "INDETERMINATE"

    if ledger_state == "PREPARED":
        if effect_exists and effect_verified and identity_match and digest_match and scope_match:
            return "CONFIRMED"
        if not effect_exists:
            # PREPARED no demuestra ausencia; pero si se puede demostrar ausencia → RETRY_SAFE
            if ev.get("absence_demonstrated", False):
                return "RETRY_SAFE"
            return "INDETERMINATE"
        return "INDETERMINATE"

    # ledger_state is None or unknown
    if effect_exists and effect_verified and identity_match and digest_match and scope_match:
        return "CONFIRMED"
    if not effect_exists and ev.get("absence_demonstrated", False):
        return "RETRY_SAFE"
    return "INDETERMINATE"


def reconcile_operation(c, operation_id: str, evidence_provider=None) -> str:
    """Reconciliación completa: lee ledger + evidencia, produce decisión.

    evidence_provider: callable que recibe operation_id y devuelve effect_evidence dict.
    No ejecuta efectos. No modifica el ledger.
    """
    state = get_status(c, operation_id)
    evidence = {}
    if callable(evidence_provider):
        try:
            evidence = evidence_provider(operation_id) or {}
        except Exception:
            evidence = {}
    return reconcile(operation_id, state, evidence)
