#!/usr/bin/env python3
"""RXRE-MISSION-243/244 — CADENA DE VERIFICACIÓN SEMÁNTICA AISLADA.
No activa op:claim; no modifica machine.py desde este módulo; no escribe en DB_OP.

Fronteras verificadas (en este orden, antes de cualquier transicion):
  1. referencia   -> debe resolverse externamente (no por pertenencia a la lista)
  2. integridad   -> artefacto/manifest observable y coherente
  3. semantica    -> SUPPORTED / REFUTED / INSUFFICIENT (evidencia_integrity NO es respaldo)
  4. autenticidad -> hash registrado (DB_OP) o manifest E2E validado
  5. scope        -> no incompatible

`verificar_precondiciones` NO escribe: es la consulta previa a persistir.
`cadena_verificacion_aislada` verifica y luego persiste (solo si la cadena pasa).
"""
import os, sqlite3, sys
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
from rxre.core.evidence_integrity import validate_evidence_path
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.isolated_contract_implementations import verificar_compatibilidad_scope, transitar_epistemico

DB_ISO_DEFAULT = "/tmp/rxre_239_iso.sqlite3"


def verificar_precondiciones(
    finding_dict: dict,
    resolver_refs,
    claim_propiedad: dict = None,
    artifact_path: str = None,
    evidence_path: str = None,
    grafo_path: str = None,
) -> dict:
    """VERIFICACION (sin escritura) de las precondiciones previas a persistir.

    Devuelve:
      {"decision": "ACCEPT"|"REJECT"|"NEEDS_INPUT",
       "frontera": "referencia"|"integridad"|"semantica"|"autenticidad"|"scope"|"ok",
       "motivo": str, "referencias": {...}, "integridad": {...},
       "semantica": {...}, "autenticidad": {...}, "scope": {...}}
    """
    out = {"decision": None, "frontera": None, "motivo": "",
           "referencias": {}, "integridad": {}, "semantica": {},
           "autenticidad": {}, "scope": {}}

    # --- 1) Referencia: resolución externa obligatoria (misión 242) ---
    if not callable(resolver_refs):
        out.update(decision="NEEDS_INPUT", frontera="referencia",
                   motivo="resolver_refs debe ser una funcion verificable; no se admite pertenencia a la lista")
        return out
    refs = finding_dict.get("evidence_ids") or finding_dict.get("evidence_refs") or []
    faltan = [r for r in refs if not resolver_refs(r)]
    out["referencias"] = {"declaradas": list(refs),
                          "resueltas": [r for r in refs if r not in faltan],
                          "faltantes": faltan}
    if faltan:
        out.update(decision="REJECT", frontera="referencia",
                   motivo="referencias no resolubles: %s (trazabilidad no verificada)" % ",".join(faltan))
        return out

    # --- 2) Integridad del artefacto observable ---
    if evidence_path and os.path.exists(evidence_path):
        int_res = validate_evidence_path(evidence_path, art_path=artifact_path)
    elif artifact_path and os.path.exists(artifact_path):
        int_res = {"ok": True, "checks": {"archivo_existe": True}, "errors": [],
                   "nota": "sin manifest E2E; la autenticidad se acredita con el hash registrado en DB_OP"}
    else:
        int_res = {"ok": False, "checks": {}, "errors": ["artefacto no disponible"],
                   "nota": "falta evidencia observable"}
    out["integridad"] = int_res
    if not int_res.get("ok"):
        out.update(decision="REJECT", frontera="integridad",
                   motivo="integridad fallida: %s" % str(int_res.get("errors")))
        return out

    # --- 3) Respaldo semántico (integridad NO equivale a respaldo) ---
    if not claim_propiedad:
        out.update(decision="NEEDS_INPUT", frontera="semantica",
                   motivo="falta verificacion semantica (claim_propiedad): la integridad no equivale a respaldo")
        return out
    if not artifact_path or not os.path.exists(artifact_path):
        out.update(decision="REJECT", frontera="semantica",
                   motivo="artefacto no disponible para verificar la propiedad")
        return out
    sem = verificar_propiedad_artefacto(artifact_path, claim_propiedad,
                                        evidencia_refs=list(refs), resolver_refs=resolver_refs)
    out["semantica"] = sem
    res_sem = sem.get("resultado")
    if res_sem == "REFUTED":
        out.update(decision="REJECT", frontera="semantica",
                   motivo="respaldo semantico REFUTED: la evidencia observacional contradice la afirmacion")
        return out
    if res_sem not in ("SUPPORTED", "INSUFFICIENT"):
        out.update(decision="REJECT", frontera="semantica",
                   motivo="resultado semantico no reconocido: %r; no se persiste" % res_sem)
        return out

    # --- 4) Autenticidad: hash registrado (DB_OP) o manifest E2E validado ---
    integ = sem.get("integridad_evidencia") or {}
    hash_reg = integ.get("hash_registrado_operativo")
    coincide = bool(integ.get("hash_coincide"))
    manifest_ok = bool(evidence_path and (int_res.get("checks") or {}).get("hash_matches"))
    out["autenticidad"] = {"hash_registrado_operativo": hash_reg, "hash_coincide": coincide,
                           "manifest_e2e_validado": manifest_ok}
    if not ((hash_reg and coincide) or manifest_ok):
        out.update(decision="REJECT", frontera="autenticidad",
                   motivo="autenticidad no acreditada: sin hash registrado coincidente ni manifest E2E validado")
        return out

    # --- 5) Scope / comparabilidad ---
    scope_compat = verificar_compatibilidad_scope(
        finding_dict.get("scope", ""), list(refs), artifact_path=artifact_path,
        resolver_refs=resolver_refs, grafo_path=grafo_path or DB_ISO_DEFAULT)
    out["scope"] = scope_compat
    if scope_compat.get("compatibilidad") == "incompatible":
        out.update(decision="REJECT", frontera="scope",
                   motivo="scope incompatible: %s" % scope_compat.get("motivo"))
        return out

    if res_sem == "INSUFFICIENT":
        out.update(decision="REJECT", frontera="semantica",
                   motivo="respaldo semantico INSUFFICIENT: la evidencia no permite concluir; no se demuestra el claim")
        return out

    out.update(decision="ACCEPT", frontera="ok",
               motivo="referencia resuelta, integridad y autenticidad acreditadas, respaldo semantico SUPPORTED, scope no incompatible")
    return out


