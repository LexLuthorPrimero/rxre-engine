#!/usr/bin/env python3
"""Compuerta de autorización de scope para la migración (M275, ensayo).
Rechaza cualquier escritura de `scope` que no tenga autorización verificable.
No escribe en DB_OP; devuelve un veredicto. Un hash válido NO sustituye autorización.
"""
import os, re

DECISION_PATH = "/home/lucas/Escritorio/rxre/audit/debugfs/SCOPE_AUTHORITY_DECISION.md"

def leer_decision_autoridad(path=DECISION_PATH):
    """Verifica el documento de autoridad. Devuelve dict o None si no es utilizable.
    Autenticidad: DOCUMENTED_AUTHORITY (verificación documental, NO criptográfica)."""
    if not path or not os.path.isfile(path):
        return None
    try:
        txt = open(path, "r", encoding="utf-8").read()
    except OSError:
        return None
    estado = re.search(r"^Estado:\s*`?([A-Z_]+)`?", txt, re.M)
    operador = re.search(r"^Operador:\s*(\S+)", txt, re.M)
    fecha = re.search(r"^Fecha:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", txt, re.M)
    if not estado:
        return None
    return {
        "estado": estado.group(1),
        "operador": operador.group(1) if operador else None,
        "fecha": fecha.group(1) if fecha else None,
        "autenticidad": "DOCUMENTED_AUTHORITY",
        "ruta": path,
    }

def evaluar_insercion_scope(declared_scope, authorized_scope, authorization=None, decision=None):
    """Veredicto de compuerta. NUNCA autoriza por hash ni por existencia de manifiesto.
    Retorna dict con decision, motivo, y (si aplica) los campos aceptados."""
    decision_doc = decision if decision is not None else leer_decision_autoridad()
    base = {
        "decision": "REJECT",
        "motivo": "",
        "autenticidad": None,
        "declared_scope": declared_scope,
        "authorized_scope": authorized_scope,
        "documento": decision_doc,
    }
    if authorization is None or not isinstance(authorization, dict):
        base["motivo"] = "autorización ausente o malformada: no se escribe scope"
        return base
    if authorization.get("decision") != "AUTHORIZED":
        base["motivo"] = "autorización con decisión distinta de AUTHORIZED"
        return base
    actor = authorization.get("actor")
    if not actor:
        base["motivo"] = "autorización sin actor identificable"
        return base
    if not authorization.get("timestamp"):
        base["motivo"] = "autorización sin timestamp (no puede distinguirse de reconstrucción retrospectiva)"
        return base
    if not authorized_scope:
        base["motivo"] = "authorized_scope vacío: no se escribe scope"
        return base
    if declared_scope and declared_scope != authorized_scope:
        base["motivo"] = "conflicto: declared_scope (%s) != authorized_scope (%s)" % (declared_scope, authorized_scope)
        base["decision"] = "CONFLICT"
        return base
    if decision_doc is None or decision_doc.get("estado") != "APPROVED":
        base["motivo"] = "documento de autoridad ausente o no APPROVED"
        return base
    if decision_doc.get("operador") != actor:
        base["motivo"] = "actor de la autorización (%s) no coincide con el documento (%s)" % (actor, decision_doc.get("operador"))
        return base
    base["decision"] = "ACCEPT"
    base["motivo"] = "autorización documentada yContemporary; autenticidad DOCUMENTED_AUTHORITY (no criptográfica)"
    base["autenticidad"] = "DOCUMENTED_AUTHORITY"
    base["actor"] = actor
    base["timestamp"] = authorization.get("timestamp")
    return base
