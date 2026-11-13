#!/usr/bin/env python3
"""RXRE-MISSION-258 — CONTRATO AISLADO DE LIMITACIONES PERSISTENTES (no integrado, no modifica DB_ISO real).
Diseñado con esquema aislado que extiende claims con `limitations_json` (reversible).
No escribe en DB_OP; no activa op:claim; no modifica core/store.py ni machine.py.
"""
import sqlite3, os, json, tempfile

SCHEMA_ISOLADO = "CREATE TABLE claims (claim_id TEXT PRIMARY KEY, statement TEXT, object_hash TEXT, scope TEXT, epistemic_state TEXT, evidence_refs TEXT, derivation_refs TEXT, contradiction_refs TEXT, falsification_test TEXT, unresolved_obligations TEXT, revaluation_ref TEXT, version INTEGER DEFAULT 1, limitations_json TEXT DEFAULT '{}', created_at TEXT, updated_at TEXT)"


def migrar_limitaciones_reversible(path: str) -> dict:
    """P3 (261): migración idempotente; usa `limitaciones_json`; si la columna `limitations` ya existe (esquema real DB_ISO alternativo), documenta compatibilidad."""
    try:
        con = sqlite3.connect(path)
        existing = con.execute("PRAGMA table_info(claims)").fetchall()
        cols = [r[1] for r in existing]
        if "limitations_json" in cols:
            con.close()
            return {"migrada": False, "motivo": "columnas ya existe (idempotente)", "columna": "limitations_json"}
        if "limitations" in cols:
            # Esquema real de DB_ISO con `limitations` existente; no requiere ALTER pero se documenta
            con.close()
            return {"migrada": False, "motivo": "esquema real usa `limitations` (compatible); `limitaciones_json` NO compatible con nombre; extensión reversible cancelada", "columna_compatible": "limitations", "limitaciones_json_compatible": False}
        con.execute("ALTER TABLE claims ADD COLUMN limitations_json TEXT DEFAULT '{}'")
        con.commit()
        con.close()
        return {"migrada": True, "motivo": "ALTER TABLE claims ADD COLUMN limitations_json (reversible)", "columna": "limitations_json"}
    except Exception as exc:
        return {"migrada": False, "motivo": str(exc), "columna": None}

def crear_base_isolada(path: str):
    con = sqlite3.connect(path)
    con.execute("DROP TABLE IF EXISTS claims")
    con.execute(SCHEMA_ISOLADO)
    con.commit()
    con.close()


def guardar_limitacion(path: str, claim_id: str, decision_contract: str, decision_flujo: str,
                       limitaciones: list, referencias: list = None, procedencia_scope: str = None):
    con = sqlite3.connect(path)
    con.execute(
        "UPDATE claims SET limitations_json = ?, version = version + 1, updated_at = datetime('now') WHERE claim_id = ?",
        (json.dumps({
            "decision_contract": decision_contract,
            "decision_flujo": decision_flujo,
            "limitaciones": limitaciones,
            "referencias_evaluadas": referencias or [],
            "procedencia_scope_autoridad": procedencia_scope,
            "revisable": decision_contract not in ("CONFLICT", "INVALID"),
        }, ensure_ascii=False), claim_id),
    )
    con.commit()
    con.close()


def leer_limitacion(path: str, claim_id: str) -> dict:
    try:
        con = sqlite3.connect(path)
        row = con.execute("SELECT claim_id, scope, epistemic_state, limitations_json FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        con.close()
    except Exception as exc:
        return {"claim_id": claim_id, "existe": False, "error": str(exc), "limitaciones": None, "revisable": False}
    if not row:
        return {"claim_id": claim_id, "existe": False, "limitaciones": None, "revisable": False}
    claim, scope, epi, lim_json = row
    try:
        lim = json.loads(lim_json or "{}")
    except Exception:
        lim = {}
    return {
        "claim_id": claim,
        "scope": scope,
        "epistemic_state": epi,
        "existe": True,
        "limitaciones_json": lim,
        "revisable": lim.get("revisable", False),
        "decision_contract": lim.get("decision_contract"),
        "decision_flujo": lim.get("decision_flujo"),
    }


def retirar_limitacion(path: str, claim_id: str, evidencia_nueva: dict = None):
    """Retirada de limitacion requiere evidencia_verificada; documenta condicion."""
    lim = leer_limitacion(path, claim_id)
    if not lim["existe"]:
        return {"retirada": False, "motivo": "claim sin registro de limitaciones"}
    if not lim.get("revisable"):
        return {"retirada": False, "motivo": "limitacion no revisable (CONFLICT/INVALID)"}
    if not evidencia_nueva or evidencia_nueva.get("autenticidad") != "VERIFIED":
        return {"retirada": False, "motivo": "falta evidencia_verificada para retirar limitacion"}
    con = sqlite3.connect(path)
    # Actualiza epistemic_state si la evidencia confirma (simulado; no se afirma PROVEN sin verificacion real)
    # La retirada no promueve a PROVEN; documenta evidencia de revision y mantiene limits como revisado
    con.execute("UPDATE claims SET limitations_json = ?, updated_at = datetime('now') WHERE claim_id = ?",
                 (json.dumps({**(lim.get("limitaciones_json") or {}),
                              "revision_evidencia": evidencia_nueva,
                              "retirada_resultado": "LIMITACION_REVISADA",
                              "revisable": False}), claim_id))
    con.commit()
    con.close()
    return {"retirada": True, "limitaciones_anteriores": lim.get("limitaciones_json"), "evidencia_nueva": evidencia_nueva}