def cadena_verificacion_aislada(
    db_path: str,
    finding_dict: dict,
    resolver_refs,
    claim_propiedad: dict = None,
    artifact_path: str = None,
    evidence_path: str = None,
    explicit_enable: bool = True,
    contradiction_statements=None,
) -> dict:
    """Verifica la cadena y, solo si pasa, persiste en DB aislada."""
    pre = verificar_precondiciones(
        finding_dict, resolver_refs=resolver_refs, claim_propiedad=claim_propiedad,
        artifact_path=artifact_path, evidence_path=evidence_path, grafo_path=db_path)
    if pre["decision"] != "ACCEPT":
        return {"status": "blocked", "decision": pre["decision"],
                "motivo": pre["motivo"], "claim_id": None, "db_path": db_path,
                "cadena": pre, "cadena_completa": True}
    result = preintegrate_finding_to_tierra(
        db_path, finding_dict, resolver_refs=resolver_refs,
        contradiction_statements=contradiction_statements, explicit_enable=explicit_enable)
    result["cadena"] = pre
    result["verificacion_integridad"] = pre["integridad"]
    result["verificacion_semantica"] = pre["semantica"]
    result["autenticidad"] = pre["autenticidad"]
    result["scope_compat"] = pre["scope"]
    result["cadena_completa"] = True
    return result
